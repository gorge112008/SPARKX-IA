"""Consent boundaries and offline receipts; never invoke a remote model."""
from __future__ import annotations

import json
from unittest.mock import patch

from tools.opencode import runner
from tools.opencode.comparison import build_comparison, render_markdown
from tools.opencode.test_runner import RunnerFixture


def receipt(task_id="synthetic-example"):
    return {
        "task": task_id, "model": {"id": runner.DEFAULT_MODEL},
        "token_semantics": "opencode-v2.2.7", "observed_steps": 1,
        "observed_tokens": [{"input": 1000, "output": 20, "reasoning": 80,
                             "cache": {"read": 2000, "write": 0}}],
        "reported_cost": [0], "status": "review_required",
    }


class AdditionalModelTests(RunnerFixture):
    def restricted_models(self):
        return [key for key, policy in runner.MODEL_POLICIES.items() if policy["requires_policy_consent"]]

    def test_restricted_models_need_synthetic_declaration_and_explicit_policy_acceptance(self):
        for model in self.restricted_models():
            for declarations in ({}, {"synthetic": True}, {"accept_model_policy": True}):
                with self.subTest(model=model, declarations=declarations):
                    with self.assertRaises(runner.TaskError):
                        runner.prepare_task("Analiza un ejemplo ficticio.", model=model, **declarations)
        self.assertFalse(self.tasks.exists())
        self.catalog.assert_not_called()

    def test_all_restricted_models_prepare_without_network_and_preserve_their_own_policy(self):
        for model in self.restricted_models():
            with self.subTest(model=model):
                directory = runner.prepare_task("Analiza un ejemplo ficticio.", model=model,
                    demo=True, accept_model_policy=True)
                task = self.load_task(directory)
                self.assertTrue(task["synthetic_demo"])
                self.assertTrue(task["accept_model_policy"])
                self.assertEqual(task["model"], model)
                self.assertEqual(task["model_policy"], dict(runner.MODEL_POLICIES[model]))
                self.assertEqual(task["status"], "prepared")
        self.catalog.assert_not_called()

    def test_removed_policy_acceptance_stops_before_preflight_and_remote_catalogue(self):
        model = self.restricted_models()[0]
        directory = runner.prepare_task("Ejemplo ficticio.", model=model, demo=True, accept_model_policy=True)
        task = self.load_task(directory)
        task["accept_model_policy"] = False
        (directory / "task.json").write_text(json.dumps(task), encoding="utf-8")
        with patch.object(runner, "preflight") as preflight, patch.object(runner, "run_bounded") as process:
            with self.assertRaises(runner.TaskError):
                runner.run_task(directory.name)
            preflight.assert_not_called()
            process.assert_not_called()
        self.catalog.assert_not_called()

    def test_truthy_strings_do_not_count_as_synthetic_or_policy_acceptance(self):
        for declarations in ({"synthetic": "true"}, {"demo": "true"}, {"accept_model_policy": "true"}):
            with self.subTest(declarations=declarations), self.assertRaises(runner.TaskError):
                runner.prepare_task("Revisa.", **declarations)
        self.assertFalse(self.tasks.exists())

    def test_demo_is_included_in_the_five_file_limit(self):
        files = [f"apps/example{index}.py" for index in range(5)]
        for file in files:
            self.source(file)
        with self.assertRaisesRegex(runner.TaskError, "cinco archivos"):
            runner.prepare_task("Revisa ejemplos.", files=files, demo=True)
        self.assertFalse(self.tasks.exists())

    def test_adding_demo_does_not_declare_other_selected_files_synthetic(self):
        self.source("docs/context.md", b"unclassified context")
        model = self.restricted_models()[0]
        with self.assertRaisesRegex(runner.TaskError, "datos ficticios"):
            runner.prepare_task("Revisa.", model=model, files=["docs/context.md"],
                                demo=True, accept_model_policy=True)
        self.assertFalse(self.tasks.exists())
        directory = runner.prepare_task("Datos ficticios declarados.", model=model,
            files=["docs/context.md"], demo=True, synthetic=True, accept_model_policy=True)
        self.assertTrue(self.load_task(directory)["synthetic_demo"])
        self.catalog.assert_not_called()

    def test_wizard_selects_alternative_and_stops_before_transmitting(self):
        model = self.restricted_models()[0]
        selection = str(list(runner.ALLOWED_MODELS).index(model) + 1)
        with patch.object(runner, "installation_is_verified", return_value=True), \
             patch("builtins.input", side_effect=[selection, "ACEPTO DATOS FICTICIOS", "1", "Revisa datos ficticios.", "", "CANCELAR"]), \
             patch.object(runner, "run_task") as run:
            self.assertEqual(runner.wizard(), 0)
            run.assert_not_called()
        tasks = list(self.tasks.iterdir())
        self.assertEqual(len(tasks), 1)
        self.assertEqual(self.load_task(tasks[0])["model"], model)
        self.assertTrue(self.load_task(tasks[0])["accept_model_policy"])
        self.catalog.assert_not_called()

    def test_wizard_refusing_model_policy_creates_no_task(self):
        model = self.restricted_models()[0]
        selection = str(list(runner.ALLOWED_MODELS).index(model) + 1)
        with patch.object(runner, "installation_is_verified", return_value=True), \
             patch("builtins.input", side_effect=[selection, "NO"]):
            self.assertEqual(runner.wizard(), 0)
        self.assertFalse(self.tasks.exists())
        self.catalog.assert_not_called()


class OfflineComparisonTests(RunnerFixture):
    def test_reported_zero_stays_separate_from_positive_hypothetical_cost_and_reasoning(self):
        result = build_comparison(receipt())
        self.assertEqual(result["reported_cost"]["total"], "0")
        self.assertFalse(result["reported_cost"]["billing_independently_verified"])
        self.assertEqual(result["usage"]["tokens"]["output_billable"], 100)
        self.assertEqual(result["usage"]["tokens"]["input_total"], 3000)
        self.assertEqual(result["usage"]["tokens"]["total"], 3100)
        self.assertEqual(len(result["scenarios"]), 3)
        glm = result["scenarios"][0]
        self.assertEqual(float(glm["hypothetical_cost"]["total"]), .00026)
        self.assertEqual(float(glm["identical_workload_projections"]["1000"]), .26)
        self.assertFalse(result["paid_models_invoked"])
        self.assertIn("no se han ejecutado", render_markdown(result))
        self.catalog.assert_not_called()

    def test_missing_usage_and_cost_are_unknown_instead_of_free(self):
        data = receipt()
        data["observed_tokens"][0].pop("reasoning")
        data["reported_cost"] = [None]
        report = build_comparison(data)
        self.assertIsNone(report["reported_cost"]["total"])
        for scenario in report["scenarios"]:
            self.assertIsNone(scenario["hypothetical_cost"]["total"])
            self.assertIsNone(scenario["identical_workload_projections"]["1000"])
        self.assertIn("Desconocido", render_markdown(report))

    def test_missing_whole_step_is_not_presented_as_complete_workload(self):
        data = receipt()
        data["observed_steps"] = 2
        report = build_comparison(data)
        self.assertFalse(report["step_counters_match"])
        self.assertIsNone(report["reported_cost"]["total"])
        self.assertTrue(all(item["hypothetical_cost"]["total"] is None for item in report["scenarios"]))

    def test_interrupted_receipt_preserves_known_subtotal_but_never_claims_full_cost(self):
        data = receipt()
        data.update(status="failed", counters_incomplete=True)
        report = build_comparison(data)
        self.assertIsNone(report["reported_cost"]["total"])
        self.assertEqual(report["reported_cost"]["known_subtotal"], "0")
        self.assertFalse(report["reported_cost"]["complete"])
        self.assertTrue(all(item["hypothetical_cost"]["total"] is None for item in report["scenarios"]))

    def test_live_abort_keeps_partial_events_and_counters_without_retry_or_known_total(self):
        directory = self.prepared()
        self.allow_mock_execution()
        events = json.dumps({"type": "step_finish", "part": {"reason": "tool-calls", "cost": 0,
            "tokens": {"input": 100, "output": 10, "reasoning": 5, "cache": {"read": 0, "write": 0}}}}) + "\n"
        events += json.dumps({"type": "error", "error": {"message": "Synthetic provider error"}}) + "\n"
        problem = runner.TaskError("Interrupción de prueba")
        problem.partial_output = {"stdout": events, "stderr": "synthetic diagnostic", "seconds": 1.2, "exit_code": 1}
        with patch.object(runner, "run_bounded", side_effect=problem) as process:
            result = runner.run_task(directory.name)
        process.assert_called_once()
        self.assertEqual(result["status"], "failed")
        self.assertTrue(result["counters_incomplete"])
        self.assertEqual(result["observed_steps"], 1)
        self.assertEqual((directory / "events.jsonl").read_text(encoding="utf-8"), events)
        self.assertEqual((directory / "diagnostics.txt").read_text(encoding="utf-8"), "synthetic diagnostic")
        report = json.loads((directory / "cost-comparison.json").read_text(encoding="utf-8"))
        self.assertIsNone(report["reported_cost"]["total"])

    def test_unknown_harness_version_is_rejected_and_legacy_verified_receipt_is_supported(self):
        data = receipt()
        data["token_semantics"] = "unverified-version"
        with self.assertRaises(ValueError):
            build_comparison(data)
        data.pop("token_semantics")
        data["preflight"] = {"version": "2.2.7"}
        self.assertTrue(build_comparison(data)["step_counters_match"])

    def test_compare_command_only_reprices_existing_receipt_and_does_not_repeat_task(self):
        directory = self.prepared()
        result_file = directory / "result.json"
        result_file.write_text(json.dumps(receipt(directory.name)), encoding="utf-8")
        original = result_file.read_bytes()
        (directory / ".execution-claim").write_text("existing", encoding="ascii")
        with patch.object(runner, "run_task") as run, patch.object(runner, "run_bounded") as process:
            self.assertEqual(runner.main(["compare", directory.name]), 0)
            run.assert_not_called()
            process.assert_not_called()
        self.assertEqual(result_file.read_bytes(), original)
        self.assertEqual((directory / ".execution-claim").read_text(encoding="ascii"), "existing")
        self.assertTrue((directory / "cost-comparison.json").is_file())
        self.assertTrue((directory / "cost-comparison.md").is_file())
        self.catalog.assert_not_called()

    def test_receipt_for_another_task_is_rejected_without_writing_comparison(self):
        directory = self.prepared()
        (directory / "result.json").write_text(json.dumps(receipt("another-task")), encoding="utf-8")
        with self.assertRaises(runner.TaskError):
            runner.write_comparison(directory.name)
        self.assertFalse((directory / "cost-comparison.json").exists())

    def test_bad_reported_amounts_never_become_known_zero(self):
        for amount in (None, True, -1, "NaN", "Infinity", "oops", "1E+1000000", "1E-1000000"):
            with self.subTest(amount=amount):
                data = receipt()
                data["reported_cost"] = [amount]
                self.assertIsNone(build_comparison(data)["reported_cost"]["total"])

    def test_malformed_model_and_legacy_preflight_do_not_crash_with_attribute_error(self):
        data = receipt()
        data["model"] = None
        with self.assertRaises(ValueError):
            build_comparison(data)
        data = receipt()
        data.pop("token_semantics")
        data["preflight"] = None
        with self.assertRaises(ValueError):
            build_comparison(data)
