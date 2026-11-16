"""One DB coordinator and at most two isolated, frozen inference calls.

Admission slots are process-local: one call per event and per provider/model.
They do not claim cross-process concurrency safety on SQLite. All worker DB
phases and observations stay on the coordinator; other HTTP requests retain
their normal application transactions. No retries or coordinator Jobs are added.
"""
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from queue import Empty, Queue
import threading

from django.contrib.auth import get_user_model
from django.core.management.base import CommandError
from django.db import close_old_connections
from django.db.models import Q
from django.utils import timezone

from apps.events.management.commands.runlocal import Command as LocalCommand
from apps.jobs.models import Job
from apps.jobs.services import (InferenceResult, claim_next, finish_inference,
                               perform_inference, prepare_claim)
from apps.jobs.trace import observe_stage


MAX_PARALLEL_INFERENCES = 2
FROZEN_PROVIDERS = {"openai", "opencode"}


@dataclass
class _Observation:
    prepared: object
    stage: str
    ready: threading.Event = field(default_factory=threading.Event)
    accepted: bool = False
    abandoned: bool = False


def next_controlled_job(owner_id, *, excluded_jobs=(), excluded_events=(), excluded_models=(), parallel_only=False):
    from apps.assistant.demo_pilot import PILOT_EVENT_ID
    candidates = Job.objects.filter(actor_id=owner_id, event__owner_id=owner_id).filter(
        Q(event__is_synthetic=True) | Q(event_id=PILOT_EVENT_ID, compact_request__version=1,
            ai_usage__snapshot__compact_contract=1, ai_usage__snapshot__provider="opencode",
            ai_usage__snapshot__mode="free", ai_usage__snapshot__agent_route="free_pool")
        | Q(event_id=PILOT_EVENT_ID, compact_request__version=1, ai_usage__snapshot__compact_contract=1,
            ai_usage__snapshot__provider="openai", ai_usage__snapshot__mode="paid",
            ai_usage__snapshot__model="gpt-5.4-mini", ai_usage__snapshot__agent_route="primary")
    ).filter(
        Q(ai_usage__snapshot__provider="openai", ai_usage__snapshot__model__in=["gpt-5.4-mini", "gpt-6-luna"])
        | Q(ai_usage__snapshot__provider__in=["openai", "opencode", "groq", "gemini", "ollama"],
            ai_usage__snapshot__agent_grant_id__isnull=False)
    ).filter(Q(status=Job.Status.QUEUED) | Q(status=Job.Status.RUNNING, lease_until__lte=timezone.now())
    ).exclude(pk__in=excluded_jobs).exclude(event_id__in=excluded_events)
    for provider, model in excluded_models:
        candidates = candidates.exclude(ai_usage__snapshot__provider=provider, ai_usage__snapshot__model=model)
    if parallel_only:
        candidates = candidates.filter(ai_usage__snapshot__provider__in=FROZEN_PROVIDERS)
    return candidates.order_by("created_at", "id").values_list("pk", flat=True).first()


class Command(LocalCommand):
    help = "Inicia Gica-1 local: web y worker para solicitudes controladas y el piloto compacto minimizado de adminjorge."
    runtime_description = "ArquiGica incluye Gica-1: un coordinador y hasta dos inferencias independientes. Las rutas habituales sólo admiten eventos ficticios; el piloto compacto exporta únicamente un tema público y opciones cerradas por la ruta elegida explícitamente. OpenAI conserva el tope global acumulado de USD 1 y los presupuestos por cuenta y agente; no hay cambio automático de proveedor."

    def add_arguments(self, parser):
        super().add_arguments(parser)
        parser.add_argument("--username", default="adminjorge")

    def handle(self, *args, **options):
        owner = get_user_model().objects.filter(username=options["username"], is_active=True, is_superuser=True).first()
        if owner is None:
            raise CommandError("El piloto requiere la cuenta administradora activa.")
        self.owner_id = owner.pk
        self.stop_worker = threading.Event()
        self.worker = None
        super().handle(*args, **options)

    def on_server_started(self):
        self.worker = threading.Thread(target=self._work, name="romeo-1-coordinator", daemon=False)
        self.worker.start()

    def _accept_observation(self, observation):
        try:
            if not observation.abandoned:
                prepared = observation.prepared
                observe_stage(prepared.job_id, prepared.token, observation.stage)
                observation.accepted = True
        except Exception:
            # Only a boolean crosses back to the inference thread, never a DB
            # error, credential, prompt or exception body.
            observation.accepted = False
        finally:
            observation.ready.set()

    def _relay(self, observations, prepared):
        def observe(stage):
            if stage not in {"context_ready", "request_started", "response_received"}:
                raise ValueError("Unexpected inference observation")
            observation = _Observation(prepared, stage)
            observations.put(observation)
            if not observation.ready.wait(timeout=10):
                observation.abandoned = True
                raise ValueError("Coordinator did not acknowledge the inference")
            if not observation.accepted:
                raise ValueError("Execution no longer owns the inference")
        return observe

    def _work(self):
        observations = Queue()
        in_flight = {}
        try:
            with ThreadPoolExecutor(max_workers=MAX_PARALLEL_INFERENCES, thread_name_prefix="romeo-inference") as executor:
                # Stop admission on shutdown, but keep servicing observations
                # and settling both calls before the runtime emits completion.
                while not self.stop_worker.is_set() or in_flight:
                    try:
                        close_old_connections()
                        while True:
                            try:
                                self._accept_observation(observations.get_nowait())
                            except Empty:
                                break
                        for future, prepared in list(in_flight.items()):
                            if not future.done():
                                continue
                            try:
                                try:
                                    result = future.result()
                                except Exception:
                                    result = InferenceResult(prepared.job_id, prepared.token, failed=True)
                                finish_inference(prepared, result)
                            finally:
                                # This attempt is never submitted again, even
                                # if settlement failed and its lease must expire.
                                del in_flight[future]
                        if not self.stop_worker.is_set() and len(in_flight) < MAX_PARALLEL_INFERENCES:
                            active = list(in_flight.values())
                            job_id = next_controlled_job(self.owner_id,
                                excluded_jobs=[item.job_id for item in active],
                                excluded_events=[item.event_id for item in active],
                                excluded_models=[(item.snapshot["provider"], item.snapshot["model"]) for item in active],
                                parallel_only=bool(active))
                            if job_id is not None:
                                claim = claim_next(job_id=job_id)
                                prepared = prepare_claim(claim, for_parallel=True) if claim else None
                                if prepared is not None:
                                    if prepared.parallel_safe:
                                        future = executor.submit(perform_inference, prepared,
                                            observer=self._relay(observations, prepared))
                                        in_flight[future] = prepared
                                    else:
                                        # Generic adapters still read ORM while
                                        # constructing payloads. Run them only
                                        # on this coordinator, with no live calls.
                                        result = perform_inference(prepared,
                                            observer=lambda stage: observe_stage(prepared.job_id, prepared.token, stage))
                                        finish_inference(prepared, result)
                                continue
                    except Exception:
                        self.stderr.write("Gica-1 detuvo un intento. Revisa Actividad; no hay reintento automático de llamada.")
                    if in_flight:
                        try:
                            self._accept_observation(observations.get(timeout=.05))
                        except Empty:
                            pass
                    else:
                        self.stop_worker.wait(2)
        finally:
            # A catastrophic coordinator exit cannot leave a relay waiting
            # forever. Normal shutdown reaches here after both results settle.
            while True:
                try:
                    observation = observations.get_nowait()
                except Empty:
                    break
                observation.abandoned = True
                observation.ready.set()
            close_old_connections()

    def on_server_stopping(self):
        self.stop_worker.set()
        if self.worker:
            self.worker.join()
