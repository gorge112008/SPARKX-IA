"""Local directory resolution and explicit registration within the 15-step draft."""
from uuid import uuid4

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.directory.models import DirectoryAudit, EventPerson, Organization, Person
from apps.directory.services import upsert_organization, upsert_person
from apps.events.models import Event
from apps.assistant.event_creation import creation_turn
from apps.assistant.models import EventCreationDraft


class CreationDirectoryTests(TestCase):
    def setUp(self):
        self.owner = get_user_model().objects.create_user(username="directory-creation-owner")
        self.other = get_user_model().objects.create_user(username="directory-creation-other")
        self.org = upsert_organization(actor=self.owner, name="Universidad Nacional del Callao - UNAC", aliases=["UNAC"])
        self.person = upsert_person(actor=self.owner, full_name="Dr. Robert Castillo Alva", category="speaker", aliases=["Robert"], organization_id=self.org.pk)
        self.state = creation_turn(self.owner, "crear evento", expected_revision=0, request_id=uuid4())
        self.answer("Tesis")

    def answer(self, text="", **kwargs):
        self.state = creation_turn(self.owner, text, draft_id=self.state["draft_id"],
            expected_revision=self.state["revision"], request_id=kwargs.pop("request_id", uuid4()), **kwargs)
        return self.state

    def resources(self):
        self.answer("UNAC")
        for value in ("Orientación de tesis", "pendiente", "sí", "50", "no", "Aprender", "Posgrado", "Virtual", "90", "pendiente"):
            self.answer(value)
        self.assertEqual(self.state["step_key"], "resources")

    def test_existing_sigla_resolves_without_registration(self):
        count = Organization.objects.count()
        self.answer("unac")
        self.assertEqual(self.state["fields"]["organization_id"], str(self.org.pk))
        self.assertEqual(Organization.objects.count(), count)
        self.assertEqual(self.state["step_key"], "brief")

    def test_missing_organization_needs_yes_and_replay_does_not_duplicate(self):
        self.answer("Instituto nuevo")
        self.assertIn("¿Quieres registrar", self.state["reply"])
        self.assertEqual(Organization.objects.count(), 1)
        self.assertNotIn("_directory_resolution", self.state["fields"])
        values = {"draft_id": self.state["draft_id"], "expected_revision": self.state["revision"], "request_id": uuid4()}
        first = creation_turn(self.owner, "sí", **values)
        self.assertEqual(first, creation_turn(self.owner, "sí", **values))
        self.assertEqual(Organization.objects.count(), 2)
        self.assertEqual(first["step_key"], "brief")
        self.assertEqual(Event.objects.count(), 0)

    def test_registration_rechecks_after_another_manual_registration(self):
        self.answer("Escuela nueva")
        registered = upsert_organization(actor=self.owner, name="Escuela nueva")
        self.answer("sí")
        self.assertEqual(Organization.objects.filter(owner=self.owner).count(), 2)
        self.assertEqual(self.state["fields"]["organization_id"], str(registered.pk))

    def test_ambiguous_person_uses_number_without_merging_homonyms(self):
        second = upsert_person(actor=self.owner, full_name="Robert alternativo", category="speaker", aliases=["Robert"])
        self.resources()
        self.answer("Robert")
        self.assertEqual(self.state["step_key"], "resources")
        self.assertIn("varias coincidencias", self.state["reply"])
        self.assertNotIn("directory_people", self.state["fields"])
        self.answer("1")
        self.assertIn(self.state["fields"]["directory_people"][0]["id"], [str(second.pk), str(self.person.pk)])
        self.assertEqual(Person.objects.filter(owner=self.owner).count(), 2)

    def test_no_skips_registration_and_foreign_name_is_not_disclosed(self):
        upsert_organization(actor=self.other, name="Privada ajena", aliases=["AJENA"])
        self.answer("AJENA")
        self.assertNotIn("Privada ajena", self.state["reply"])
        self.answer("no")
        self.assertIsNone(self.state["fields"]["organization_id"])
        self.assertEqual(Organization.objects.filter(owner=self.owner).count(), 1)

    def test_ambiguous_alias_requires_choice_not_first_match(self):
        second = upsert_organization(actor=self.owner, name="Instituto UNAC", aliases=["UNAC"])
        self.answer("UNAC")
        self.assertEqual(self.state["step_key"], "organization")
        self.assertIn("varias coincidencias", self.state["reply"])
        self.assertNotIn("organization_id", self.state["fields"])
        self.answer(second.name)
        self.assertEqual(self.state["fields"]["organization_id"], str(second.pk))

    def test_existing_speaker_link_only_at_final_event_confirmation(self):
        self.resources()
        self.answer("Robert")
        self.assertEqual(self.state["fields"]["directory_people"][0]["id"], str(self.person.pk))
        self.assertEqual(EventPerson.objects.count(), 0)
        self.answer("Sin restricciones")
        self.assertEqual(self.state["status"], "review")
        self.answer(operation="confirm")
        self.assertEqual(Event.objects.count(), 1)
        self.assertEqual(EventPerson.objects.get().person_id, self.person.pk)
        self.assertEqual(EventPerson.objects.get().status, "planned")

    def test_descriptive_resources_do_not_create_people(self):
        self.resources()
        count = Person.objects.count()
        self.answer("Tres expositores y un proyector por confirmar")
        self.assertEqual(self.state["step_key"], "constraints")
        self.assertEqual(Person.objects.count(), count)
        self.assertNotIn("directory_people", self.state["fields"])

    def test_missing_speaker_yes_creates_only_person_then_no_does_not(self):
        self.resources()
        self.answer("expositor: Ana Pérez")
        self.assertEqual(Person.objects.count(), 1)
        self.assertIn("¿Quieres registrar", self.state["reply"])
        self.answer("sí por favor")
        ana = Person.objects.get(full_name="Ana Pérez")
        self.assertEqual(ana.organization_id, self.org.pk)
        self.assertEqual(self.state["step_key"], "constraints")
        self.assertEqual(Event.objects.count(), 0)
        self.answer(operation="back")
        self.answer("invitado: Juan Ramírez")
        self.answer("no")
        self.assertEqual(Person.objects.count(), 2)
        self.assertEqual(self.state["fields"]["directory_people"], [])
        self.assertEqual(self.state["fields"]["interview_answers"]["resources"]["value"], "invitado: Juan Ramírez")

    def test_natural_singular_declarations_resolve_existing_speaker(self):
        self.resources()
        for phrase in ("expositor Robert", "el expositor será Robert", "un ponente se llama Robert", "la expositora es Robert"):
            with self.subTest(phrase=phrase):
                self.answer(phrase)
                self.assertEqual(self.state["step_key"], "constraints")
                self.assertEqual(self.state["fields"]["directory_people"][0]["id"], str(self.person.pk))
                self.answer(operation="back")
        self.assertEqual(Person.objects.count(), 1)

    def test_natural_unknown_guest_still_requires_yes_or_can_be_declined(self):
        self.resources()
        self.answer("una invitada se llama Ana Pérez")
        self.assertEqual(self.state["step_key"], "resources")
        self.assertIn("¿Quieres registrar", self.state["reply"])
        self.assertEqual(Person.objects.count(), 1)
        self.answer("no gracias")
        self.assertEqual(self.state["step_key"], "constraints")
        self.assertEqual(self.state["fields"]["directory_people"], [])
        self.assertEqual(Person.objects.count(), 1)

    def test_negated_reported_conditional_and_plural_resources_remain_literal(self):
        self.resources()
        for phrase in ("el expositor no será Juan Pérez", "el expositor dijo Juan Pérez", "el expositor fue Juan Pérez", 'el expositor es "Juan Pérez"',
                       "el expositor será Juan Pérez si confirma", "tres expositores ficticios", "no quiero un expositor Juan Pérez"):
            with self.subTest(phrase=phrase):
                self.answer(phrase)
                self.assertEqual(self.state["step_key"], "constraints")
                self.assertNotIn("¿Quieres registrar", self.state["reply"])
                self.assertEqual(Person.objects.count(), 1)
                self.assertNotIn("directory_people", self.state["fields"])
                self.answer(operation="back")

    def test_partial_single_suggestion_waits_for_explicit_yes(self):
        audit = DirectoryAudit.objects.count()
        self.answer("Callao")
        self.assertEqual(self.state["step_key"], "organization")
        self.assertNotIn("organization_id", self.state["fields"])
        self.assertEqual(self.state["directory_resolution"], {
            "kind": "organization", "mode": "choose", "query": "Callao",
            "candidates": [{"id": str(self.org.pk), "name": self.org.name}], "can_skip": True,
        })
        self.answer("bueno sí por favor usa esa institución")
        self.assertEqual(self.state["fields"]["organization_id"], str(self.org.pk))
        self.assertIsNone(self.state["directory_resolution"])
        self.assertEqual(DirectoryAudit.objects.count(), audit)

    def test_suggestion_terms_ignore_order_case_accents_and_connectors(self):
        self.answer("CALLÁO de NACIONAL")
        self.assertEqual(self.state["directory_resolution"]["mode"], "choose")
        self.assertEqual(self.state["directory_resolution"]["candidates"][0]["id"], str(self.org.pk))
        self.answer("1")
        self.assertEqual(self.state["fields"]["organization_id"], str(self.org.pk))

    def test_natural_wrapper_keeps_informative_search_tokens(self):
        self.answer("la institución es Callao")
        self.assertEqual(self.state["directory_resolution"]["mode"], "choose")
        self.assertEqual(self.state["directory_resolution"]["candidates"][0]["id"], str(self.org.pk))

    def test_all_search_terms_are_required(self):
        self.answer("Callao inexistente")
        self.assertEqual(self.state["directory_resolution"]["mode"], "register")
        self.assertEqual(self.state["directory_resolution"]["candidates"], [])

    def test_partial_multiple_candidates_are_bounded_and_yes_does_not_choose(self):
        for index in range(5):
            upsert_organization(actor=self.owner, name=f"Academia Callao {index}")
        self.answer("Callao")
        candidates = self.state["directory_resolution"]["candidates"]
        self.assertEqual(len(candidates), 3)
        self.answer("sí por favor")
        self.assertEqual(self.state["step_key"], "organization")
        self.assertNotIn("organization_id", self.state["fields"])
        self.answer("opción 2")
        self.assertEqual(self.state["fields"]["organization_id"], candidates[1]["id"])

    def test_registration_yes_and_no_are_independent_keywords_in_context(self):
        self.answer("Instituto nuevo")
        self.answer("bueno Gica sí por favor registra esa institución")
        self.assertEqual(self.state["fields"]["organization_name"], "Instituto nuevo")
        self.answer(operation="back")
        self.answer("Otra escuela inexistente")
        self.answer("mira Gica no deseo registrarla gracias")
        self.assertEqual(self.state["step_key"], "brief")
        self.assertIsNone(self.state["fields"]["organization_id"])
        self.assertFalse(Organization.objects.filter(name="Otra escuela inexistente").exists())

    def test_contradictory_uncertain_and_incomplete_confirmations_do_not_advance(self):
        self.answer("Instituto nuevo")
        for value in ("sí pero no", "no sí regístrala", "no sé", "no estoy seguro", "quizás sí", "todavía estoy pensando", "Universidad inventada"):
            with self.subTest(value=value):
                previous = EventCreationDraft.objects.get(pk=self.state["draft_id"]).data
                self.answer(value)
                self.assertEqual(self.state["step_key"], "organization")
                self.assertEqual(self.state["directory_resolution"]["query"], "Instituto nuevo")
                self.assertEqual(EventCreationDraft.objects.get(pk=self.state["draft_id"]).data, previous)
                self.assertEqual(Organization.objects.count(), 1)

    def test_yes_no_contradiction_cannot_select_a_single_suggestion(self):
        self.answer("Callao")
        self.answer("sí no")
        self.assertEqual(self.state["directory_resolution"]["mode"], "choose")
        self.assertNotIn("organization_id", self.state["fields"])

    def test_prompt_fragment_is_not_a_replacement_name_or_consent(self):
        self.answer("Instituto nuevo")
        for value in ("Para continuar sin hacerlo o indica otro nombre.", "Di sí para registrarla no para continuar", self.state["question"]):
            with self.subTest(value=value):
                self.answer(value)
                self.assertEqual(self.state["directory_resolution"]["query"], "Instituto nuevo")
                self.assertEqual(Organization.objects.count(), 1)
        self.answer("sí por favor")
        self.assertTrue(Organization.objects.filter(name="Instituto nuevo").exists())
        self.assertFalse(Organization.objects.filter(name__contains="continuar").exists())

    def test_explicit_other_name_is_a_separate_step_before_registration(self):
        self.answer("Callao")
        self.answer("quiero registrar otra")
        self.assertEqual(self.state["directory_resolution"]["mode"], "new_name")
        self.assertEqual(self.state["directory_resolution"]["query"], "")
        self.answer("Escuela Nueva")
        self.assertEqual(self.state["directory_resolution"]["mode"], "register")
        self.assertEqual(self.state["directory_resolution"]["query"], "Escuela Nueva")
        self.assertEqual(Organization.objects.count(), 1)
        self.answer("sí por favor")
        self.assertEqual(self.state["fields"]["organization_name"], "Escuela Nueva")

    def test_new_name_can_resolve_existing_exact_alias_without_duplicate(self):
        self.answer("Instituto nuevo")
        self.answer("otro nombre")
        self.answer("UNAC")
        self.assertEqual(self.state["fields"]["organization_id"], str(self.org.pk))
        self.assertEqual(Organization.objects.count(), 1)

    def test_proper_name_containing_no_is_preserved_outside_confirmation(self):
        self.answer("Instituto del No")
        self.assertEqual(self.state["directory_resolution"]["query"], "Instituto del No")
        self.answer("registrar otro")
        self.answer("Instituto del No")
        self.assertEqual(self.state["directory_resolution"]["query"], "Instituto del No")
        self.answer("sí")
        self.assertEqual(self.state["fields"]["organization_name"], "Instituto del No")

    def test_standalone_yes_without_confirmation_asks_for_name(self):
        self.answer("sí")
        self.assertEqual(self.state["directory_resolution"]["mode"], "new_name")
        self.assertEqual(Organization.objects.count(), 1)
        self.answer("UNAC")
        self.assertEqual(self.state["fields"]["organization_id"], str(self.org.pk))

    def test_standalone_no_without_confirmation_skips_organization(self):
        self.answer("no")
        self.assertEqual(self.state["step_key"], "brief")
        self.assertIsNone(self.state["fields"]["organization_id"])
        self.assertFalse(Organization.objects.filter(name="no").exists())

    def test_courteous_yes_without_pending_resolution_is_not_a_name(self):
        self.answer("bueno sí claro por favor")
        self.assertEqual(self.state["directory_resolution"]["mode"], "new_name")
        self.assertEqual(Organization.objects.count(), 1)

    def test_courteous_no_without_pending_resolution_skips_without_a_name(self):
        self.answer("no muchas gracias")
        self.assertEqual(self.state["step_key"], "brief")
        self.assertIsNone(self.state["fields"]["organization_id"])
        self.assertEqual(Organization.objects.count(), 1)

    def test_courteous_yes_while_asking_name_stays_on_the_name_question(self):
        self.answer("Instituto nuevo")
        self.answer("registrar otro")
        self.answer("bueno sí claro por favor")
        self.assertEqual(self.state["directory_resolution"]["mode"], "new_name")
        self.assertEqual(self.state["directory_resolution"]["query"], "")
        self.assertEqual(Organization.objects.count(), 1)

    def test_courteous_no_while_asking_name_skips_without_registering(self):
        self.answer("Instituto nuevo")
        self.answer("registrar otro")
        self.answer("no muchas gracias")
        self.assertEqual(self.state["step_key"], "brief")
        self.assertIsNone(self.state["fields"]["organization_id"])
        self.assertEqual(Organization.objects.count(), 1)

    def test_positive_im_sure_registers_but_negative_im_not_sure_waits(self):
        self.answer("Instituto nuevo")
        self.answer("no estoy seguro")
        self.assertEqual(self.state["directory_resolution"]["mode"], "register")
        self.assertEqual(Organization.objects.count(), 1)
        self.answer("sí estoy seguro")
        self.assertEqual(self.state["fields"]["organization_name"], "Instituto nuevo")

    def test_no_or_contradiction_does_not_authorize_register_another(self):
        self.answer("Instituto nuevo")
        self.answer("sí no registrar otro")
        self.assertEqual(self.state["directory_resolution"]["mode"], "register")
        self.answer("no quiero registrar otra")
        self.assertEqual(self.state["step_key"], "brief")
        self.assertIsNone(self.state["fields"]["organization_id"])
        self.assertEqual(Organization.objects.count(), 1)

    def test_foreign_and_inactive_suggestions_are_not_exposed(self):
        foreign = upsert_organization(actor=self.other, name="Centro secreto Callao")
        inactive = upsert_organization(actor=self.owner, name="Centro antiguo Callao")
        Organization.objects.filter(pk=inactive.pk).update(is_active=False)
        self.answer("Callao")
        candidates = self.state["directory_resolution"]["candidates"]
        self.assertEqual([item["id"] for item in candidates], [str(self.org.pk)])
        self.assertNotIn(foreign.name, str(self.state))
        self.assertNotIn(inactive.name, str(self.state))

    def test_candidate_archived_or_renamed_before_click_needs_a_new_name(self):
        self.answer("Callao")
        Organization.objects.filter(pk=self.org.pk).update(is_active=False)
        self.answer("1")
        self.assertEqual(self.state["directory_resolution"]["mode"], "new_name")
        self.assertNotIn("organization_id", self.state["fields"])
        self.assertEqual(Organization.objects.count(), 1)

    def test_foreign_candidate_id_in_old_private_state_is_not_disclosed_or_linked(self):
        foreign = upsert_organization(actor=self.other, name="Centro secreto Callao")
        self.answer("Callao")
        draft = EventCreationDraft.objects.get(pk=self.state["draft_id"])
        draft.data["_directory_resolution"]["candidates"] = [{"id": str(foreign.pk), "name": foreign.name}]
        draft.save(update_fields=["data"])
        self.answer(operation="resume")
        self.assertEqual(self.state["directory_resolution"]["mode"], "new_name")
        self.assertNotIn(foreign.name, str(self.state))
        self.answer("sí")
        self.assertNotIn("organization_id", self.state["fields"])

    def test_historical_prompt_as_name_recovers_on_resume_without_registration(self):
        self.answer("Instituto nuevo")
        draft = EventCreationDraft.objects.get(pk=self.state["draft_id"])
        draft.data["_directory_resolution"]["name"] = "Para continuar sin hacerlo o indica otro nombre."
        draft.save(update_fields=["data"])
        previous_revision = draft.revision
        self.answer(operation="resume")
        self.assertEqual(self.state["revision"], previous_revision + 1)
        self.assertEqual(self.state["directory_resolution"]["mode"], "new_name")
        self.assertEqual(self.state["directory_resolution"]["query"], "")
        self.assertNotIn("continuar sin hacerlo", self.state["question"])
        self.assertEqual(Organization.objects.count(), 1)
        self.answer("UNAC")
        self.assertEqual(self.state["fields"]["organization_id"], str(self.org.pk))

    def test_historical_prompt_as_name_cannot_be_registered_by_yes(self):
        self.answer("Instituto nuevo")
        draft = EventCreationDraft.objects.get(pk=self.state["draft_id"])
        draft.data["_directory_resolution"]["name"] = "Para continuar sin hacerlo o indica otro nombre."
        draft.save(update_fields=["data"])
        self.answer("sí por favor")
        self.assertEqual(self.state["directory_resolution"]["mode"], "new_name")
        self.assertEqual(Organization.objects.count(), 1)

    def test_stale_tab_and_request_replay_do_not_duplicate_registration(self):
        self.answer("Instituto nuevo")
        old = dict(self.state)
        token = uuid4()
        first = self.answer("sí por favor", request_id=token)
        replay = creation_turn(self.owner, "sí por favor", draft_id=old["draft_id"], expected_revision=old["revision"], request_id=token)
        self.assertEqual(first, replay)
        stale = creation_turn(self.owner, "sí por favor", draft_id=old["draft_id"], expected_revision=old["revision"], request_id=uuid4())
        self.assertEqual(stale["error_code"], "stale_revision")
        self.assertEqual(Organization.objects.count(), 2)

    def test_new_partial_match_from_another_tab_is_offered_before_registering(self):
        self.answer("Salamanca")
        registered = upsert_organization(actor=self.owner, name="Universidad de Salamanca")
        self.answer("sí por favor")
        self.assertEqual(self.state["directory_resolution"]["mode"], "choose")
        self.assertNotIn("organization_id", self.state["fields"])
        self.assertEqual(Organization.objects.count(), 2)
        self.answer("1")
        self.assertEqual(self.state["fields"]["organization_id"], str(registered.pk))

    def test_partial_person_suggestion_and_other_name_registration(self):
        self.resources()
        self.answer("Castillo")
        self.assertEqual(self.state["directory_resolution"]["kind"], "person")
        self.assertEqual(self.state["directory_resolution"]["mode"], "choose")
        self.assertEqual(self.state["directory_resolution"]["candidates"][0]["id"], str(self.person.pk))
        self.answer("registrar otro")
        self.answer("Ana Pérez")
        self.assertEqual(self.state["directory_resolution"]["mode"], "register")
        self.answer("bueno sí por favor registra esa persona")
        self.assertEqual(self.state["fields"]["directory_people"][0]["name"], "Ana Pérez")
        self.assertEqual(self.state["step_key"], "constraints")
        self.assertEqual(EventPerson.objects.count(), 0)

    def test_directory_questions_are_short_and_private_resolution_stays_private(self):
        self.answer("Instituto nuevo")
        self.assertLessEqual(len(self.state["question"]), 160)
        self.assertNotIn("_directory_resolution", self.state["fields"])
        self.assertEqual(set(self.state["directory_resolution"]), {"kind", "mode", "query", "candidates", "can_skip"})
        self.answer("registrar otro")
        self.assertLessEqual(len(self.state["question"]), 160)
