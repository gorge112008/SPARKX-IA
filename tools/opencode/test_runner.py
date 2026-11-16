"""Restricted-runner regression tests, with no OpenCode or model requests."""

from __future__ import annotations

import copy
import hashlib
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import threading
import time
import unittest
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from contextlib import ExitStack, redirect_stderr, redirect_stdout
from unittest.mock import Mock, patch

from tools.opencode import runner
from tools.opencode.configuration import build_config


def cli_events(*events):
    return "".join(json.dumps(event) + "\n" for event in events)


def successful_cli_response(text="Hallazgo de ejemplo para revisión."):
    return cli_events(
        {"type": "text", "part": {"text": text}},
        {"type": "step_finish", "part": {"reason": "stop", "cost": 0,
            "tokens": {"input": 123, "output": 45, "reasoning": 0, "cache": {"read": 0, "write": 0}}}},
    )


class RunnerFixture(unittest.TestCase):
    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        temporal = Path(__file__).resolve().parents[2] / "Temporal"
        temporal.mkdir(exist_ok=True)
        temporary = self.stack.enter_context(tempfile.TemporaryDirectory(prefix="test-opencode-runner-", dir=temporal))
        self.root = Path(temporary) / "project"
        self.root.mkdir()
        self.tasks = self.root / "Temporal" / "opencode" / "tasks"
        self.stack.enter_context(patch.multiple(runner, PROJECT_ROOT=self.root, TASK_ROOT=self.tasks))
        self.catalog = self.stack.enter_context(
            patch.object(runner, "verify_free_model", side_effect=AssertionError("Real catalogue/network forbidden"))
        )
        self.output = io.StringIO()
        self.stack.enter_context(redirect_stdout(self.output))
        self.stack.enter_context(redirect_stderr(self.output))

    def source(self, relative="apps/example.py", content=b"def total(items):\n    return sum(items)\n"):
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        return path

    def prepared(self, **kwargs):
        return runner.prepare_task("Revisa posibles errores y explica sus límites.", demo=True, **kwargs)

    def load_task(self, directory):
        return json.loads((directory / "task.json").read_text(encoding="utf-8"))

    def effective_entries(self, directory, mode="review"):
        expected = build_config("opencode/" + runner.DEFAULT_MODEL, mode)
        actual = copy.deepcopy(expected)
        model = {"providerID": "opencode", "model": runner.DEFAULT_MODEL}
        actual["model"] = model
        for agent in actual["agents"].values():
            agent["model"] = model.copy()
        return [{
            "type": "document",
            "path": str(directory / ".runtime" / "config" / "opencode" / "opencode.json"),
            "info": actual,
        }]

    def allow_mock_execution(self):
        self.stack.enter_context(patch.object(runner, "installation_is_verified", return_value=True))
        self.stack.enter_context(patch.object(runner, "preflight", return_value={"configuration_verified": True}))
        self.catalog.side_effect = None
        self.catalog.return_value = {"id": runner.DEFAULT_MODEL, "prices": {"input": 0, "output": 0}}


class SelectedContextTests(RunnerFixture):
    def test_only_explicit_reviewed_text_roots_and_readme_are_accepted(self):
        for name in ("apps/example.py", "templates/example.html", "static/example.css", "docs/example.md", "README.md"):
            with self.subTest(file=name):
                source = self.source(name, b"public reviewed text")
                relative, data = runner.selected_text(name)
                self.assertEqual(relative, source.relative_to(self.root).as_posix())
                self.assertEqual(data, b"public reviewed text")

    def test_absolute_traversal_hidden_runtime_and_unsupported_files_are_rejected(self):
        denied = [
            str(self.root / "apps" / "example.py"), "../apps/example.py", "apps/../docs/example.md",
            "var/database.json", "Temporal/result.txt", ".agents/context.md", "config/settings.py",
            "apps/.env", "apps/.env.example.md", "apps/.hidden/code.py", "apps/var/export.json",
            "apps/node_modules/module.js", "apps/__pycache__/module.py", "docs/report.pdf", "",
        ]
        for name in denied:
            with self.subTest(file=name):
                with self.assertRaises(runner.TaskError):
                    runner.selected_text(name)
        self.assertFalse(self.tasks.exists())

    def test_context_byte_limit_utf8_nuls_and_recognizable_secrets_are_enforced(self):
        cases = {
            "oversized": b"x" * (runner.MAX_INPUT_BYTES + 1),
            "not UTF-8": b"\xff\xfe\x80",
            "NUL": b"ordinary text\x00more text",
            "API secret": b"sk-" + b"a" * 30,
            "GitHub secret": b"ghp_" + b"b" * 30,
            "private key": b"-----BEGIN RSA PRIVATE KEY-----\nfixture",
        }
        for label, content in cases.items():
            with self.subTest(case=label):
                self.source(content=content)
                with self.assertRaises(runner.TaskError):
                    runner.selected_text("apps/example.py")
        self.source(content=b"x" * runner.MAX_INPUT_BYTES)
        self.assertEqual(len(runner.selected_text("apps/example.py")[1]), runner.MAX_INPUT_BYTES)

    def test_symlink_detection_blocks_selected_file_before_content_is_read(self):
        source = self.source()
        original_open = Path.open
        content_opened = []

        def guarded_open(path, *args, **kwargs):
            if path == source:
                content_opened.append(path)
            return original_open(path, *args, **kwargs)

        # Windows may prohibit creating real symlinks without Developer Mode.
        # Simulate filesystem metadata at the check, never bypass the guard.
        original_is_symlink = Path.is_symlink
        with patch.object(Path, "is_symlink", autospec=True, side_effect=lambda path: path == source or original_is_symlink(path)):
            with patch.object(Path, "open", autospec=True, side_effect=guarded_open):
                with self.assertRaisesRegex(runner.TaskError, "enlaces"):
                    runner.selected_text("apps/example.py")
        self.assertEqual(content_opened, [])


class PreparationAndEnvironmentTests(RunnerFixture):
    def test_preparation_copies_inputs_and_never_changes_application_or_contacts_provider(self):
        original = self.source()
        original_bytes = original.read_bytes()
        directory = runner.prepare_task("Revisa esta función.", files=["apps/example.py"])
        task = self.load_task(directory)
        self.assertTrue(directory.is_relative_to(self.tasks))
        self.assertEqual(task["status"], "prepared")
        self.assertEqual(task["model"], runner.DEFAULT_MODEL)
        self.assertFalse(task["synthetic_demo"])
        self.assertEqual(len(task["inputs"]), 1)
        entry = task["inputs"][0]
        self.assertEqual((directory / entry["copy"]).read_bytes(), original_bytes)
        self.assertEqual(entry["sha256"], hashlib.sha256(original_bytes).hexdigest())
        self.assertEqual(original.read_bytes(), original_bytes)
        self.assertEqual(list((directory / "outputs").iterdir()), [])
        configuration = json.loads((directory / ".runtime/config/opencode/opencode.json").read_text(encoding="utf-8"))
        self.assertEqual(configuration, build_config("opencode/" + runner.DEFAULT_MODEL, "review"))
        self.assertFalse((directory / "result.json").exists())
        self.catalog.assert_not_called()

    def test_invalid_prompts_models_modes_file_count_and_combined_bytes_create_no_task(self):
        for prompt in ("", "  ", "x" * (runner.MAX_PROMPT_CHARS + 1), "sk-" + "a" * 30):
            with self.subTest(prompt=prompt[:20]):
                with self.assertRaises(runner.TaskError):
                    runner.prepare_task(prompt)
        for arguments in ({"model": "paid-model"}, {"mode": "build"}, {"files": ["apps/example.py"] * 6}):
            with self.subTest(arguments=arguments):
                with self.assertRaises(runner.TaskError):
                    runner.prepare_task("Revisa.", **arguments)
        self.source("apps/one.py", b"x" * (runner.MAX_INPUT_BYTES // 2 + 1))
        self.source("apps/two.py", b"x" * (runner.MAX_INPUT_BYTES // 2 + 1))
        with self.assertRaisesRegex(runner.TaskError, "combinados"):
            runner.prepare_task("Revisa.", files=["apps/one.py", "apps/two.py"])
        self.assertFalse(self.tasks.exists())
        self.catalog.assert_not_called()

    def test_child_environment_whitelists_os_fields_and_isolates_all_profile_directories(self):
        directory = self.root / "isolated"
        directory.mkdir()
        inherited = {
            "SystemRoot": r"C:\Windows", "WINDIR": r"C:\Windows", "COMSPEC": r"C:\Windows\System32\cmd.exe",
            "PATHEXT": ".EXE;.CMD", "PATH": r"C:\untrusted\bin", "HOME": r"C:\real-home",
            "USERPROFILE": r"C:\real-profile", "APPDATA": r"C:\real-appdata", "XDG_CONFIG_HOME": r"C:\real-config",
            "OPENAI_API_KEY": "sk-" + "a" * 30, "ANTHROPIC_API_KEY": "private-fixture",
            "GITHUB_TOKEN": "ghp_" + "b" * 30, "HTTPS_PROXY": "https://user:pass@proxy.example",
            "HTTP_PROXY": "http://proxy.example", "OTEL_EXPORTER_OTLP_ENDPOINT": "https://collector.example",
            "OPENCODE_CONFIG_CONTENT": "{untrusted override}", "OPENCODE_SERVER_PASSWORD": "private-password",
        }
        with patch.dict(os.environ, inherited, clear=True):
            env = runner.child_environment(directory)
        for field in ("OPENAI_API_KEY", "ANTHROPIC_API_KEY", "GITHUB_TOKEN", "HTTPS_PROXY", "HTTP_PROXY", "OTEL_EXPORTER_OTLP_ENDPOINT", "OPENCODE_CONFIG_CONTENT", "OPENCODE_SERVER_PASSWORD"):
            self.assertNotIn(field, env)
        self.assertEqual(env["SystemRoot"], inherited["SystemRoot"])
        self.assertEqual(env["PATH"], str(Path(inherited["SystemRoot"]) / "System32"))
        for field in ("USERPROFILE", "APPDATA", "LOCALAPPDATA", "TEMP", "TMP", "XDG_CONFIG_HOME", "XDG_DATA_HOME", "XDG_CACHE_HOME", "XDG_STATE_HOME", "OPENCODE_TEST_HOME"):
            self.assertTrue(Path(env[field]).is_relative_to(directory / ".runtime"), field)
            self.assertTrue(Path(env[field]).is_dir(), field)
        self.assertNotEqual(env.get("HOME"), inherited["HOME"])
        self.assertEqual(env["DO_NOT_TRACK"], "1")
        self.assertEqual(env["OPENCODE_DISABLE_AUTOUPDATE"], "1")
        self.assertEqual(env["OPENCODE_PURE"], "1")
        self.assertEqual(env["OPENCODE_TEST_HOME"], env["USERPROFILE"])

    def test_task_identifier_and_resolved_directory_cannot_escape_task_root(self):
        for task_id in ("../outside", "", "20261114T235959-fffffffffg", "20261114T235959-aaaaaaaaaa/../outside"):
            with self.subTest(task=task_id):
                with self.assertRaises(runner.TaskError):
                    runner.task_directory(task_id)
        valid = "20261114T235959-aaaaaaaaaa"
        self.assertEqual(runner.task_directory(valid), self.tasks / valid)


class EffectiveConfigurationTests(RunnerFixture):
    def test_expected_effective_configuration_is_accepted(self):
        directory = self.prepared()
        runner.verify_effective_configuration(self.effective_entries(directory), task_dir=directory,
                                              expected=build_config("opencode/" + runner.DEFAULT_MODEL, "review"))

    def test_extra_sources_changed_permissions_agents_and_model_fail_closed(self):
        directory = self.prepared()
        original = self.effective_entries(directory)
        expected = build_config("opencode/" + runner.DEFAULT_MODEL, "review")
        cases = []
        cases.append(("extra source", original + [copy.deepcopy(original[0])]))
        outside = copy.deepcopy(original)
        outside[0]["path"] = str(self.root / "opencode.json")
        cases.append(("outside configuration", outside))
        for name, mutation in (
            ("global permissions", lambda actual: actual.update(permissions=[{"action": "*", "resource": "*", "effect": "allow"}])),
            ("global policies", lambda actual: actual.update(policies=[])),
            ("main model", lambda actual: actual.update(model={"providerID": "openai", "model": "paid"})),
            ("missing agent", lambda actual: actual["agents"].pop("sparkx-review")),
            ("added agent", lambda actual: actual["agents"].update(extra={"model": {"providerID": "opencode", "model": "paid"}})),
            ("agent permissions", lambda actual: actual["agents"]["sparkx-review"].update(permissions=[])),
            ("maintenance model", lambda actual: actual["agents"]["title"].update(model={"providerID": "opencode", "model": "paid"})),
            ("agent steps", lambda actual: actual["agents"]["sparkx-review"].update(steps=999)),
        ):
            changed = copy.deepcopy(original)
            mutation(changed[0]["info"])
            cases.append((name, changed))
        for name, entries in cases:
            with self.subTest(change=name), self.assertRaises(runner.TaskError):
                runner.verify_effective_configuration(entries, task_dir=directory, expected=expected)
        self.catalog.assert_not_called()

    def test_injected_provider_endpoint_and_mcp_configuration_are_rejected(self):
        directory = self.prepared()
        expected = build_config("opencode/" + runner.DEFAULT_MODEL, "review")
        for key, value in {
            "providers": {"opencode": {"settings": {"baseURL": "https://unapproved.example/v1"}}},
            "mcp": {"servers": {"unexpected": {"type": "local", "command": ["unapproved"]}}},
        }.items():
            with self.subTest(injected=key):
                entries = self.effective_entries(directory)
                entries[0]["info"][key] = value
                with self.assertRaises(runner.TaskError):
                    runner.verify_effective_configuration(entries, task_dir=directory, expected=expected)

    def test_preflight_stops_on_diagnostics_bad_json_or_configuration_override_without_model_call(self):
        directory = self.prepared()
        task = self.load_task(directory)
        entries = self.effective_entries(directory)
        entries[0]["info"]["policies"] = []
        for label, result in {
            "process failure": {"exit_code": 1, "stdout": "", "stderr": "", "seconds": .01},
            "diagnostics": {"exit_code": 0, "stdout": "[]", "stderr": "ignored policy warning", "seconds": .01},
            "bad JSON": {"exit_code": 0, "stdout": "not JSON", "stderr": "", "seconds": .01},
            "wrong shape": {"exit_code": 0, "stdout": "null", "stderr": "", "seconds": .01},
            "override": {"exit_code": 0, "stdout": json.dumps(entries), "stderr": "", "seconds": .01},
        }.items():
            with self.subTest(case=label), patch.object(runner, "run_bounded", return_value=result):
                with self.assertRaises(runner.TaskError):
                    runner.preflight(directory, task, runner.child_environment(directory))
        self.assertEqual(self.load_task(directory)["status"], "prepared")
        self.catalog.assert_not_called()


class TaskExecutionTests(RunnerFixture):
    def test_installation_input_changes_and_invalid_manifest_model_stop_before_inference(self):
        directory = self.prepared()
        with patch.object(runner, "installation_is_verified", return_value=False), patch.object(runner, "run_bounded") as process:
            with self.assertRaises(runner.TaskError):
                runner.run_task(directory.name)
            process.assert_not_called()
        self.assertTrue((directory / ".execution-claim").is_file())
        self.allow_mock_execution()

        directory = self.prepared()
        task = self.load_task(directory)
        (directory / task["inputs"][0]["copy"]).write_text("changed", encoding="utf-8")
        with patch.object(runner, "run_bounded") as process:
            with self.assertRaisesRegex(runner.TaskError, "cambió"):
                runner.run_task(directory.name)
            process.assert_not_called()
        self.assertTrue((directory / ".execution-claim").is_file())

        directory = self.prepared()
        task = self.load_task(directory)
        task["model"] = "paid-model"
        (directory / "task.json").write_text(json.dumps(task), encoding="utf-8")
        with patch.object(runner, "run_bounded") as process:
            with self.assertRaises(runner.TaskError):
                runner.run_task(directory.name)
            process.assert_not_called()
        self.assertTrue((directory / ".execution-claim").is_file())
        self.catalog.assert_not_called()

    def test_concurrent_executions_only_one_enters_claimed_work_and_claim_remains(self):
        directory = self.prepared()
        start = threading.Barrier(3)
        entered = threading.Event()
        release = threading.Event()

        def claimed_work(task_id):
            self.assertEqual(task_id, directory.name)
            entered.set()
            if not release.wait(timeout=5):
                raise AssertionError("The test did not release its own claimed worker")
            return {"status": "review_required", "task": task_id}

        def attempt():
            start.wait(timeout=5)
            try:
                return "completed", runner.run_task(directory.name)
            except runner.TaskError as error:
                return "blocked", str(error)

        with patch.object(runner, "_run_claimed_task", side_effect=claimed_work) as work:
            with ThreadPoolExecutor(max_workers=2) as pool:
                futures = [pool.submit(attempt), pool.submit(attempt)]
                try:
                    start.wait(timeout=5)
                    self.assertTrue(entered.wait(timeout=3))
                    completed, pending = wait(futures, timeout=3, return_when=FIRST_COMPLETED)
                    self.assertEqual(len(completed), 1, "The losing execution must return while the owner is still working")
                    self.assertEqual(len(pending), 1)
                    loser_status, loser_message = completed.pop().result()
                    self.assertEqual(loser_status, "blocked")
                    self.assertIn("reclamada", loser_message)
                    claim = directory / ".execution-claim"
                    self.assertEqual(claim.read_text(encoding="ascii"), str(os.getpid()))
                finally:
                    release.set()
                results = [future.result(timeout=5) for future in futures]
            self.assertEqual(sorted(status for status, _ in results), ["blocked", "completed"])
            self.assertTrue((directory / ".execution-claim").is_file())
            # The persistent claim must prevent a later retry even when the
            # mocked worker intentionally left task.json in prepared status.
            self.assertEqual(self.load_task(directory)["status"], "prepared")
            with self.assertRaisesRegex(runner.TaskError, "reclamada"):
                runner.run_task(directory.name)
            work.assert_called_once_with(directory.name)
        self.catalog.assert_not_called()

    def test_free_catalogue_rejection_has_no_paid_fallback_or_attempt(self):
        directory = self.prepared()
        self.allow_mock_execution()
        self.catalog.side_effect = runner.CatalogVerificationError("The selected model is no longer free")
        with patch.object(runner, "run_bounded") as process:
            with self.assertRaises(runner.CatalogVerificationError):
                runner.run_task(directory.name)
            process.assert_not_called()
        self.assertEqual(self.load_task(directory)["status"], "prepared")
        self.assertFalse((directory / "result.json").exists())
        self.assertTrue((directory / ".execution-claim").is_file())
        with self.assertRaisesRegex(runner.TaskError, "reclamada"):
            runner.run_task(directory.name)
        self.catalog.assert_called_once_with(runner.DEFAULT_MODEL)

    def test_success_requires_review_never_imports_and_cannot_run_same_task_twice(self):
        source = self.source()
        original = source.read_bytes()
        directory = self.prepared()
        self.allow_mock_execution()
        response = {"exit_code": 0, "seconds": .01, "stdout": successful_cli_response(), "stderr": ""}
        with patch.object(runner, "run_bounded", return_value=response.copy()) as process:
            report = runner.run_task(directory.name)
            self.assertEqual(report["status"], "review_required")
            self.assertFalse(report["automatic_import"])
            self.assertEqual(self.load_task(directory)["status"], "review_required")
            command = process.call_args.args[0]
            self.assertIn("--standalone", command)
            self.assertNotIn("--auto", command)
            self.assertEqual(command[command.index("--model") + 1], "opencode/" + runner.DEFAULT_MODEL)
            self.assertEqual(command[command.index("--agent") + 1], "sparkx-review")
            self.assertEqual(process.call_args.kwargs["cwd"], directory)
            self.assertTrue(process.call_args.kwargs["stop_on_model_error"])
            self.assertNotIn("OPENAI_API_KEY", process.call_args.kwargs["env"])
            self.assertEqual(report["observed_steps"], 1)
            self.assertEqual(report["observed_tokens"][0]["input"], 123)
            self.assertEqual(report["reported_cost"], [0])
            with self.assertRaises(runner.TaskError):
                runner.run_task(directory.name)
            self.assertEqual(process.call_count, 1)
        self.assertEqual(source.read_bytes(), original)
        self.assertEqual((directory / "events.jsonl").read_text(encoding="utf-8"), response["stdout"])
        self.assertEqual((directory / "outputs/respuesta.md").read_text(encoding="utf-8"), "Hallazgo de ejemplo para revisión.")
        self.catalog.assert_called_once_with(runner.DEFAULT_MODEL)

    def test_zero_exit_with_empty_or_error_events_is_failed_instead_of_false_success(self):
        for label, events in {
            "empty": "",
            "error after text": successful_cli_response() + cli_events({"type": "error", "error": {"message": "fixture error"}}),
            "retry after text": successful_cli_response() + cli_events({"type": "retry", "attempt": 1}),
            "malformed after text": successful_cli_response() + "not JSON\n",
        }.items():
            with self.subTest(case=label):
                directory = self.prepared()
                self.allow_mock_execution()
                with patch.object(runner, "run_bounded", return_value={"exit_code": 0, "seconds": .01, "stdout": events, "stderr": ""}) as process:
                    report = runner.run_task(directory.name)
                    self.assertEqual(report["status"], "failed")
                    self.assertEqual(self.load_task(directory)["status"], "failed")
                    with self.assertRaises(runner.TaskError):
                        runner.run_task(directory.name)
                    self.assertEqual(process.call_count, 1)
                self.assertFalse(report["automatic_import"])

    def test_nonzero_exit_and_runtime_error_persist_failure_without_retry(self):
        for label in ("nonzero", "timeout"):
            with self.subTest(case=label):
                directory = self.prepared()
                self.allow_mock_execution()
                self.catalog.reset_mock()
                with patch.object(runner, "run_bounded") as process:
                    if label == "nonzero":
                        process.return_value = {"exit_code": 1, "seconds": .01, "stdout": "", "stderr": "model unavailable"}
                    else:
                        process.side_effect = runner.TaskError("bounded timeout")
                    report = runner.run_task(directory.name)
                    self.assertEqual(report["status"], "failed")
                    task = self.load_task(directory)
                    self.assertEqual(task["status"], "failed")
                    self.assertIn("finished_at", task)
                    self.assertEqual(json.loads((directory / "result.json").read_text(encoding="utf-8"))["status"], "failed")
                    with self.assertRaises(runner.TaskError):
                        runner.run_task(directory.name)
                    self.assertEqual(process.call_count, 1)
                self.catalog.assert_called_once_with(runner.DEFAULT_MODEL)

    def test_input_changed_during_mock_execution_marks_result_failed(self):
        directory = self.prepared()
        task = self.load_task(directory)
        self.allow_mock_execution()

        def changed_input(*_args, **_kwargs):
            (directory / task["inputs"][0]["copy"]).write_text("modified input", encoding="utf-8")
            return {"exit_code": 0, "seconds": .01, "stdout": "", "stderr": ""}

        with patch.object(runner, "run_bounded", side_effect=changed_input):
            report = runner.run_task(directory.name)
        self.assertEqual(report["status"], "failed")
        self.assertIn("cambió", report["error"])
        self.assertEqual(self.load_task(directory)["status"], "failed")


class BoundedProcessTests(RunnerFixture):
    def process_environment(self):
        # Absolute Python executable, with only the Windows runtime fields it
        # needs. Never copy API credentials, proxy settings, or the parent PATH.
        return {name: os.environ[name] for name in ("SystemRoot", "WINDIR", "COMSPEC", "PATHEXT") if name in os.environ}

    def test_local_python_stdout_stderr_and_exit_status_are_collected(self):
        result = runner.run_bounded(
            [sys.executable, "-B", "-c", "import os,sys;os.write(1,b'local stdout');os.write(2,b'local stderr');sys.exit(3)"],
            cwd=self.root, env=self.process_environment(), seconds=5,
        )
        self.assertEqual(result["exit_code"], 3)
        self.assertEqual(result["stdout"], "local stdout")
        self.assertEqual(result["stderr"], "local stderr")
        self.assertGreaterEqual(result["seconds"], 0)
        self.catalog.assert_not_called()

    def test_only_own_sleeping_child_is_stopped_at_timeout(self):
        with self.assertRaisesRegex(runner.TaskError, "tiempo máximo"):
            runner.run_bounded([sys.executable, "-B", "-c", "import time;time.sleep(10)"],
                               cwd=self.root, env=self.process_environment(), seconds=.15)
        self.catalog.assert_not_called()

    def test_output_cap_stops_only_own_child(self):
        with patch.object(runner, "MAX_OUTPUT_BYTES", 1024):
            with self.assertRaisesRegex(runner.TaskError, "salida"):
                runner.run_bounded([sys.executable, "-B", "-c", "import os;os.write(1,b'x'*16384)"],
                                   cwd=self.root, env=self.process_environment(), seconds=5)
        self.catalog.assert_not_called()

    def test_live_retry_error_and_length_events_stop_own_child_before_long_sleep(self):
        events = {
            "retry": {"type": "retry", "attempt": 1},
            "error": {"type": "error", "error": {"message": "synthetic error"}},
            "length": {"type": "step_finish", "part": {"reason": "length", "tokens": {}, "cost": 0}},
        }
        for label, event in events.items():
            with self.subTest(event=label):
                encoded = cli_events(event).encode("utf-8")
                split = len(encoded) // 2
                code = ("import os,time;"
                        f"os.write(1,{encoded[:split]!r});time.sleep(.03);"
                        f"os.write(1,{encoded[split:]!r});time.sleep(10)")
                started = time.monotonic()
                with self.assertRaisesRegex(runner.TaskError, "error, reintento o límite"):
                    runner.run_bounded([sys.executable, "-B", "-c", code], cwd=self.root,
                                       env=self.process_environment(), seconds=5, stop_on_model_error=True)
                self.assertLess(time.monotonic() - started, 4)
        self.catalog.assert_not_called()


class CliResponseTests(unittest.TestCase):
    def test_documented_text_parts_and_step_counters_are_collected_without_executing_tools(self):
        first_tokens = {"input": 12, "output": 4, "cache": {"read": 0, "write": 0}}
        second_tokens = {"input": 15, "output": 8, "cache": {"read": 2, "write": 0}}
        events = cli_events(
            {"type": "step_start", "part": {"id": "step-1"}},
            {"type": "text", "part": {"text": "Primer hallazgo."}},
            {"type": "tool_use", "part": {"name": "shell", "input": {"command": "DO NOT EXECUTE"}}},
            {"type": "step_finish", "part": {"reason": "tool-calls", "tokens": first_tokens, "cost": 0}},
            {"type": "text", "part": {"text": "Segundo hallazgo."}},
            {"type": "step_finish", "part": {"reason": "stop", "tokens": second_tokens, "cost": 0}},
        )
        with patch.object(runner.subprocess, "Popen", side_effect=AssertionError("Parser must never execute tools")):
            result = runner.parse_response(events)
        self.assertFalse(result["error"])
        self.assertEqual(result["text"], "Primer hallazgo.\n\nSegundo hallazgo.")
        self.assertEqual(result["steps"], 2)
        self.assertEqual(result["tokens"], [first_tokens, second_tokens])
        self.assertEqual(result["cost"], [0, 0])

    def test_error_and_retry_events_fail_even_if_text_was_received(self):
        for event_type in ("error", "retry"):
            with self.subTest(event=event_type):
                result = runner.parse_response(successful_cli_response() + cli_events({"type": event_type}))
                self.assertTrue(result["error"])
                self.assertIn("Hallazgo", result["text"])

    def test_truncated_response_reason_length_is_not_complete_success(self):
        events = cli_events(
            {"type": "text", "part": {"text": "Respuesta parcial"}},
            {"type": "step_finish", "part": {"reason": "length", "tokens": {"output": 100}, "cost": 0}},
        )
        result = runner.parse_response(events)
        self.assertTrue(result["error"])
        self.assertEqual(result["text"], "Respuesta parcial")
        self.assertEqual(result["steps"], 1)

    def test_malformed_json_and_non_object_events_are_not_ignored_as_success(self):
        for malformed in ("not JSON\n", "null\n", "[]\n", "42\n", '"string"\n'):
            with self.subTest(event=malformed):
                result = runner.parse_response(successful_cli_response() + malformed)
                self.assertTrue(result["error"])

    def test_missing_blank_and_wrongly_shaped_text_cannot_produce_success(self):
        for events in (
            "", " \n\n", cli_events({"type": "text", "text": "legacy wrong shape"}),
            cli_events({"type": "text", "part": {"text": 42}}),
            successful_cli_response(""), successful_cli_response(" \n\t"),
            cli_events({"type": "step_finish", "part": {"reason": "stop", "cost": 0, "tokens": {}}}),
        ):
            with self.subTest(events=events):
                self.assertTrue(runner.parse_response(events)["error"])


if __name__ == "__main__":
    unittest.main()
