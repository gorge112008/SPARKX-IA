"""Consent replay, revocation and UI boundaries, with no remote model calls."""
from copy import deepcopy
import time
from types import SimpleNamespace
import uuid
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from apps.events.models import Event
from apps.jobs.models import Job
from apps.jobs.services import enqueue, run_one
from apps.ai_management.model_policy import bind_request_consent, request_policy_context, validate_job_consent
from apps.ai_management.models import AIAccount, AIProfile, AIUsage
from apps.ai_management.services import configured_snapshot


class PolicyBindingTests(SimpleTestCase):
    def setUp(self):
        self.actor = SimpleNamespace(pk=1)
        self.event = SimpleNamespace(pk=uuid.uuid4(), revision=1)
        self.snapshot = {"provider": "opencode", "model": "beam-free", "profile_id": 10, "profile_version": 1}
        self.params = {"event": self.event, "actor": self.actor, "kind": "plan", "request_key": str(uuid.uuid4())}
        self.token = request_policy_context(self.snapshot, **self.params)["token"]

    def test_token_is_scoped_to_actor_event_revision_action_request_profile_model_and_policy(self):
        mutations = [
            ({}, {"actor": SimpleNamespace(pk=2)}),
            ({}, {"event": SimpleNamespace(pk=uuid.uuid4(), revision=1)}),
            ({}, {"event": SimpleNamespace(pk=self.event.pk, revision=2)}),
            ({}, {"kind": "chat"}), ({}, {"request_key": str(uuid.uuid4())}),
            ({"profile_id": 11}, {}), ({"profile_version": 2}, {}),
            ({"model": "longcat-2.5-free"}, {}),
        ]
        for snapshot_change, params_change in mutations:
            with self.subTest(snapshot=snapshot_change, params=params_change):
                with self.assertRaises(ValidationError):
                    bind_request_consent({**self.snapshot, **snapshot_change}, token=self.token, **{**self.params, **params_change})
        with patch("apps.ai_management.model_policy.policy_fingerprint", return_value="0" * 64):
            with self.assertRaises(ValidationError):
                bind_request_consent(self.snapshot, token=self.token, **self.params)

    def test_expired_forged_missing_and_non_string_tokens_fail(self):
        for token in (None, True, {}, self.token + "tamper", "x" * 4097):
            with self.subTest(token_type=type(token).__name__):
                with self.assertRaises(ValidationError):
                    bind_request_consent(self.snapshot, token=token, **self.params)
        with patch("django.core.signing.time.time", return_value=time.time() + 3602):
            with self.assertRaises(ValidationError):
                bind_request_consent(self.snapshot, token=self.token, **self.params)

    def test_receipt_is_recorded_and_revalidated_without_changing_original_snapshot(self):
        original = deepcopy(self.snapshot)
        accepted = bind_request_consent(self.snapshot, token=self.token, **self.params)
        self.assertEqual(self.snapshot, original)
        self.assertTrue(accepted["model_policy_consent"]["acknowledged_at"])
        validate_job_consent(accepted, **self.params)
        for key in ("fingerprint", "model", "token"):
            changed = deepcopy(accepted)
            changed["model_policy_consent"][key] = "invalid"
            with self.subTest(key=key), self.assertRaises(ValidationError):
                validate_job_consent(changed, **self.params)


class PolicyJobBoundaryTests(TestCase):
    def setUp(self):
        self.owner = get_user_model().objects.create_user(username="policy-organizer")
        self.event = Event.objects.create(owner=self.owner, title="Fictional policy event", brief="Synthetic only", is_synthetic=True)
        self.profile = AIProfile.objects.create(owner=self.owner, name="Beam synthetic", provider="opencode", model="beam-free", mode="free", free_tier_confirmed=True, max_output_tokens=2048)
        self.account = AIAccount.objects.create(owner=self.owner, active_profile=self.profile, monthly_token_limit=1000000)
        self.ready = patch("apps.assistant.provider.profile_ready", return_value=True)
        self.ready.start()
        self.addCleanup(self.ready.stop)
        self.client.force_login(self.owner)

    def request(self, **changes):
        params = {"event": self.event, "actor": self.owner, "kind": "chat", "prompt": "Describe this synthetic event", "idempotency_key": str(uuid.uuid4())}
        params.update(changes)
        return params

    def token(self, params):
        return request_policy_context(configured_snapshot(self.account), event=params["event"], actor=params["actor"], kind=params["kind"], request_key=params["idempotency_key"])["token"]

    def test_missing_acknowledgement_creates_neither_job_nor_financial_reservation(self):
        with self.assertRaises(ValidationError):
            enqueue(**self.request())
        self.assertEqual(Job.objects.count(), 0)
        self.assertEqual(AIUsage.objects.count(), 0)

    def test_job_records_own_consent_and_duplicate_does_not_reserve_again(self):
        params = self.request()
        token = self.token(params)
        job = enqueue(**params, model_policy_token=token)
        self.assertEqual(enqueue(**params).pk, job.pk)
        self.assertEqual(AIUsage.objects.count(), 1)
        self.assertEqual(job.ai_usage.snapshot["model_policy_consent"]["token"], token)
        with self.assertRaises(ValidationError):
            enqueue(**self.request(), model_policy_token=token)

    def test_policy_change_while_queued_releases_reservation_without_dispatch(self):
        params = self.request()
        job = enqueue(**params, model_policy_token=self.token(params))
        with patch("apps.ai_management.model_policy.policy_fingerprint", return_value="1" * 64), patch("apps.assistant.provider.answer_question") as remote:
            run_one()
        job.refresh_from_db()
        self.assertEqual(job.status, "failed")
        self.assertEqual(job.ai_usage.status, "released")
        self.assertIsNone(job.ai_usage.dispatch_token)
        remote.assert_not_called()

    def test_both_ui_forms_display_specific_terms_unchecked_and_ignore_unchecked_token(self):
        page = self.client.get(reverse("events:detail", args=[self.event.pk]))
        self.assertContains(page, 'id="generate-policy-accept"')
        self.assertContains(page, 'id="chat-policy-accept"')
        self.assertContains(page, "30 días")
        for kind, route, content_key in (("plan", "generate", "brief"), ("chat", "chat", "message")):
            params = self.request(kind=kind)
            token = self.token(params)
            response = self.client.post(reverse("events:" + route, args=[self.event.pk]), {
                "idempotency_key": params["idempotency_key"], content_key: params["prompt"], "model_policy_token": token,
            }, HTTP_HX_REQUEST="true")
            self.assertContains(response, "acepta las condiciones")
        self.assertEqual(Job.objects.count(), 0)

    def test_accepted_htmx_request_rotates_key_token_and_resets_checkbox(self):
        params = self.request()
        token = self.token(params)
        response = self.client.post(reverse("events:chat", args=[self.event.pk]), {
            "idempotency_key": params["idempotency_key"], "message": params["prompt"],
            "model_policy_token": token, "accept_model_policy": "1",
        }, HTTP_HX_REQUEST="true")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="chat-model-policy" hx-swap-oob="outerHTML"')
        self.assertNotContains(response, token)
        self.assertNotContains(response, " checked")
        self.assertEqual(Job.objects.count(), 1)

    def test_local_directory_query_still_needs_no_privacy_acceptance_or_remote_job(self):
        response = self.client.post(reverse("events:chat", args=[self.event.pk]), {
            "idempotency_key": str(uuid.uuid4()), "message": "buscar expositores",
        }, HTTP_HX_REQUEST="true")
        self.assertContains(response, "Consulta local completada")
        self.assertEqual(Job.objects.count(), 0)
        self.assertEqual(AIUsage.objects.count(), 0)

    def test_worker_passes_only_each_models_own_policy_and_usage_to_the_bridge(self):
        from apps.ai_management.catalog import OPENCODE_DEMO_MODELS
        from tools.opencode.catalog import MODEL_POLICIES, policy_fingerprint
        for index, model in enumerate(sorted(OPENCODE_DEMO_MODELS), start=1):
            with self.subTest(model=model):
                self.profile.model = model
                self.profile.version += 1
                self.profile.save()
                params = self.request()
                context = request_policy_context(configured_snapshot(self.account), event=self.event,
                    actor=self.owner, kind="chat", request_key=params["idempotency_key"])
                job = enqueue(**params, model_policy_token=context["token"] if context else None)
                counters = {"input_tokens": index, "output_tokens": 1, "total_tokens": index + 1}
                with patch("apps.assistant.free_harness.run_free_harness",
                           return_value={"text": "Synthetic answer: " + model, "usage": counters}) as bridge:
                    run_one()
                job.refresh_from_db()
                self.assertEqual(job.status, "succeeded")
                self.assertEqual(job.ai_usage.total_tokens, index + 1)
                self.assertEqual(job.message.content, "Synthetic answer: " + model)
                self.assertEqual(bridge.call_args.kwargs["model"], model)
                expected = policy_fingerprint(model) if MODEL_POLICIES[model]["requires_policy_consent"] else None
                self.assertEqual(bridge.call_args.kwargs["policy_acknowledgement"], expected)
                history = bridge.call_args.kwargs["context"]["history"]
                self.assertEqual(history, [], "Another model's answers must not be sent to a fresh model")
