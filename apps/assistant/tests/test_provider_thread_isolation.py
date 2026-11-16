"""Thread-local model/usage isolation through the actual provider entry point."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from threading import Barrier
from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase

from apps.assistant import provider
from apps.assistant.free_harness import FreeHarnessError

A, B = "glm-5.3-flash-free", "deepseek-v4.1-flash-free"


def profile(model):
    return {"provider": "opencode", "model": model, "mode": "free",
            "max_input_tokens": 24000, "max_output_tokens": 2048}


def event(model):
    return SimpleNamespace(is_synthetic=True, _free_context_snapshot={
        "source_model": model, "action": "chat", "prompt": "synthetic " + model,
        "context": {"sentinel": model}, "instructions": "Synthetic response only.",
    })


class ProviderThreadIsolationTests(SimpleTestCase):
    def test_concurrent_profiles_prompts_and_counters_remain_on_their_own_threads(self):
        barrier = Barrier(2)

        def bridge(**kwargs):
            model = kwargs["model"]
            barrier.wait(timeout=5)
            self.assertEqual(provider._configuration()["model"], model)
            self.assertEqual(kwargs["context"]["sentinel"], model)
            kwargs["context"]["sentinel"] = "modified only in bridge copy"
            number = 3 if model == A else 7
            return {"text": model, "usage": {"input_tokens": number, "output_tokens": 1, "total_tokens": number + 1}}

        def task(model):
            item = event(model)
            original = deepcopy(item._free_context_snapshot)
            with provider.use_profile(profile(model)):
                text = provider.answer_question(event=item, prompt="synthetic " + model)
                usage = provider.pop_usage()
            self.assertEqual(item._free_context_snapshot, original)
            self.assertIsNone(provider._profile.get())
            return text, usage

        with patch("apps.assistant.free_harness.run_free_harness", side_effect=bridge), ThreadPoolExecutor(max_workers=2) as executor:
            first, second = executor.submit(task, A), executor.submit(task, B)
            self.assertEqual(first.result(timeout=10), (A, {"input_tokens": 3, "output_tokens": 1, "total_tokens": 4}))
            self.assertEqual(second.result(timeout=10), (B, {"input_tokens": 7, "output_tokens": 1, "total_tokens": 8}))
        self.assertIsNone(provider._profile.get())

    def test_quota_failure_does_not_leak_profile_or_usage_into_next_call_on_same_thread(self):
        with provider.use_profile(profile(A)), patch("apps.assistant.free_harness.run_free_harness",
                side_effect=FreeHarnessError("Synthetic quota", usage={"input_tokens": 9}, http_status=429)):
            with self.assertRaises(provider.FreeQuotaUnavailable):
                provider.answer_question(event=event(A), prompt="synthetic " + A)
        self.assertIsNone(provider._profile.get())
        with provider.use_profile(profile(B)), patch("apps.assistant.free_harness.run_free_harness",
                return_value={"text": "Synthetic answer B", "usage": {"input_tokens": 2, "output_tokens": 1, "total_tokens": 3}}):
            self.assertEqual(provider.answer_question(event=event(B), prompt="synthetic " + B), "Synthetic answer B")
            self.assertEqual(provider.pop_usage(), {"input_tokens": 2, "output_tokens": 1, "total_tokens": 3})
        self.assertEqual(provider.pop_usage(), {})
