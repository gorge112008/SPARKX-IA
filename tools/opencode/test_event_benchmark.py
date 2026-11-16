"""Reference cases and hostile/incorrect proposals, without model calls."""
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tools.opencode import event_benchmark as bench
from tools.opencode import runner


def reference_answer(case):
    answer = {"event_id": case["id"], "institution": case["institution"], "title": case["title"]}
    for phase in ("baseline", "changed"):
        choices = bench.solutions(case, phase)
        answer[phase] = {"status": "scheduled" if choices else "blocked", "sessions": choices[0] if choices else [],
                         "reason": "Referencia determinista ficticia.", "options": [] if choices else [
                             {"description": "Solicitar nueva disponibilidad y aprobación del organizador.", "requires_confirmation": True}]}
    return answer


class SyntheticWeekTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cases = bench.make_cases()

    def test_exactly_six_events_five_unac_one_gica_with_only_requested_duplicate_title(self):
        self.assertEqual(len(self.cases), 6)
        self.assertEqual([c["institution"] for c in self.cases], ["UNAC"] * 5 + ["GICA"])
        self.assertEqual(len({c["title"] for c in self.cases}), 5)
        self.assertEqual(self.cases[0]["title"], self.cases[5]["title"])
        self.assertEqual([c["day"] for c in self.cases], list(bench.DAYS))
        self.assertEqual(len({c["date"] for c in self.cases}), 6)

    def test_randomization_is_reproducible_and_different_seed_changes_agendas(self):
        self.assertEqual(self.cases, bench.make_cases(bench.SEED))
        self.assertNotEqual(self.cases, bench.make_cases(bench.SEED + 1))

    def test_three_shared_speakers_and_all_baseline_agendas_feasible(self):
        self.assertEqual(set(bench.SPEAKERS), {"P1", "P2", "P3"})
        for case in self.cases:
            with self.subTest(case=case["id"]):
                self.assertEqual(set(case["baseline"]["availability"]), set(bench.SPEAKERS))
                self.assertEqual(bench.schedule_errors(case, "baseline", case["preferred"]), [])
                self.assertTrue(bench.solutions(case, "baseline"))

    def test_changed_cases_have_expected_feasibility_and_valid_reference_answers(self):
        expected = [True, True, True, False, False, True]
        for case, possible in zip(self.cases, expected):
            with self.subTest(case=case["id"]):
                self.assertEqual(bool(bench.solutions(case, "changed")), possible)
                self.assertTrue(bench.evaluate(case, reference_answer(case))["passed"])

    def test_shift_case_has_no_solution_at_old_start_and_combined_case_requires_substitute(self):
        for index in (2, 5):
            case = self.cases[index]
            choices = bench.solutions(case, "changed")
            self.assertTrue(all(bench.instant(a[0]["start"]) >= bench.instant(case["window"]["start"]) + bench.timedelta(minutes=30) for a in choices))
        self.assertTrue(all(a[0]["speaker_id"] != self.cases[5]["preferred"][0]["speaker_id"]
                            for a in bench.solutions(self.cases[5], "changed")))

    def test_locked_case_is_infeasible_even_though_releasing_lock_would_offer_options(self):
        case = deepcopy(self.cases[4])
        self.assertEqual(bench.solutions(case, "changed"), [])
        case["changed"]["locks"] = []
        self.assertTrue(bench.solutions(case, "changed"))

    def test_lock_compares_instants_not_equivalent_iso_string_format(self):
        case = self.cases[4]
        agenda = deepcopy(case["preferred"])
        for item in agenda:
            item["start"] = bench.instant(item["start"]).isoformat(timespec="seconds")
        self.assertEqual(bench.schedule_errors(case, "baseline", agenda), [])

    def test_shared_calendar_accepts_six_independent_days_and_two_honest_blocks(self):
        answers = {case["id"]: reference_answer(case) for case in self.cases}
        baseline = bench.check_shared_calendar(answers, "baseline")
        changed = bench.check_shared_calendar(answers, "changed")
        self.assertTrue(baseline["passed"])
        self.assertEqual(baseline["scheduled_events"], 6)
        self.assertTrue(changed["passed"])
        self.assertEqual(changed["scheduled_events"], 4)
        self.assertEqual(changed["blocked_events"], 2)

    def test_shared_calendar_never_confirms_a_missing_or_wrong_brand_event(self):
        answers = {case["id"]: reference_answer(case) for case in self.cases}
        answers.pop("E06")
        self.assertFalse(bench.check_shared_calendar(answers, "baseline")["passed"])
        answers["E06"] = reference_answer(self.cases[5])
        answers["E06"]["institution"] = "UNAC"
        self.assertFalse(bench.check_shared_calendar(answers, "baseline")["passed"])


class AnswerRejectionTests(unittest.TestCase):
    def setUp(self):
        self.case = bench.make_cases()[0]
        self.answer = reference_answer(self.case)

    def test_invented_speaker_timezone_duration_schema_or_missing_session_fails(self):
        for field, value in (("speaker_id", "invented"), ("start", "2026-11-16T19:00"),
                             ("start", "2026-11-16T19:00+00:00"), ("id", []), ("speaker_id", {})):
            with self.subTest(field=field, value=value):
                answer = deepcopy(self.answer)
                answer["baseline"]["sessions"][0][field] = value
                self.assertFalse(bench.evaluate(self.case, answer)["passed"])
        answer = deepcopy(self.answer)
        answer["baseline"]["sessions"][0]["duration_minutes"] = 10
        self.assertFalse(bench.evaluate(self.case, answer)["passed"])
        answer = deepcopy(self.answer)
        answer["baseline"]["sessions"].pop()
        self.assertFalse(bench.evaluate(self.case, answer)["passed"])

    def test_wrong_brand_title_event_or_false_block_cannot_pass(self):
        for field in ("event_id", "institution", "title"):
            with self.subTest(field=field):
                answer = deepcopy(self.answer)
                answer[field] = "otra cosa"
                self.assertFalse(bench.evaluate(self.case, answer)["passed"])
        answer = deepcopy(self.answer)
        answer["changed"] = {"status": "blocked", "sessions": [], "reason": "No busqué opciones.",
                             "options": [{"description": "Moverlo.", "requires_confirmation": True}]}
        self.assertFalse(bench.evaluate(self.case, answer)["passed"])

    def test_no_space_must_not_invent_an_agenda_or_confirm_an_unapproved_option(self):
        case = bench.make_cases()[3]
        answer = reference_answer(case)
        answer["changed"]["sessions"] = deepcopy(case["preferred"])
        answer["changed"]["status"] = "scheduled"
        self.assertFalse(bench.evaluate(case, answer)["passed"])
        answer = reference_answer(case)
        answer["changed"]["options"][0]["requires_confirmation"] = False
        self.assertFalse(bench.evaluate(case, answer)["passed"])

    def test_exact_boundaries_are_allowed_but_booking_overlap_is_rejected(self):
        case = deepcopy(self.case)
        session = case["preferred"][0]
        end = bench.instant(session["start"]) + bench.timedelta(minutes=30)
        case["baseline"]["bookings"].append({"speaker_id": session["speaker_id"],
            "start": end.isoformat(), "end": (end + bench.timedelta(minutes=30)).isoformat()})
        self.assertEqual(bench.schedule_errors(case, "baseline", case["preferred"]), [])
        case["baseline"]["bookings"][-1]["start"] = (end - bench.timedelta(minutes=1)).isoformat()
        self.assertTrue(bench.schedule_errors(case, "baseline", case["preferred"]))

    def test_parser_accepts_one_json_object_and_rejects_duplicates_multiple_objects_and_absence(self):
        encoded = json.dumps(self.answer)
        self.assertEqual(bench.parse_answer("```json\n" + encoded + "\n```"), self.answer)
        self.assertEqual(bench.parse_answer("Respuesta:\n" + encoded), self.answer)
        for value in ('{"a":1,"a":2}', '{"a":1}\n{"b":2}', "No hay JSON"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                bench.parse_answer(value)


class BrokerPreparationTests(unittest.TestCase):
    def test_synthetic_case_is_copied_with_hash_without_reference_answer_or_inference(self):
        temporal = runner.PROJECT_ROOT / "Temporal"
        with tempfile.TemporaryDirectory(prefix="benchmark-unit-", dir=temporal) as location:
            base = Path(location).resolve()
            self.assertTrue(base.is_relative_to(temporal.resolve()))
            with patch.object(runner, "TASK_ROOT", base / "tasks"), \
                 patch.object(runner, "verify_free_model", side_effect=AssertionError("No network")), \
                 patch.object(runner, "run_task", side_effect=AssertionError("No inference")):
                directory = bench.prepare_case(bench.make_cases()[0], "beam-free")
            task = json.loads((directory / "task.json").read_text(encoding="utf-8"))
            self.assertTrue(task["synthetic_demo"])
            self.assertTrue(task["accept_model_policy"])
            self.assertEqual(task["status"], "prepared")
            raw = (directory / task["inputs"][0]["copy"]).read_bytes()
            self.assertEqual(bench.hashlib.sha256(raw).hexdigest(), task["inputs"][0]["sha256"])
            self.assertNotIn(b"reference_answer", raw)
            self.assertLess(len(raw), runner.MAX_INPUT_BYTES)
            self.assertLess(max(map(len, raw.decode("utf-8").splitlines())), 1500)
            self.assertGreater(len(raw.splitlines()), 30)


if __name__ == "__main__":
    unittest.main()
