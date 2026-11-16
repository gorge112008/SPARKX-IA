"""Pure contract/scheduling tests; no database, API or availability inference."""

from copy import deepcopy
import json
import unittest
from unittest.mock import patch

from .constraints import MAX_BUSY, MAX_SEARCH_STEPS, normalize_constraints, repair_plan, validate_event_plan


def instant(clock):
    return f"2026-11-15T{clock}:00-05:00"


def interval(start="09:00", end="12:00"):
    return {"start": instant(start), "end": instant(end)}


def constraints():
    return {
        "version": 1,
        "window": interval(),
        "max_duration_minutes": 60,
        "speakers": [
            {"name": "Ana Pérez", "windows": [interval()], "busy": []},
            {"name": "Bea Ruiz", "windows": [interval()], "busy": []},
        ],
        "resources": [{"name": "Sala declarada", "windows": [interval()], "busy": []}],
        "sessions": [
            {"session_id": "s1", "allowed_speakers": ["Ana Pérez", "Bea Ruiz"], "allowed_resources": ["Sala declarada"]},
            {"session_id": "s2", "allowed_speakers": ["Ana Pérez", "Bea Ruiz"], "allowed_resources": ["Sala declarada"]},
        ],
        "fixed": [],
    }


def plan():
    return {
        "title": "Ejemplo declarado", "summary": "Propuesta pendiente de revisión.",
        "sessions": [
            {"id": "s1", "title": "Apertura", "start": instant("09:00"), "duration_minutes": 30, "speaker": "Ana Pérez", "resource": "Sala declarada"},
            {"id": "s2", "title": "Preguntas", "start": instant("09:30"), "duration_minutes": 30, "speaker": "Bea Ruiz", "resource": "Sala declarada"},
        ],
        "tasks": [
            {"id": "t1", "title": "Preparar contenido", "depends_on": [], "status": "pending", "purpose": "Preparación pendiente."},
            {"id": "t2", "title": "Revisar contenido", "depends_on": ["t1"], "status": "pending", "purpose": "Revisión humana pendiente."},
        ],
        "risks": ["Las declaraciones no prueban asistencia confirmada."],
    }


class ConstraintContractTests(unittest.TestCase):
    def test_legacy_empty_constraints_use_existing_validation(self):
        self.assertEqual(normalize_constraints({}), {})
        self.assertEqual(validate_event_plan(plan(), {}), [])
        invalid = plan()
        invalid["tasks"][0]["status"] = "completed"
        self.assertTrue(validate_event_plan(invalid, {}))
        self.assertEqual(repair_plan(invalid, {})["status"], "blocked")

    def test_canonicalization_is_detached_idempotent_and_preserves_identity(self):
        raw = constraints()
        raw["speakers"][0]["name"] = "  Ana   Pe\u0301rez  "
        raw["sessions"][0]["allowed_speakers"][0] = "ANA PÉREZ"
        before = deepcopy(raw)
        canonical = normalize_constraints(raw)
        self.assertEqual(raw, before)
        self.assertEqual(canonical, normalize_constraints(canonical))
        self.assertEqual(canonical["speakers"][0]["name"], "Ana Pérez")
        canonical["speakers"][0]["busy"].append(interval())
        self.assertEqual(raw, before)

    def test_homonyms_and_normalized_duplicates_are_rejected_without_merging(self):
        for name in ("ANA   PÉREZ", "Ana Pe\u0301rez"):
            raw = constraints()
            raw["speakers"].append({"name": name, "windows": [], "busy": []})
            with self.subTest(name=name), self.assertRaisesRegex(ValueError, "ambiguo"):
                normalize_constraints(raw)

    def test_accented_and_unaccented_names_are_distinct(self):
        raw = constraints()
        raw["speakers"].append({"name": "Ana Perez", "windows": [], "busy": []})
        self.assertEqual(len(normalize_constraints(raw)["speakers"]), 3)

    def test_unknown_fields_and_untrusted_types_are_rejected(self):
        mutations = [None, [], {**constraints(), "approved": True}, {**constraints(), "version": True}]
        for raw in mutations:
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                normalize_constraints(raw)
            self.assertTrue(validate_event_plan(plan(), raw))
            self.assertEqual(repair_plan(plan(), raw)["status"], "blocked")
        raw = constraints()
        raw["speakers"][0]["confirmed"] = True
        with self.assertRaises(ValueError):
            normalize_constraints(raw)

    def test_naive_reversed_and_oversized_windows_are_rejected(self):
        for window in (
            {"start": "2026-11-15T09:00:00", "end": instant("12:00")},
            interval("12:00", "09:00"),
            {"start": instant("09:00"), "end": "2026-11-16T09:15:00-05:00"},
        ):
            raw = constraints()
            raw["window"] = window
            with self.subTest(window=window), self.assertRaises(ValueError):
                normalize_constraints(raw)

    def test_catalog_and_reservation_limits_block_instead_of_truncating(self):
        for field, value in (
            ("speakers", [{"name": str(index), "windows": [], "busy": []} for index in range(4)]),
            ("sessions", [{"session_id": str(index), "allowed_speakers": [], "allowed_resources": []} for index in range(13)]),
        ):
            raw = constraints()
            raw[field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                normalize_constraints(raw)
        raw = constraints()
        raw["speakers"][0]["busy"] = [interval()] * (MAX_BUSY + 1)
        with self.assertRaisesRegex(ValueError, str(MAX_BUSY)):
            normalize_constraints(raw)

    def test_allowed_names_and_fixed_session_ids_must_be_authorized(self):
        for field, value in (
            ("sessions", [{"session_id": "s1", "allowed_speakers": ["Desconocido"], "allowed_resources": []}]),
            ("fixed", [{"session_id": "ajena", "speaker": "Ana Pérez"}]),
            ("fixed", [{"session_id": "s1", "speaker": "Desconocido"}]),
            ("fixed", [{"session_id": "s1"}]),
        ):
            raw = constraints()
            raw[field] = value
            with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                normalize_constraints(raw)

    def test_duration_bool_and_unknown_lock_fields_are_rejected(self):
        raw = constraints()
        raw["max_duration_minutes"] = True
        with self.assertRaises(ValueError):
            normalize_constraints(raw)
        raw = constraints()
        raw["fixed"] = [{"session_id": "s1", "duration_minutes": True}]
        with self.assertRaises(ValueError):
            normalize_constraints(raw)
        raw["fixed"] = [{"session_id": "s1", "confirmed_by": "AI"}]
        with self.assertRaises(ValueError):
            normalize_constraints(raw)


class EventConstraintValidationTests(unittest.TestCase):
    def test_valid_and_equivalent_timezone_start_are_accepted(self):
        self.assertEqual(validate_event_plan(plan(), constraints()), [])
        proposed = plan()
        proposed["sessions"][0]["start"] = "2026-11-15T14:00:00+00:00"
        self.assertEqual(validate_event_plan(proposed, constraints()), [])

    def test_grid_uses_event_window_offset_and_checks_seconds(self):
        for start in (instant("09:01"), "2026-11-15T09:00:01-05:00", "2026-11-15T14:05:00+00:00"):
            proposed = plan()
            proposed["sessions"][0]["start"] = start
            with self.subTest(start=start):
                self.assertTrue(any("cuadrícula" in error for error in validate_event_plan(proposed, constraints())))

    def test_outside_window_excess_duration_and_changed_ids_are_invalid(self):
        for field, value, expected in (("start", instant("08:30"), "ventana"), ("duration_minutes", 61, "duración"), ("id", "inventada", "identificadores")):
            proposed = plan()
            proposed["sessions"][0][field] = value
            if field == "duration_minutes":
                proposed["sessions"][1]["start"] = instant("11:00")
            with self.subTest(field=field):
                self.assertTrue(any(expected in error for error in validate_event_plan(proposed, constraints())))

    def test_unavailable_unknown_or_reserved_speaker_is_invalid(self):
        raw = constraints()
        raw["speakers"][0]["windows"] = []
        self.assertTrue(any("disponibilidad" in error for error in validate_event_plan(plan(), raw)))
        raw = constraints()
        raw["speakers"][0]["busy"] = [interval("09:15", "09:30")]
        self.assertTrue(any("reserva" in error for error in validate_event_plan(plan(), raw)))
        proposed = plan()
        proposed["sessions"][0]["speaker"] = "Persona inventada"
        self.assertTrue(any("habilitada" in error for error in validate_event_plan(proposed, constraints())))

    def test_resource_availability_and_reservations_are_constraints(self):
        raw = constraints()
        raw["resources"][0]["busy"] = [interval("09:00", "09:30")]
        self.assertTrue(any("recurso" in error and "reserva" in error for error in validate_event_plan(plan(), raw)))
        raw["resources"][0]["busy"] = []
        raw["resources"][0]["windows"] = []
        self.assertTrue(any("recurso" in error and "disponibilidad" in error for error in validate_event_plan(plan(), raw)))

    def test_touching_busy_endpoints_do_not_overlap(self):
        raw = constraints()
        raw["speakers"][0]["busy"] = [interval("08:30", "09:00"), interval("09:30", "10:00")]
        self.assertEqual(validate_event_plan(plan(), raw), [])

    def test_all_fixed_fields_are_checked_using_instants_and_normalized_names(self):
        raw = constraints()
        raw["fixed"] = [{"session_id": "s1", "start": "2026-11-15T14:00:00Z", "speaker": "  ANA PÉREZ ", "resource": "Sala declarada", "duration_minutes": 30}]
        self.assertEqual(validate_event_plan(plan(), raw), [])
        for field, value in (("start", instant("10:00")), ("speaker", "Bea Ruiz"), ("resource", ""), ("duration_minutes", 15)):
            proposed = plan()
            proposed["sessions"][0][field] = value
            with self.subTest(field=field):
                self.assertTrue(any("fijad" in error for error in validate_event_plan(proposed, raw)))

    def test_empty_allowed_assignments_require_blank_without_inventing_catalog(self):
        raw, proposed = constraints(), plan()
        raw["speakers"] = []
        raw["resources"] = []
        for spec, session in zip(raw["sessions"], proposed["sessions"]):
            spec.update(allowed_speakers=[], allowed_resources=[])
            session.update(speaker="", resource="")
        self.assertEqual(validate_event_plan(proposed, raw), [])
        proposed["sessions"][0]["resource"] = "Sala ficticia"
        self.assertTrue(validate_event_plan(proposed, raw))

    def test_unicode_equivalent_assignments_cannot_evade_overlap(self):
        proposed, raw = plan(), constraints()
        proposed["sessions"][0]["resource"] = ""
        proposed["sessions"][1].update(start=instant("09:00"), speaker="Ana Pe\u0301rez", resource="")
        for spec in raw["sessions"]:
            spec["allowed_resources"] = []
        self.assertTrue(any("solapan" in error for error in validate_event_plan(proposed, raw)))

    def test_bad_plan_types_and_space_dates_do_not_raise(self):
        for proposed in (None, [], {**plan(), "sessions": [None]}, {**plan(), "tasks": [None]}):
            with self.subTest(proposed=proposed):
                self.assertTrue(validate_event_plan(proposed, constraints()))
                self.assertEqual(repair_plan(proposed, constraints())["status"], "blocked")
        proposed = plan()
        proposed["sessions"][0]["start"] = "2026-11-15 09:00:00-05:00"
        self.assertTrue(validate_event_plan(proposed, constraints()))


class DeterministicRepairTests(unittest.TestCase):
    def assert_candidate(self, result, raw):
        self.assertEqual(result["status"], "candidate", result)
        self.assertEqual(validate_event_plan(result["payload"], raw), [])
        self.assertEqual(result["errors"], [])
        self.assertEqual(result["options"], [])
        self.assertLessEqual(result["steps"], MAX_SEARCH_STEPS)
        json.dumps(result, ensure_ascii=False, allow_nan=False)
        return result["payload"]

    def test_valid_proposal_is_copied_without_changes_or_search(self):
        proposed = plan()
        result = repair_plan(proposed, constraints())
        self.assertEqual(self.assert_candidate(result, constraints()), proposed)
        self.assertEqual(result["steps"], 0)
        self.assertIsNot(result["payload"], proposed)

    def test_substitutes_allowed_speaker_before_changing_any_start(self):
        raw, proposed = constraints(), plan()
        raw["speakers"][0]["busy"] = [interval("09:00", "09:30")]
        before_constraints, before_payload = deepcopy(raw), deepcopy(proposed)
        result = repair_plan(proposed, raw)
        candidate = self.assert_candidate(result, raw)
        self.assertEqual(candidate["sessions"][0]["speaker"], "Bea Ruiz")
        self.assertEqual([item["start"] for item in candidate["sessions"]], [item["start"] for item in proposed["sessions"]])
        self.assertEqual(raw, before_constraints)
        self.assertEqual(proposed, before_payload)
        self.assertEqual(result, repair_plan(proposed, raw))

    def test_moves_start_when_all_declared_speakers_are_busy(self):
        raw, proposed = constraints(), plan()
        for person in raw["speakers"]:
            person["busy"] = [interval("09:00", "10:00")]
        candidate = self.assert_candidate(repair_plan(proposed, raw), raw)
        self.assertEqual(candidate["sessions"][0]["start"], instant("10:00"))
        self.assertEqual(candidate["sessions"][1]["start"], instant("10:30"))
        for field in ("title", "summary", "tasks", "risks"):
            self.assertEqual(candidate[field], proposed[field])
        for before, after in zip(proposed["sessions"], candidate["sessions"]):
            for field in ("id", "title", "duration_minutes"):
                self.assertEqual(before[field], after[field])

    def test_repairs_internal_collisions_without_changing_fixed_decisions(self):
        raw, proposed = constraints(), plan()
        raw["fixed"] = [{"session_id": "s1", "start": instant("09:00"), "speaker": "Ana Pérez", "resource": "Sala declarada", "duration_minutes": 30}]
        proposed["sessions"][1]["start"] = instant("09:00")
        candidate = self.assert_candidate(repair_plan(proposed, raw), raw)
        self.assertEqual(candidate["sessions"][0], proposed["sessions"][0])
        self.assertEqual(candidate["sessions"][1]["start"], instant("09:30"))

    def test_restores_fixed_duration_and_assignment_instead_of_accepting_ai_change(self):
        raw, proposed = constraints(), plan()
        raw["fixed"] = [{"session_id": "s1", "duration_minutes": 30, "speaker": "Ana Pérez"}]
        proposed["sessions"][0].update(duration_minutes=15, speaker="Bea Ruiz")
        candidate = self.assert_candidate(repair_plan(proposed, raw), raw)
        self.assertEqual(candidate["sessions"][0]["duration_minutes"], 30)
        self.assertEqual(candidate["sessions"][0]["speaker"], "Ana Pérez")

    def test_does_not_shorten_unfixed_duration_to_force_feasibility(self):
        raw, proposed = constraints(), plan()
        raw["max_duration_minutes"] = 15
        result = repair_plan(proposed, raw)
        self.assertEqual(result["status"], "blocked")
        self.assertIsNone(result["payload"])

    def test_unavailable_fixed_speaker_blocks_with_unconfirmed_options(self):
        raw, proposed = constraints(), plan()
        raw["speakers"][0]["windows"] = []
        raw["fixed"] = [{"session_id": "s1", "speaker": "Ana Pérez", "start": instant("09:00")}]
        result = repair_plan(proposed, raw)
        self.assertEqual(result["status"], "blocked")
        self.assertIsNone(result["payload"])
        self.assertTrue(result["errors"])
        self.assertTrue(all(option["requires_confirmation"] is True for option in result["options"]))
        self.assertTrue(any("fijadas" in option["description"] for option in result["options"]))
        self.assertEqual(raw["fixed"][0]["speaker"], "Ana Pérez")

    def test_never_invents_availability_when_all_windows_are_empty(self):
        raw = constraints()
        for person in raw["speakers"]:
            person["windows"] = []
        result = repair_plan(plan(), raw)
        self.assertEqual(result["status"], "blocked")
        self.assertIsNone(result["payload"])

    def test_unknown_names_are_replaced_only_by_eligible_catalog_entries(self):
        raw, proposed = constraints(), plan()
        proposed["sessions"][0].update(speaker="Persona inventada", resource="Sala inventada")
        candidate = self.assert_candidate(repair_plan(proposed, raw), raw)
        self.assertIn(candidate["sessions"][0]["speaker"], raw["sessions"][0]["allowed_speakers"])
        self.assertEqual(candidate["sessions"][0]["resource"], "Sala declarada")

    def test_malformed_content_and_cyclic_tasks_are_not_repaired_or_silently_removed(self):
        for mutate in (
            lambda proposed: proposed["tasks"][0].update(depends_on=["t2"]),
            lambda proposed: proposed["tasks"][0].update(status="completed"),
            lambda proposed: proposed["sessions"][0].update(approved=True),
            lambda proposed: proposed["sessions"][0].update(speaker={"identity": "inventada"}),
            lambda proposed: proposed["sessions"].pop(),
        ):
            proposed = plan()
            mutate(proposed)
            result = repair_plan(proposed, constraints())
            self.assertEqual(result["status"], "blocked")
            self.assertIsNone(result["payload"])

    def test_finite_budget_reports_unknown_feasibility_without_relaxing_constraints(self):
        raw, proposed = constraints(), plan()
        proposed["sessions"][1]["start"] = instant("09:00")
        with patch("apps.planning.constraints.MAX_SEARCH_STEPS", 1):
            result = repair_plan(proposed, raw)
        self.assertEqual(result["status"], "blocked")
        self.assertEqual(result["steps"], 1)
        self.assertIn("no se ha demostrado", result["reason"])
        self.assertIsNone(result["payload"])

    def test_rounds_up_an_off_grid_window_and_never_uses_seconds_as_slots(self):
        raw, proposed = constraints(), plan()
        raw["window"]["start"] = "2026-11-15T09:01:20-05:00"
        candidate = self.assert_candidate(repair_plan(proposed, raw), raw)
        self.assertEqual(candidate["sessions"][0]["start"], instant("09:15"))

    def test_replaces_invalid_date_only_with_an_authorized_grid_start(self):
        proposed = plan()
        proposed["sessions"][0]["start"] = "fecha no válida"
        self.assert_candidate(repair_plan(proposed, constraints()), constraints())

    def test_extreme_valid_window_without_grid_slots_blocks_without_overflow(self):
        raw, proposed = constraints(), plan()
        extreme = {"start": "9999-12-31T23:59:30+00:00", "end": "9999-12-31T23:59:59+00:00"}
        raw["window"] = extreme
        for person in raw["speakers"] + raw["resources"]:
            person["windows"] = [deepcopy(extreme)]
        result = repair_plan(proposed, raw)
        self.assertEqual(result["status"], "blocked")


if __name__ == "__main__":
    unittest.main()
