"""No remote calls: synthetic source boundaries and frozen free requests."""
import json
from copy import deepcopy
from unittest.mock import patch
from uuid import uuid4

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.directory.models import EventPerson, Organization, Person
from apps.directory.normalization import search_key
from apps.events.models import Event
from . import provider
from .local_queries import local_directory_reply
from .models import Message


class SyntheticContextTests(TestCase):
    def setUp(self):
        self.owner = get_user_model().objects.create_user(username="synthetic-context-owner")
        self.other = get_user_model().objects.create_user(username="synthetic-context-other")
        self.real_org = Organization.objects.create(owner=self.owner, name="Institución privada real", name_key="real")
        self.fake_org = Organization.objects.create(owner=self.owner, name="Instituto ficticio", name_key="fake", is_synthetic=True)
        self.event = Event.objects.create(owner=self.owner, title="Encuentro ficticio", brief="Demostración ficticia",
                                          is_synthetic=True, organization=self.real_org)
        self.fake = self.person("Ponente ficticio", synthetic=True, organization=self.real_org)
        self.real = self.person("Nombre privado real", synthetic=False, organization=self.real_org)
        self.foreign = self.person("Ponente ajeno", synthetic=True, owner=self.other)
        self.profile = {"provider": "opencode", "model": "glm-5.3-flash-free", "mode": "free",
                        "max_input_tokens": 64000, "max_output_tokens": 2048}

    def person(self, name, *, synthetic, owner=None, organization=None, category="speaker"):
        return Person.objects.create(owner=owner or self.owner, full_name=name, name_key=search_key(name),
                                     is_synthetic=synthetic, organization=organization, category=category,
                                     email=f"{uuid4().hex}@example.test", expertise="Especialidad ficticia")

    def local(self, prompt):
        return local_directory_reply(event=self.event, actor=self.owner, prompt=prompt, request_key=uuid4()).content

    def freeze(self, *, action="plan", prompt="Prepara una demostración", conversation=None):
        self.event._free_context_snapshot = provider.freeze_free_context(
            event=self.event, prompt=prompt, action=action, conversation=conversation,
        )
        return self.event._free_context_snapshot

    def test_local_speaker_query_filters_before_counting_and_hides_real_affiliation(self):
        for index in range(12):
            self.person(f"Otra persona real {index}", synthetic=False)
        result = self.local("buscar expositores")
        self.assertIn(self.fake.full_name, result)
        self.assertIn("1 resultado(s); muestro 1", result)
        self.assertNotIn(self.real.full_name, result)
        self.assertNotIn(self.foreign.full_name, result)
        self.assertNotIn(self.real_org.name, result)
        self.assertNotIn(self.fake.email, result)

    def test_local_queries_filter_participants_guests_and_event_links(self):
        for category, command in (("participant", "buscar participantes"), ("guest", "buscar invitados")):
            real = self.person(f"Persona real {category}", synthetic=False, category=category)
            fake = self.person(f"Persona ficticia {category}", synthetic=True, category=category, organization=self.fake_org)
            result = self.local(command)
            self.assertIn(fake.full_name, result)
            self.assertIn(self.fake_org.name, result)
            self.assertNotIn(real.full_name, result)
        for person in (self.fake, self.real, self.foreign):
            EventPerson.objects.create(event=self.event, person=person, role="speaker")
        result = self.local("personas de este evento")
        self.assertIn(self.fake.full_name, result)
        self.assertIn("1 resultado(s); muestro 1", result)
        for private in (self.real.full_name, self.foreign.full_name, self.real_org.name):
            self.assertNotIn(private, result)

    def test_local_event_search_excludes_real_events_and_real_organization_names(self):
        real = Event.objects.create(owner=self.owner, title="Evento privado real", brief="Privado", organization=self.real_org)
        fake = Event.objects.create(owner=self.owner, title="Otro encuentro ficticio", brief="Ficticio",
                                   is_synthetic=True, organization=self.fake_org)
        result = self.local("buscar eventos")
        self.assertIn(self.event.title, result)
        self.assertIn(fake.title, result)
        self.assertIn(self.fake_org.name, result)
        self.assertIn("2 resultado(s); muestro 2", result)
        self.assertNotIn(real.title, result)
        self.assertNotIn(self.real_org.name, result)

    def test_every_local_history_message_is_removed_before_the_free_history_limit(self):
        for index in range(5):
            Message.objects.create(event=self.event, role="user", content=f"Mensaje ficticio remoto {index}", request_key=f"remote-{index}")
        for index in range(12):
            Message.objects.create(event=self.event, role="assistant", content=f"Nombre privado histórico {index}",
                                   request_key="local:" + str(uuid4()))
        conversation = provider.chat_context(self.event)
        self.assertTrue(any("privado" in item["content"] for item in conversation["history"]))
        frozen = self.freeze(action="chat", conversation=conversation)
        history = frozen["context"]["history"]
        # Legacy strings without a Job/model receipt cannot authorize history.
        self.assertEqual(history, [])
        self.assertNotIn("Nombre privado histórico", json.dumps(frozen, ensure_ascii=False))

    def test_real_foreign_stale_and_mismatched_planning_references_fail_closed(self):
        for person, version, name in ((self.real, self.real.version, self.real.full_name),
                                      (self.foreign, self.foreign.version, self.foreign.full_name),
                                      (self.fake, self.fake.version + 1, self.fake.full_name),
                                      (self.fake, self.fake.version, self.real.full_name)):
            self.event.planning_people = [{"id": str(person.pk), "version": version, "name": name}]
            with self.subTest(person=person.pk, version=version), patch("apps.assistant.free_harness.run_free_harness") as remote:
                with self.assertRaises(provider.ProviderError):
                    self.freeze()
                remote.assert_not_called()

    def test_free_speaker_candidates_include_only_current_owned_synthetic_records(self):
        cancelled = self.person("Ponente ficticio cancelado", synthetic=True)
        for person in (self.fake, self.real, self.foreign, cancelled):
            EventPerson.objects.create(event=self.event, person=person, role="speaker",
                                       status="cancelled" if person == cancelled else "planned")
        frozen = self.freeze()
        candidates = frozen["context"]["context"]["speaker_candidates"]
        self.assertEqual([person["name"] for person in candidates], [self.fake.full_name])
        serialized = json.dumps(frozen, ensure_ascii=False)
        for private in (self.real.full_name, self.real_org.name, self.foreign.full_name, cancelled.full_name, self.fake.email):
            self.assertNotIn(private, serialized)

    def test_free_request_uses_the_same_frozen_speakers_without_orm_reads(self):
        EventPerson.objects.create(event=self.event, person=self.fake, role="speaker")
        frozen = self.freeze()
        expected = deepcopy(frozen["context"])
        with provider.use_profile(self.profile):
            bound = provider.ensure_input_fits(event=self.event, kind="plan", prompt=frozen["prompt"], snapshot=self.profile)
            self.assertGreater(bound, provider.INPUT_OVERHEAD_TOKENS)
        Person.objects.filter(pk=self.fake.pk).update(full_name="Nuevo nombre real que no debe consultarse", is_synthetic=False)
        with provider.use_profile(self.profile), patch("apps.assistant.free_harness.run_free_harness") as remote:
            remote.return_value = {"payload": {"result": "candidate"}, "usage": {}}
            with self.assertNumQueries(0):
                self.assertEqual(provider.generate_plan(event=self.event, prompt=frozen["prompt"]), {"result": "candidate"})
        self.assertEqual(remote.call_args.kwargs["context"], expected)
        self.assertIn(self.fake.full_name, json.dumps(remote.call_args.kwargs["context"], ensure_ascii=False))
        self.assertNotIn("Nuevo nombre real", json.dumps(remote.call_args.kwargs["context"], ensure_ascii=False))

    def test_free_preflight_measures_candidates_and_exact_instructions(self):
        EventPerson.objects.create(event=self.event, person=self.fake, role="speaker")
        frozen = self.freeze()
        bound = provider.ensure_input_fits(event=self.event, kind="plan", prompt=frozen["prompt"], snapshot=self.profile)
        limited = {**self.profile, "max_input_tokens": bound - 1}
        with patch("apps.assistant.free_harness.run_free_harness") as remote:
            with self.assertRaises(provider.ProviderError):
                provider.ensure_input_fits(event=self.event, kind="plan", prompt=frozen["prompt"], snapshot=limited)
            remote.assert_not_called()

    def test_missing_or_different_snapshot_never_invokes_free_harness(self):
        with provider.use_profile(self.profile), patch("apps.assistant.free_harness.run_free_harness") as remote:
            with self.assertRaises(provider.ProviderError):
                provider.generate_plan(event=self.event, prompt="Sin instantánea")
            self.freeze()
            with self.assertRaises(provider.ProviderError):
                provider.answer_question(event=self.event, prompt="Otro contenido")
            remote.assert_not_called()

    def test_free_context_is_detached_from_mutable_conversation(self):
        original = {"context": provider._context(self.event), "history": [{"role": "assistant", "content": "Dato local privado"}]}
        frozen = self.freeze(action="chat", conversation=original)
        original["context"]["event"]["brief"] = "Cambio después de preparar"
        self.assertEqual(frozen["context"]["context"]["event"]["brief"], "Demostración ficticia")
        self.assertNotIn("Dato local privado", json.dumps(frozen, ensure_ascii=False))
