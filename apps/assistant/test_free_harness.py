"""Free bridge checks with mocked CLI/catalogue: no models or database writes."""

import copy
from concurrent.futures import ThreadPoolExecutor
from contextlib import ExitStack
import json
import os
from pathlib import Path
from types import SimpleNamespace
import tempfile
from threading import Barrier, Event, Lock
import unittest
from unittest.mock import call, patch

from apps.assistant import free_harness as harness
from tools.opencode import runner
from tools.opencode.catalog import CatalogVerificationError


def events(text="Respuesta sintética.", *, tokens=None, cost=0, reason="stop"):
    if tokens is None:
        tokens = {"input": 100, "output": 20, "reasoning": 7, "cache": {"read": 30, "write": 2}}
    return "\n".join(json.dumps(value) for value in (
        {"type": "step_start", "part": {}},
        {"type": "text", "part": {"text": text}},
        {"type": "step_finish", "part": {"reason": reason, "cost": cost, "tokens": tokens}},
    ))


class FreeHarnessTests(unittest.TestCase):
    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        temporal = harness.PROJECT_ROOT / "Temporal"
        temporal.mkdir(exist_ok=True)
        temporary = self.stack.enter_context(tempfile.TemporaryDirectory(prefix="test-assistant-free-", dir=temporal))
        self.task_root = Path(temporary) / "calls"
        self.stack.enter_context(patch.object(harness, "TASK_ROOT", self.task_root))
        self.stack.enter_context(patch.object(harness, "settings", SimpleNamespace(FREE_DEMO_ENABLED=True)))
        # The bridge's behavior is checked for the curated policy set; the app
        # catalogue's own tests separately check which profiles it exposes.
        self.stack.enter_context(patch.object(harness, "OPENCODE_DEMO_MODELS", frozenset(harness.MODEL_POLICIES)))
        self.installed = self.stack.enter_context(patch.object(harness, "installation_is_verified", return_value=True))
        self.catalog = self.stack.enter_context(patch.object(harness, "verify_free_model", return_value={
            "id": harness.MODEL, "context_limit": 128000, "output_limit": 2048,
        }))
        self.cli = self.stack.enter_context(patch.object(runner, "run_bounded", side_effect=self.run_cli))
        self.output = events()
        self.exit_code = 0
        self.directories = []
        self.configurations = []
        self.inputs = {
            "context": {"event": {"title": "Evento ficticio", "is_synthetic": True}, "request": "Ayuda"},
            "instructions": "Usa solo los datos ficticios de este contexto.",
            "action": "chat", "max_input_tokens": 24000, "max_output_tokens": 2048, "synthetic": True,
        }

    def run_cli(self, command, *, cwd, env, seconds, **options):
        self.directories.append(cwd)
        self.assertLessEqual(seconds, 90)
        self.assertGreater(seconds, 0)
        self.assertEqual(env["OPENCODE_CONFIG_PROJECT_DISABLE"], "1")
        self.assertEqual(env["OPENCODE_PURE"], "1")
        self.assertTrue(Path(env["USERPROFILE"]).is_relative_to(cwd))
        config_path = Path(env["XDG_CONFIG_HOME"]) / "opencode" / "opencode.json"
        configuration = json.loads(config_path.read_text(encoding="utf-8"))
        self.configurations.append(configuration)
        selected_model = configuration["model"].split("/", 1)[1]
        if command[1] == "debug":
            effective = copy.deepcopy(configuration)
            effective["model"] = {"providerID": "opencode", "model": selected_model}
            for agent in effective["agents"].values():
                agent["model"] = dict(effective["model"])
            return {"exit_code": 0, "stderr": "", "seconds": .01,
                    "stdout": json.dumps([{"type": "document", "path": str(config_path), "info": effective}])}
        self.assertTrue(options["stop_on_model_error"])
        catalogue_arguments = {"synthetic_demo": True}
        if harness.MODEL_POLICIES[selected_model]["requires_policy_consent"]:
            catalogue_arguments["accept_model_policy"] = True
        self.assertEqual(self.catalog.call_args, call(selected_model, **catalogue_arguments))
        self.assertEqual(command[command.index("--model") + 1], "opencode/" + selected_model)
        self.assertNotIn("--file", command)
        self.assertEqual(json.loads(command[-1])["context"], self.inputs["context"])
        return {"exit_code": self.exit_code, "stderr": "private diagnostic, never returned",
                "seconds": .05, "stdout": self.output}

    def call(self, **overrides):
        return harness.run_free_harness(**{**self.inputs, **overrides})

    def test_text_and_disjoint_usage_conversion_and_private_cleanup(self):
        result = self.call()
        self.assertEqual(result["text"], "Respuesta sintética.")
        self.assertIsNone(result["payload"])
        self.assertEqual(result["usage"], {"input_tokens": 132, "output_tokens": 27,
            "cached_input_tokens": 30, "reasoning_tokens": 7, "total_tokens": 159})
        self.assertEqual(result["reported_cost"], 0)
        self.assertEqual(result["token_semantics"], "opencode-v2.2.7")
        self.assertEqual(self.cli.call_count, 2)
        self.assertTrue(all(not directory.exists() for directory in self.directories))
        self.assertEqual(list(self.task_root.iterdir()), [])

    def test_each_reviewed_model_is_explicit_and_never_replaced(self):
        for model in sorted(harness.OPENCODE_DEMO_MODELS):
            with self.subTest(model=model):
                self.cli.reset_mock()
                self.catalog.return_value = {"id": model, "context_limit":128000,"output_limit":2048}
                consent = {"policy_acknowledgement": harness.policy_fingerprint(model)} if harness.MODEL_POLICIES[model]["requires_policy_consent"] else {}
                result = self.call(model=model, **consent)
                self.assertEqual(result["usage"]["total_tokens"],159)
                self.assertEqual(self.cli.call_count,2)
                self.assertEqual(self.configurations[-1]["model"],"opencode/"+model)

    def test_unreviewed_or_paid_model_is_rejected_before_native_or_catalogue(self):
        for model in (None,True,[],"deepseek-v4.1-flash","minimax-m3","groq/openai/gpt-oss-20b","jev"):
            with self.subTest(model=model), self.assertRaises(harness.FreeHarnessError) as raised:
                self.call(model=model)
            self.assertEqual(raised.exception.phase,"validation")
        self.cli.assert_not_called()
        self.catalog.assert_not_called()

    def test_special_model_acknowledgement_is_current_model_specific_and_checked_before_runtime(self):
        restricted = [model for model, policy in harness.MODEL_POLICIES.items() if policy["requires_policy_consent"]]
        self.assertEqual(len(restricted), 10)
        with patch.object(harness, "_private_runtime") as runtime:
            for model in restricted:
                for acknowledgement in (None, True, 1, [], {}, "", "forged", "0" * 64,
                                        harness.policy_fingerprint(harness.MODEL)):
                    with self.subTest(model=model, ack=acknowledgement), self.assertRaises(harness.FreeHarnessError) as failure:
                        self.call(model=model, policy_acknowledgement=acknowledgement)
                    self.assertEqual(failure.exception.phase, "validation")
            runtime.assert_not_called()
        self.cli.assert_not_called()
        self.catalog.assert_not_called()

    def test_valid_special_acknowledgement_reaches_catalogue_without_authorizing_price_or_model_changes(self):
        model = "big-pickle"
        self.catalog.return_value = {"id": model, "context_limit": 128000, "output_limit": 2048}
        acknowledgement = harness.policy_fingerprint(model)
        result = self.call(model=model, policy_acknowledgement=acknowledgement)
        self.assertEqual(result["text"], "Respuesta sintética.")
        self.catalog.assert_called_once_with(model, synthetic_demo=True, accept_model_policy=True)
        self.assertEqual(self.configurations[-1]["model"], "opencode/" + model)
        self.catalog.reset_mock(); self.cli.reset_mock()
        self.catalog.side_effect = CatalogVerificationError("price changed; private body")
        with self.assertRaises(harness.FreeHarnessError):
            self.call(model=model, policy_acknowledgement=acknowledgement)
        self.assertEqual(self.cli.call_count, 1)  # Preflight only, never inference.
        self.catalog.assert_called_once_with(model, synthetic_demo=True, accept_model_policy=True)

    def test_changed_policy_or_supplied_invalid_acknowledgement_never_creates_runtime(self):
        model = "big-pickle"
        old_fingerprint = harness.policy_fingerprint(model)
        with patch.object(harness, "policy_fingerprint", return_value="f" * 64), patch.object(harness, "_private_runtime") as runtime:
            with self.assertRaises(harness.FreeHarnessError):
                self.call(model=model, policy_acknowledgement=old_fingerprint)
            with self.assertRaises(harness.FreeHarnessError):
                self.call(policy_acknowledgement=True)
            runtime.assert_not_called()
        self.cli.assert_not_called()
        self.catalog.assert_not_called()

    def _parallel_calls(self, *, fail_first=False):
        """Overlap two mocked native processes, never sharing mutable receipts."""
        barrier, lock, second_completed = Barrier(2), Lock(), Event()
        models = ("glm-5.3-flash-free", "deepseek-v4.1-flash-free")
        markers = {models[0]: "synthetic-alpha", models[1]: "synthetic-beta"}
        token_buckets = {
            models[0]: {"input":101,"output":11,"reasoning":3,"cache":{"read":7,"write":2}},
            models[1]: {"input":202,"output":22,"reasoning":5,"cache":{"read":13,"write":4}},
        }
        private_keys = ("XDG_CONFIG_HOME","XDG_DATA_HOME","XDG_CACHE_HOME","XDG_STATE_HOME",
                        "USERPROFILE","APPDATA","LOCALAPPDATA","TEMP","TMP")
        captured, completion_order = {}, []
        def catalogue(model, **options):
            self.assertEqual(options, {"synthetic_demo": True})
            return {"id":model,"context_limit":128000,"output_limit":2048}
        def native(command, *, cwd, env, **options):
            config_path = Path(env["XDG_CONFIG_HOME"]) / "opencode" / "opencode.json"
            configuration = json.loads(config_path.read_text(encoding="utf-8"))
            model = configuration["model"].split("/",1)[1]
            if command[1] == "debug":
                effective = copy.deepcopy(configuration)
                effective["model"] = {"providerID":"opencode","model":model}
                for agent in effective["agents"].values():agent["model"] = dict(effective["model"])
                return {"exit_code":0,"stderr":"","stdout":json.dumps([{"type":"document","path":str(config_path),"info":effective}])}
            marker = markers[model]
            other_marker = next(value for value in markers.values() if value != marker)
            self.assertEqual(command[command.index("--model")+1], "opencode/"+model)
            self.assertIs(options["stop_on_model_error"], True)
            self.assertEqual(json.loads(command[-1])["context"], {"request":marker})
            self.assertIn(marker,configuration["agents"]["sparkx-review"]["system"])
            self.assertNotIn(other_marker,json.dumps(configuration))
            self.assertTrue(all(Path(env[key]).is_relative_to(cwd) for key in private_keys))
            self.assertNotIn("OPENAI_API_KEY",env)
            self.assertNotIn("OPENCODE_API_KEY",env)
            canary = Path(env["XDG_CACHE_HOME"]) / "sentinel.txt"
            canary.write_text(marker,encoding="utf-8")
            with lock:captured[model] = {"cwd":cwd,"env":dict(env),"config":configuration,"canary":canary}
            barrier.wait(timeout=5)
            self.assertEqual(canary.read_text(encoding="utf-8"),marker)
            if model == models[0]:self.assertTrue(second_completed.wait(timeout=5))
            with lock:completion_order.append(model)
            if model == models[1]:second_completed.set()
            if fail_first and model == models[0]:
                error = runner.TaskError("private synthetic process failure")
                error.partial_output = {"stdout":json.dumps({"type":"error","error":{"status":429}}),"stderr":"private"}
                raise error
            return {"exit_code":0,"stderr":"","stdout":events(marker,tokens=token_buckets[model])}
        def run(model):
            try:
                return self.call(model=model,context={"request":markers[model]},instructions="Usa solo "+markers[model])
            except harness.FreeHarnessError as error:return error
        self.catalog.side_effect=catalogue
        self.cli.side_effect=native
        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = {model:executor.submit(run,model) for model in models}
            results = {model:future.result(timeout=10) for model,future in futures.items()}
        self.assertEqual(completion_order,[models[1],models[0]])
        self.assertNotEqual(captured[models[0]]["cwd"],captured[models[1]]["cwd"])
        for key in private_keys:
            self.assertNotEqual(captured[models[0]]["env"][key],captured[models[1]]["env"][key])
        self.assertTrue(all(not item["cwd"].exists() for item in captured.values()))
        self.assertEqual(list(self.task_root.iterdir()),[])
        self.assertEqual(self.cli.call_count,4)
        self.assertEqual(self.catalog.call_count,2)
        for model in models:
            result=results[model]
            if fail_first and model == models[0]:
                self.assertIsInstance(result,harness.FreeHarnessError)
                self.assertEqual(result.http_status,429)
                self.assertEqual(result.usage,{})
                self.assertEqual(result.observed_usage,{})
            else:
                self.assertIsInstance(result,dict)
                self.assertEqual(result["text"],markers[model])
                buckets=token_buckets[model]
                self.assertEqual(result["usage"],{
                    "input_tokens":buckets["input"]+buckets["cache"]["read"]+buckets["cache"]["write"],
                    "output_tokens":buckets["output"]+buckets["reasoning"],
                    "cached_input_tokens":buckets["cache"]["read"],"reasoning_tokens":buckets["reasoning"],
                    "total_tokens":sum((buckets["input"],buckets["cache"]["read"],buckets["cache"]["write"],buckets["output"],buckets["reasoning"]))})
        return results

    def test_parallel_models_keep_prompts_configuration_cache_runtime_and_usage_separate(self):
        self._parallel_calls()

    def test_one_parallel_native_failure_does_not_mix_other_calls_usage_or_cleanup(self):
        self._parallel_calls(fail_first=True)

    def test_all_tools_and_auxiliary_agents_denied_and_only_one_step(self):
        self.call()
        config = self.configurations[0]
        self.assertIn({"action": "tool.use", "resource": "*", "effect": "deny"}, config["policies"])
        for name, agent in config["agents"].items():
            self.assertEqual(agent["permissions"], [{"action": "*", "resource": "*", "effect": "deny"}])
            self.assertEqual(agent["steps"], 1)
            self.assertEqual(agent["model"], "opencode/" + harness.MODEL)
            if name != "sparkx-review":
                self.assertIs(agent["disabled"], True)
        self.assertFalse(config["compaction"]["auto"])
        self.assertEqual(config["mcp"], {"servers": {}})
        self.assertEqual(config["skills"], [])

    def test_plan_schema_is_prompt_only_and_object_returned(self):
        self.output = events('{"title":"Propuesta sintética"}')
        schema = {"type": "object", "properties": {"title": {"type": "string"}}}
        result = self.call(action="plan", schema=schema)
        self.assertEqual(result["payload"], {"title": "Propuesta sintética"})
        self.assertIn(json.dumps(schema, ensure_ascii=False), self.configurations[0]["agents"]["sparkx-review"]["system"])

    def test_invalid_model_json_is_safe_and_keeps_completed_usage(self):
        for text in ('```json\n{}\n```', '[]', '{"x":1,"x":2}', '{"x":NaN}'):
            with self.subTest(text=text):
                self.cli.reset_mock()
                self.catalog.reset_mock()
                self.output = events(text)
                with self.assertRaises(harness.FreeHarnessError) as raised:
                    self.call(action="plan")
                self.assertEqual(raised.exception.usage["total_tokens"], 159)
                self.assertNotIn(text, str(raised.exception))

    def test_declared_synthetic_true_required_before_any_child_or_catalogue(self):
        for value in (False, None, 1, "true"):
            with self.subTest(value=value), self.assertRaises(harness.FreeHarnessError):
                self.call(synthetic=value)
        self.cli.assert_not_called()
        self.catalog.assert_not_called()

    def test_invalid_limits_action_and_serialization_stop_locally(self):
        bad = ({"max_output_tokens": 2049}, {"max_output_tokens": True}, {"max_input_tokens": 10},
               {"max_seconds": 91}, {"max_seconds": True}, {"action": "shell"},
               {"context": {"unexpected": object()}}, {"context": {"number": float("nan")}},
               {"context": {1: "bad key"}}, {"instructions": "x" * 6001},
               {"context": {"surrogate": "\ud800"}}, {"context": {"huge": "x" * 24000}})
        for overrides in bad:
            with self.subTest(fields=list(overrides)), self.assertRaises(harness.FreeHarnessError):
                self.call(**overrides)
        self.cli.assert_not_called()
        self.catalog.assert_not_called()

    def test_likely_secrets_stop_before_any_external_call(self):
        with self.assertRaises(harness.FreeHarnessError):
            self.call(context={"key": "sk-" + "A" * 30})
        self.cli.assert_not_called()
        self.catalog.assert_not_called()

    def test_ready_is_local_and_feature_switch_and_integrity_gate_calls(self):
        self.assertTrue(harness.ready())
        self.cli.assert_not_called()
        self.catalog.assert_not_called()
        with patch.object(harness, "settings", SimpleNamespace(FREE_DEMO_ENABLED=False)):
            self.assertFalse(harness.ready())
            with self.assertRaises(harness.FreeHarnessError):
                self.call()
        self.installed.return_value = False
        with self.assertRaises(harness.FreeHarnessError):
            self.call()
        self.cli.assert_not_called()
        self.catalog.assert_not_called()

    def test_credentials_are_not_inherited(self):
        with patch.dict(os.environ, {"OPENAI_API_KEY": "secret", "OPENCODE_API_KEY": "secret",
                                     "HTTPS_PROXY": "https://secret.invalid", "AWS_SECRET_ACCESS_KEY": "secret"}):
            self.call()
        for call in self.cli.call_args_list:
            for key in ("OPENAI_API_KEY", "OPENCODE_API_KEY", "HTTPS_PROXY", "AWS_SECRET_ACCESS_KEY"):
                self.assertNotIn(key, call.kwargs["env"])

    def test_catalogue_failure_never_calls_model_or_fallback(self):
        self.catalog.side_effect = CatalogVerificationError("untrusted remote body secret")
        with self.assertRaises(harness.FreeHarnessError) as raised:
            self.call()
        self.assertEqual(self.cli.call_count, 1)
        self.assertEqual(self.catalog.call_count, 1)
        self.assertEqual(raised.exception.usage, {})
        self.assertNotIn("secret", str(raised.exception))

    def test_preflight_mismatch_never_checks_catalogue_or_calls_model(self):
        with patch.object(runner, "verify_effective_configuration", side_effect=runner.TaskError("unsafe config")):
            with self.assertRaises(harness.FreeHarnessError):
                self.call()
        self.assertEqual(self.cli.call_count, 1)
        self.catalog.assert_not_called()

    def test_catalogue_limits_or_wrong_model_block_call(self):
        for catalog in ({"id": "other", "context_limit": 128000, "output_limit": 2048},
                        {"id": harness.MODEL, "context_limit": 100, "output_limit": 2048},
                        {"id": harness.MODEL, "context_limit": 128000, "output_limit": 10}):
            with self.subTest(catalog=catalog):
                self.cli.reset_mock()
                self.catalog.return_value = catalog
                with self.assertRaises(harness.FreeHarnessError):
                    self.call()
                self.assertEqual(self.cli.call_count, 1)

    def test_retry_error_tool_extra_step_and_positive_cost_receipts_are_incomplete(self):
        cases = (events(reason="length"), events(cost=.01), events() + '\n{"type":"retry"}',
                 events() + '\n{"type":"tool_use","part":{"name":"read"}}', events() + "\n" + events(),
                 events() + '\n{"type":"error","message":"secret"}', events() + '\nnot JSON')
        for output in cases:
            with self.subTest(output=output[-80:]):
                self.cli.reset_mock()
                self.catalog.reset_mock()
                self.output = output
                with self.assertRaises(harness.FreeHarnessError) as raised:
                    self.call()
                self.assertNotIn("output_tokens", raised.exception.usage)
                self.assertNotIn("total_tokens", raised.exception.usage)
                self.assertIn("output_tokens", raised.exception.observed_usage)
                self.assertNotIn("secret", str(raised.exception))
                self.assertEqual(self.cli.call_count, 2)
                self.assertEqual(self.catalog.call_count, 1)

    def test_missing_usage_is_unknown_not_zero_and_cache_never_double_counted(self):
        self.output = events(tokens={})
        self.assertEqual(self.call()["usage"], {})
        self.cli.reset_mock()
        self.catalog.reset_mock()
        self.output = events(tokens={"input": 100, "output": 20, "cache": {"read": 30}})
        self.assertEqual(self.call()["usage"], {"cached_input_tokens": 30})

    def test_interruption_keeps_partial_observations_without_settling(self):
        original = self.run_cli

        def interrupted(command, **kwargs):
            if command[1] == "debug":
                return original(command, **kwargs)
            error = runner.TaskError("native diagnostic with secret")
            error.partial_output = {"stdout": events(), "stderr": "secret", "exit_code": -1, "seconds": 90}
            raise error

        self.cli.side_effect = interrupted
        with self.assertRaises(harness.FreeHarnessError) as raised:
            self.call()
        self.assertEqual(raised.exception.usage["input_tokens"], 132)
        self.assertNotIn("output_tokens", raised.exception.usage)
        self.assertEqual(raised.exception.observed_usage["output_tokens"], 27)
        self.assertNotIn("secret", str(raised.exception))
        self.assertTrue(all(not directory.exists() for directory in self.directories))

    def test_nonzero_exit_never_settles_usage(self):
        self.exit_code = 1
        with self.assertRaises(harness.FreeHarnessError) as raised:
            self.call()
        self.assertNotIn("output_tokens", raised.exception.usage)

    def test_each_explicit_call_rechecks_catalogue_and_has_new_private_state(self):
        self.call()
        self.call()
        self.assertEqual(self.catalog.call_count, 2)
        self.assertEqual(self.cli.call_count, 4)
        self.assertNotEqual(self.directories[0], self.directories[2])

    def test_deadline_exhausted_before_catalogue_or_before_model_never_runs_model(self):
        for ticks, expected_catalogue_calls in (([0, 1, 80], 0), ([0, 1, 2, 91], 1)):
            with self.subTest(ticks=ticks):
                self.cli.reset_mock()
                self.catalog.reset_mock()
                with patch.object(harness.time, "monotonic", side_effect=ticks):
                    with self.assertRaises(harness.FreeHarnessError):
                        self.call()
                self.assertEqual(self.cli.call_count, 1)
                self.assertEqual(self.catalog.call_count, expected_catalogue_calls)

    def test_linked_or_external_task_root_cannot_start_process(self):
        with patch.object(Path, "is_symlink", lambda path: path == self.task_root):
            with self.assertRaises(harness.FreeHarnessError):
                self.call()
        with patch.object(harness, "TASK_ROOT", harness.PROJECT_ROOT.parent / "outside-free-task"):
            with self.assertRaises(harness.FreeHarnessError):
                self.call()
        self.cli.assert_not_called()
        self.catalog.assert_not_called()

    def test_chat_size_bound_preserves_completed_counters(self):
        self.output = events("x" * 20001)
        with self.assertRaises(harness.FreeHarnessError) as raised:
            self.call()
        self.assertEqual(raised.exception.usage["total_tokens"], 159)

    def fail_native(self, *, status=429):
        original = self.run_cli

        def fail(command, **kwargs):
            if command[1] == "debug":
                return original(command, **kwargs)
            error = runner.TaskError("private native exception")
            error.partial_output = {"stdout": "\n".join(json.dumps(event) for event in (
                {"type": "step_start", "part": {}},
                {"type": "error", "error": {"type": "APIError", "status": status,
                    "message": "private message", "response": {"body": "secret provider body"}}},
            )), "stderr": "private diagnostic", "exit_code": 1, "seconds": .1}
            raise error

        self.cli.side_effect = fail

    def test_empty_and_error_without_step_finish_do_not_invent_counts_or_raise(self):
        self.assertEqual(harness._normalize_usage([]), {})
        receipt = harness._receipt('{"type":"step_start"}\n{"type":"error"}', interrupted=True)
        self.assertEqual(receipt["usage"], {})
        self.assertEqual(receipt["observed_usage"], {})
        self.assertFalse(receipt["valid"])
        self.assertIsNone(receipt["reported_cost"])

    def test_native_http_status_is_safe_and_failure_without_usage_is_preserved(self):
        self.fail_native()
        with self.assertRaises(harness.FreeHarnessError) as raised:
            self.call()
        error = raised.exception
        self.assertEqual(error.diagnostic, {"phase": "inference", "code": "quota_or_rate_limit",
                                          "http_status": 429, "cleanup_failed": False})
        self.assertEqual(error.usage, {})
        self.assertEqual(error.observed_usage, {})
        self.assertNotIn("private", str(error))
        self.assertNotIn("secret", json.dumps(error.diagnostic))
        self.assertIn("no se reintenta", str(error))

    def test_http_status_never_comes_from_messages_bodies_or_untyped_values(self):
        for status in (None, "429", True, -1, 600, {"status": 429}):
            with self.subTest(status=status):
                event = {"type": "error", "error": {"status": status, "message": "HTTP 429 secret",
                         "response": {"body": "HTTP 503 secret", "status": 503}}}
                receipt = harness._receipt(json.dumps(event), interrupted=True)
                self.assertIsNone(receipt["http_status"])
                self.assertEqual(receipt["error_code"], "native_error")

    def test_transient_native_handle_cleanup_is_retried_without_model_reexecution(self):
        actual_cleanup = tempfile.TemporaryDirectory.cleanup
        attempts = []

        def transient_cleanup(temporary):
            attempts.append(temporary.name)
            if len(attempts) == 1:
                raise PermissionError("temporary native handle")
            actual_cleanup(temporary)

        with patch.object(tempfile.TemporaryDirectory, "cleanup", transient_cleanup), patch.object(harness.time, "sleep"):
            result = self.call()
        self.assertEqual(result["usage"]["total_tokens"], 159)
        self.assertEqual(len(attempts), 2)
        self.assertEqual(self.cli.call_count, 2)  # One preflight and one inference.

    def test_cleanup_failure_never_replaces_original_native_status(self):
        self.fail_native()
        actual_cleanup = tempfile.TemporaryDirectory.cleanup

        def fail_cleanup(temporary):
            actual_cleanup(temporary)
            raise PermissionError("private path and native diagnostic")

        with patch.object(tempfile.TemporaryDirectory, "cleanup", fail_cleanup):
            with self.assertRaises(harness.FreeHarnessError) as raised:
                self.call()
        self.assertEqual(raised.exception.diagnostic, {"phase": "inference", "code": "quota_or_rate_limit",
                                                      "http_status": 429, "cleanup_failed": True})
        self.assertEqual(raised.exception.usage, {})
        self.assertIn("no se reintenta", str(raised.exception))

    def test_cleanup_failure_after_completed_call_retains_reported_usage(self):
        actual_cleanup = tempfile.TemporaryDirectory.cleanup

        def fail_cleanup(temporary):
            actual_cleanup(temporary)
            raise PermissionError("private runtime path")

        with patch.object(tempfile.TemporaryDirectory, "cleanup", fail_cleanup):
            with self.assertRaises(harness.FreeHarnessError) as raised:
                self.call()
        self.assertEqual(raised.exception.phase, "cleanup")
        self.assertEqual(raised.exception.code, "cleanup_failed")
        self.assertTrue(raised.exception.cleanup_failed)
        self.assertEqual(raised.exception.usage["total_tokens"], 159)

    def test_catalogue_and_output_errors_expose_only_controlled_phase_codes(self):
        self.catalog.side_effect = CatalogVerificationError("secret body")
        with self.assertRaises(harness.FreeHarnessError) as raised:
            self.call()
        self.assertEqual(raised.exception.phase, "catalog")
        self.assertEqual(raised.exception.code, "catalog_unavailable")
        self.assertIsNone(raised.exception.http_status)
        self.catalog.side_effect = None
        self.catalog.reset_mock()
        self.output = events("bad JSON")
        with self.assertRaises(harness.FreeHarnessError) as raised:
            self.call(action="plan")
        self.assertEqual(raised.exception.phase, "output")
        self.assertEqual(raised.exception.code, "invalid_output")
        self.assertEqual(raised.exception.usage["total_tokens"], 159)


if __name__ == "__main__":
    unittest.main()
