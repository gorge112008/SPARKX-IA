"""Checks of the generated policy document, not proof of runtime isolation.

OpenCode's pinned binary must also load and report the expected effective
configuration.  These checks intentionally perform no inference or network I/O.
"""

from __future__ import annotations

import json
import re
import unittest

from tools.opencode.configuration import MAX_AGENT_STEPS, MAX_OUTPUT_TOKENS, build_config


MODEL = "opencode/fixture-free"


def _matches(value: str, pattern: str, *, windows: bool = False) -> bool:
    """Apply the documented whole-value '*'/'?' syntax to policy fixtures."""
    if windows:
        value = value.replace("\\", "/").lower()
        pattern = pattern.replace("\\", "/").lower()
    expression = re.escape(pattern).replace(r"\*", ".*").replace(r"\?", ".")
    return re.fullmatch(expression, value, flags=re.DOTALL) is not None


def _tool_decision(config: dict, agent: str, action: str, resource: str) -> str:
    """Evaluate declared rules only; do not emulate paths or OpenCode tools."""
    decision = "ask"
    rules = config["permissions"] + config["agents"][agent]["permissions"]
    for rule in rules:
        if _matches(action, rule["action"]) and _matches(
            resource, rule["resource"], windows=True
        ):
            decision = rule["effect"]
    # tool.use policies only tighten decisions.  They never authorize a tool.
    policy = _policy_decision(config, "tool.use", action + ":" + resource)
    return "deny" if policy == "deny" else decision


def _policy_decision(config: dict, action: str, resource: str) -> str:
    decision = "allow"
    for policy in config["policies"]:
        if policy["action"] == action and _matches(resource, policy["resource"]):
            decision = policy["effect"]
    return decision


class ConfigurationTests(unittest.TestCase):
    def test_unknown_tools_and_unknown_paths_are_denied(self):
        for mode in ("review", "draft"):
            config = build_config(MODEL, mode)
            agent = config["default_agent"]
            for action, resource in (
                ("new_plugin_action", "*"),
                ("read", "AGENTS.md"),
                ("read", ".env"),
                ("read", "var/db.sqlite3"),
                ("read", "C:/Users/JORGE/.aws/credentials"),
                ("edit", "apps/events/views.py"),
                ("edit", "../outside.txt"),
            ):
                with self.subTest(mode=mode, action=action, resource=resource):
                    self.assertEqual(
                        _tool_decision(config, agent, action, resource), "deny"
                    )

    def test_review_can_read_prepared_inputs_but_never_edit(self):
        config = build_config(MODEL, "review")
        for path in ("inputs/source.py", "inputs/nested/context.txt", "INPUTS\\code.py"):
            with self.subTest(path=path):
                self.assertEqual(
                    _tool_decision(config, "sparkx-review", "read", path), "allow"
                )
                self.assertEqual(
                    _tool_decision(config, "sparkx-review", "edit", path), "deny"
                )
        self.assertEqual(
            _tool_decision(config, "sparkx-review", "read", "outputs/draft.py"),
            "deny",
        )
        self.assertEqual(
            _tool_decision(config, "sparkx-review", "edit", "outputs/draft.py"),
            "deny",
        )

    def test_review_policy_blocks_switching_to_draft_agent(self):
        config = build_config(MODEL, "review")
        self.assertEqual(
            _tool_decision(config, "sparkx-draft", "edit", "outputs/draft.py"),
            "deny",
        )

    def test_draft_can_write_only_disposable_outputs(self):
        config = build_config(MODEL, "draft")
        for action in ("read", "edit"):
            self.assertEqual(
                _tool_decision(config, "sparkx-draft", action, "outputs/draft.py"),
                "allow",
            )
        for path in ("inputs/source.py", "outputs-neighbor/a.py", "C:/outside/a.py"):
            with self.subTest(path=path):
                self.assertEqual(
                    _tool_decision(config, "sparkx-draft", "edit", path), "deny"
                )
        self.assertEqual(
            _tool_decision(config, "sparkx-review", "edit", "outputs/draft.py"),
            "deny",
        )

    def test_dangerous_actions_hard_denied_despite_agent_override(self):
        for mode in ("review", "draft"):
            config = build_config(MODEL, mode)
            agent = config["default_agent"]
            # A future accidental role grant must not lift these hard policies.
            config["agents"][agent]["permissions"].append(
                {"action": "*", "resource": "*", "effect": "allow"}
            )
            for action, resource in (
                ("shell", "python -c arbitrary"),
                ("external_directory", "C:/Users/*"),
                ("execute", "*"),
                ("browser", "*"),
                ("webfetch", "https://example.com"),
                ("websearch", "query"),
                ("subagent", "general"),
                ("skill", "new-skill"),
                ("glob", "../*"),
                ("grep", ".*"),
                ("opencode_list_mcp_resources", "server"),
                ("opencode_read_mcp_resource", "server:uri"),
            ):
                with self.subTest(mode=mode, action=action):
                    self.assertEqual(
                        _tool_decision(config, agent, action, resource), "deny"
                    )

    def test_only_signed_out_opencode_provider_and_integration_allowed(self):
        config = build_config(MODEL, "review")
        self.assertEqual(_policy_decision(config, "provider.use", "opencode"), "allow")
        self.assertEqual(_policy_decision(config, "integration.use", "opencode"), "allow")
        for provider in ("openai", "anthropic", "google", "opencode-paid", "new"):
            with self.subTest(provider=provider):
                self.assertEqual(
                    _policy_decision(config, "provider.use", provider), "deny"
                )
        for integration in ("openai", "opencode#personal", "opencode#org_123", "new"):
            with self.subTest(integration=integration):
                self.assertEqual(
                    _policy_decision(config, "integration.use", integration), "deny"
                )
        self.assertEqual(
            _policy_decision(config, "integration.connect", "opencode"), "deny"
        )

    def test_external_extensions_cannot_add_a_capability(self):
        config = build_config(MODEL, "draft")
        for action in ("mcp.use", "plugin.use", "skill.use", "websearch.use"):
            with self.subTest(action=action):
                self.assertEqual(_policy_decision(config, action, "new-extension"), "deny")
        self.assertEqual(config["plugins"], [])
        self.assertEqual(config["mcp"], {"servers": {}})
        self.assertEqual(config["skills"], [])

    def test_maintenance_and_work_agents_pin_the_same_model(self):
        config = build_config(MODEL, "draft")
        self.assertEqual(config["model"], MODEL)
        for agent_id, agent in config["agents"].items():
            with self.subTest(agent=agent_id):
                self.assertEqual(agent["model"], MODEL)
                self.assertLessEqual(agent["steps"], MAX_AGENT_STEPS)
        for agent_id in ("title", "summary", "compaction"):
            self.assertEqual(config["agents"][agent_id]["steps"], 1)
            self.assertEqual(
                _tool_decision(config, agent_id, "read", "inputs/source.py"), "deny"
            )
        for agent_id in ("build", "plan", "general", "explore"):
            self.assertIs(config["agents"][agent_id]["disabled"], True)

    def test_selected_model_output_override_preserves_catalog_capacity_and_prices(self):
        config = build_config(MODEL, "review")
        self.assertEqual(
            config["providers"],
            {"opencode": {"models": {"fixture-free": {"limit": {"output": 2048}}}}},
        )
        self.assertEqual(MAX_OUTPUT_TOKENS, 2048)
        override = config["providers"]["opencode"]["models"]["fixture-free"]
        self.assertNotIn("cost", override)
        self.assertNotIn("context", override["limit"])
        self.assertNotIn("input", override["limit"])
        self.assertNotIn("settings", override)

    def test_background_inference_sharing_and_command_automation_disabled(self):
        config = build_config(MODEL, "review")
        self.assertEqual(config["share"], "disabled")
        self.assertEqual(config["update"], "disable")
        for setting in ("warming", "snapshots", "lsp", "formatter", "websearch"):
            self.assertIs(config[setting], False)
        self.assertIs(config["compaction"]["auto"], False)
        self.assertIs(config["experimental"]["background_compaction"], False)
        self.assertEqual(config["experimental"]["subagent_depth"], 0)
        self.assertEqual(config["commands"], {})
        self.assertEqual(config["references"], {})
        self.assertEqual(config["instructions"], [])

    def test_invalid_modes_and_ambiguous_model_references_fail(self):
        for mode in (None, "build", "", "REVIEW"):
            with self.subTest(mode=mode), self.assertRaises(ValueError):
                build_config(MODEL, mode)
        for model in (
            None,
            "",
            "openai/free-model",
            "opencode/",
            "opencode/a/b",
            "opencode/a#paid",
            "opencode/*",
            "opencode/model\n",
            "opencode/" + "a" * 129,
        ):
            with self.subTest(model=model), self.assertRaises(ValueError):
                build_config(model, "review")

    def test_documents_are_serializable_and_independent_between_runs(self):
        first = build_config(MODEL, "draft")
        second = build_config(MODEL, "draft")
        self.assertEqual(json.loads(json.dumps(first)), first)
        first["agents"]["sparkx-draft"]["permissions"].clear()
        first["policies"].clear()
        self.assertTrue(second["agents"]["sparkx-draft"]["permissions"])
        self.assertTrue(second["policies"])


if __name__ == "__main__":
    unittest.main()
