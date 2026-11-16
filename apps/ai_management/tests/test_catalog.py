"""Reviewed tariffs and cache semantics; no accounts, credentials or network."""
from datetime import date
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import SimpleTestCase

from apps.ai_management.catalog import CATALOG, catalog_entry
from apps.ai_management.models import AIProfile
from apps.ai_management.services import profile_snapshot


class ReviewedMiniTests(SimpleTestCase):
    def profile(self, preset):
        entry = catalog_entry(preset)
        return AIProfile(**{name: entry[name] for name in (
            "name", "provider", "model", "mode", "input_rate", "cached_rate",
            "output_rate", "verified_on", "source_url",
        )})

    def test_mini_keeps_standard_gross_tariffs_and_only_its_own_review_date(self):
        entry = catalog_entry("openai_54_mini")
        self.assertEqual(entry["mode"], "paid")
        self.assertEqual((entry["input_rate"], entry["cached_rate"], entry["output_rate"]),
                         (Decimal("0.75"), Decimal("0.075"), Decimal("4.50")))
        self.assertEqual(entry["verified_on"], date(2026, 11, 12))
        opencode = {key for key, value in CATALOG.items() if value["provider"] == "opencode"}
        for key in opencode:
            self.assertEqual(catalog_entry(key)["verified_on"], date(2026, 11, 15))
        for key in CATALOG.keys() - opencode - {"openai_54_mini"}:
            with self.subTest(preset=key):
                self.assertEqual(catalog_entry(key)["verified_on"], date(2026, 11, 9))

    def test_free_presets_have_matching_provider_financial_and_harness_allowlists(self):
        from apps.assistant import provider, free_harness
        from apps.ai_management.catalog import OPENCODE_DEMO_MODELS, preset_for
        from tools.opencode.catalog import MODEL_POLICIES
        expected = set(MODEL_POLICIES) - {"nemotron-3-ultra-free"}
        self.assertEqual(len(expected), 12)
        self.assertEqual(OPENCODE_DEMO_MODELS,expected)
        self.assertEqual(provider._MODELS["opencode"],expected)
        self.assertEqual(free_harness.OPENCODE_DEMO_MODELS,expected)
        for preset in (key for key, value in CATALOG.items() if value["provider"] == "opencode"):
            profile=self.profile(preset)
            profile.free_tier_confirmed=True
            profile.max_output_tokens=2048
            snapshot=profile_snapshot(profile)
            self.assertEqual(snapshot["model"],CATALOG[preset]["model"])
            self.assertEqual(snapshot["input_rate"],"0")
            self.assertEqual(preset_for(profile),preset)

    def test_immutable_snapshot_distinguishes_mini_auto_cache_from_luna_disabled(self):
        mini = profile_snapshot(self.profile("openai_54_mini"))
        luna = profile_snapshot(self.profile("openai_luna"))
        self.assertEqual(mini["cache_policy"], "provider")
        self.assertEqual(luna["cache_policy"], "disabled")
        self.assertEqual(mini["verified_on"], "2026-11-12")
        self.assertEqual(luna["verified_on"], "2026-11-09")

    def test_sharing_incentive_cannot_be_configured_as_a_free_openai_profile(self):
        profile = self.profile("openai_54_mini")
        profile.mode = "free"
        profile.free_tier_confirmed = True
        profile.input_rate = profile.cached_rate = profile.output_rate = Decimal("0")
        with self.assertRaises(ValidationError) as caught:
            profile_snapshot(profile)
        self.assertEqual(caught.exception.code, "ai_not_configured")
