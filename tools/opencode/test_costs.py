"""Offline arithmetic and uncertainty tests for hypothetical model costs."""

from __future__ import annotations

import copy
from decimal import Decimal, localcontext
import importlib.util
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from tools.opencode.costs import (
    CostDataError, MAX_STEPS, SEMANTICS_SOURCE, TOKEN_SEMANTICS,
    default_tariffs, estimate_usage, summarize_usage,
)


def tokens(input=100, output=50, reasoning=20, read=10, write=0):
    return {"input": input, "output": output, "reasoning": reasoning, "cache": {"read": read, "write": write}}


def tariff(**rates):
    return {
        "provider": "example", "model": "example-model", "currency": "USD",
        "source": "manual:test-fixture", "verified_at": "2026-11-14",
        "rates_per_million": {"input": "1", "output": "3", "cache_read": "0.1", "cache_write": "2", **rates},
    }


class UsageSummaryTests(unittest.TestCase):
    def test_pinned_disjoint_buckets_include_reasoning_once_and_do_not_subtract_cache(self):
        summary = summarize_usage([tokens(input=10, output=50, reasoning=20, read=100, write=5)])
        self.assertEqual(summary["token_semantics"], TOKEN_SEMANTICS)
        self.assertEqual(summary["semantics_source"], SEMANTICS_SOURCE)
        self.assertEqual(summary["tokens"], {
            "input_uncached": 10, "cache_read": 100, "cache_write": 5, "output": 50, "reasoning": 20,
            "input_total": 115, "output_billable": 70, "total": 185,
        })
        self.assertTrue(summary["complete"])

    def test_multiple_steps_are_summed_without_mutating_observations(self):
        observed = [tokens(), tokens(input=7, output=2, reasoning=3, read=5, write=4)]
        before = copy.deepcopy(observed)
        summary = summarize_usage(observed)
        self.assertEqual(summary["steps"], 2)
        self.assertEqual(summary["tokens"]["input_total"], 126)
        self.assertEqual(summary["tokens"]["output_billable"], 75)
        self.assertEqual(summary["tokens"]["total"], 201)
        self.assertEqual(observed, before)

    def test_missing_bucket_stays_unknown_while_partial_subtotal_is_preserved(self):
        first, second = tokens(), tokens()
        del second["cache"]["read"]
        summary = summarize_usage([first, second])
        self.assertIsNone(summary["tokens"]["cache_read"])
        self.assertEqual(summary["known_tokens"]["cache_read"], 10)
        self.assertIsNone(summary["tokens"]["input_total"])
        self.assertIsNone(summary["tokens"]["total"])
        self.assertEqual(summary["tokens"]["output_billable"], 140)
        self.assertEqual(summary["unknown_fields"], ["cache_read"])
        self.assertFalse(summary["complete"])

    def test_absent_observations_are_unknown_and_confirmed_zeros_remain_zero(self):
        for observed in (None, [], [None], [{}]):
            with self.subTest(observed=observed):
                summary = summarize_usage(observed)
                self.assertIsNone(summary["tokens"]["total"])
                self.assertFalse(summary["complete"])
        confirmed = summarize_usage([tokens(0, 0, 0, 0, 0)])
        self.assertEqual(confirmed["tokens"]["total"], 0)
        self.assertTrue(confirmed["complete"])

    def test_non_integer_negative_and_boolean_counters_are_invalid(self):
        for field in ("input", "output", "reasoning", "read", "write"):
            for invalid in (True, False, -1, 1.0, "1", Decimal("1"), []):
                with self.subTest(field=field, value=invalid):
                    with self.assertRaises(CostDataError):
                        summarize_usage([tokens(**{field: invalid})])

    def test_malformed_or_unbounded_step_structures_are_invalid(self):
        for invalid in (tokens(), "text", ["text"], [True], [{"cache": []}], [None] * (MAX_STEPS + 1)):
            with self.subTest(value=type(invalid).__name__):
                with self.assertRaises(CostDataError):
                    summarize_usage(invalid)


class HypotheticalCostTests(unittest.TestCase):
    def test_exact_formula_prices_visible_output_and_reasoning_once(self):
        result = estimate_usage([tokens()], tariff())
        # (100*1 + 10*.1 + 0*2 + (50+20)*3) / 1M = .000311
        self.assertEqual(result["hypothetical_cost"], {
            "input_uncached": "0.0001", "cache_read": "0.000001", "cache_write": "0",
            "output": "0.00021", "total": "0.000311", "known_subtotal": "0.000311",
        })
        self.assertEqual(result["scenario"], "hypothetical")
        self.assertTrue(result["complete"])
        self.assertIn("No representa un gasto realizado", " ".join(result["warnings"]))

    def test_missing_price_and_missing_usage_are_not_invented_as_free(self):
        for observed, rates, expected_field in (
            ([tokens(write=2)], {"cache_write": None}, "cache_write"),
            ([tokens(read=10)], {"cache_read": None}, "cache_read"),
            ([tokens(input=None)], {}, "input_uncached"),
            ([tokens(reasoning=None)], {}, "output"),
            ([tokens(input=None)], {"input": "0"}, "input_uncached"),
        ):
            with self.subTest(field=expected_field, rates=rates):
                result = estimate_usage(observed, tariff(**rates))
                self.assertIsNone(result["hypothetical_cost"][expected_field])
                self.assertIsNone(result["hypothetical_cost"]["total"])
                self.assertFalse(result["complete"])
        absent = estimate_usage(None, tariff())
        self.assertTrue(all(value is None for value in absent["hypothetical_cost"].values()))

    def test_known_zero_cache_writes_need_no_unknown_write_tariff(self):
        result = estimate_usage([tokens(write=0)], tariff(cache_write=None))
        self.assertEqual(result["hypothetical_cost"]["cache_write"], "0")
        self.assertEqual(result["hypothetical_cost"]["total"], "0.000311")
        self.assertTrue(result["complete"])

    def test_all_missing_prices_preserve_unknown_components_except_known_zero_usage(self):
        unknown = tariff()
        unknown["rates_per_million"] = {}
        result = estimate_usage([tokens(write=2)], unknown)
        self.assertIsNone(result["hypothetical_cost"]["total"])
        self.assertIsNone(result["hypothetical_cost"]["known_subtotal"])

    def test_float_boolean_nonfinite_negative_and_excessive_exponent_rates_are_rejected(self):
        for invalid in (True, False, .1, "NaN", "Infinity", Decimal("-Infinity"), "-0.1", "bad", "1e101", []):
            with self.subTest(rate=invalid):
                with self.assertRaises(CostDataError):
                    estimate_usage([tokens()], tariff(input=invalid))

    def test_metadata_and_currency_are_required_without_guessing_provider_or_date(self):
        for field in ("provider", "model", "currency", "source", "verified_at"):
            with self.subTest(field=field):
                incomplete = tariff()
                del incomplete[field]
                with self.assertRaises(CostDataError):
                    estimate_usage([tokens()], incomplete)
        for overrides in ({"verified_at": "2026-13-99"}, {"currency": "usd"}, {"source": " "}, {"rates_per_million": {"unexpected_tool_fee": "1"}}):
            with self.subTest(overrides=overrides):
                with self.assertRaises(CostDataError):
                    estimate_usage([tokens()], {**tariff(), **overrides})

    def test_exact_decimal_arithmetic_does_not_round_large_counts_or_subcent_prices(self):
        count = 2**80 + 1
        rate = Decimal("0.123456789123456789")
        result = estimate_usage([tokens(input=count, output=0, reasoning=0, read=0, write=0)], tariff(input=rate))
        with localcontext() as context:
            context.prec = 80
            expected = Decimal(count) * rate / Decimal(1_000_000)
        self.assertEqual(Decimal(result["hypothetical_cost"]["total"]), expected)
        self.assertNotIn("E", result["hypothetical_cost"]["total"])

    def test_supplied_context_tiers_are_not_silently_ignored(self):
        selected = {**tariff(), "context_tiers": [{"above_input_tokens": 200000, "input": "2"}]}
        result = estimate_usage([tokens()], selected)
        self.assertFalse(result["complete"])
        self.assertFalse(result["tariff"]["context_tiers_supported"])
        self.assertTrue(all(value is None for value in result["hypothetical_cost"].values()))
        self.assertIn("niveles de contexto", " ".join(result["warnings"]))

    def test_estimates_are_json_serializable_and_do_not_mutate_inputs_or_tariff(self):
        observed, selected = [tokens()], tariff()
        before = copy.deepcopy((observed, selected))
        result = estimate_usage(observed, selected)
        serialized = json.loads(json.dumps(result))
        self.assertIsInstance(serialized["hypothetical_cost"]["total"], str)
        self.assertEqual((observed, selected), before)


class SnapshotAndImportTests(unittest.TestCase):
    def test_three_dated_public_snapshots_have_independent_nested_values_and_unknown_write_prices(self):
        first = default_tariffs()
        self.assertEqual([entry["model"] for entry in first], ["glm-5.3-flash", "deepseek-v4.1-flash", "minimax-m3"])
        expected = [("0.15", "0.50", "0.03"), ("0.30", "1.20", "0.006"), ("0.30", "1.20", "0.06")]
        for entry, prices in zip(first, expected):
            self.assertEqual(entry["verified_at"], "2026-11-14")
            self.assertEqual(entry["source"], "https://opencode.ai/docs/console/models/")
            self.assertEqual(entry["currency"], "USD")
            self.assertEqual(entry["rates_per_million"], dict(zip(("input", "output", "cache_read", "cache_write"), (*prices, None))))
        self.assertIn("diferente", first[2]["model_difference_note"])
        first[0]["rates_per_million"]["input"] = "999"
        self.assertEqual(default_tariffs()[0]["rates_per_million"]["input"], "0.15")

    def test_same_counters_produce_counterfactual_prices_without_claiming_same_model(self):
        observed = [tokens(input=3451, output=799, reasoning=257, read=2176, write=0)]
        expected = ["0.00111093", "0.002315556", "0.00243306"]
        for selected, total in zip(default_tariffs(), expected):
            result = estimate_usage(observed, selected)
            self.assertEqual(result["hypothetical_cost"]["total"], total)
            self.assertEqual(result["usage"]["tokens"]["total"], 6683)
            self.assertEqual(result["scenario"], "hypothetical")
            self.assertIn("cambiar de modelo", " ".join(result["warnings"]))

    def test_fresh_module_import_and_helpers_do_not_open_files_network_or_processes(self):
        path = Path(__file__).with_name("costs.py")
        spec = importlib.util.spec_from_file_location("isolated_opencode_costs", path)
        module = importlib.util.module_from_spec(spec)
        # The import loader itself reads its source through importlib's own
        # mechanism. Guard application I/O and subprocess/network entry points.
        with patch("builtins.open", side_effect=AssertionError("No file I/O")), patch("urllib.request.urlopen", side_effect=AssertionError("No network")), patch("subprocess.Popen", side_effect=AssertionError("No process")):
            spec.loader.exec_module(module)
            summary = module.summarize_usage([tokens()])
            result = module.estimate_usage([tokens()], module.default_tariffs()[0])
        self.assertEqual(summary["tokens"]["total"], 180)
        self.assertEqual(result["scenario"], "hypothetical")


if __name__ == "__main__":
    unittest.main()
