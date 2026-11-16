import io
import json
from types import SimpleNamespace
from unittest.mock import patch
from urllib.error import HTTPError, URLError

from django.test import SimpleTestCase, override_settings

from apps.assistant import provider


@override_settings(OPENAI_API_KEY="test-only-key", OPENAI_MODEL="test-model",
                   AI_HTTP_TIMEOUT_SECONDS=3, AI_MAX_OUTPUT_TOKENS=100)
class ProviderTests(SimpleTestCase):
    def setUp(self):
        provider.pop_usage()
        self.event = SimpleNamespace(
            title="Evento de prueba", brief="Datos de prueba, no un evento real",
            starts_at=None, timezone="America/Lima", capacity=20,
            revision=1, active_plan_id=None, interview_answers={},
        )

    def response(self, text, **changes):
        data = {"status": "completed", "output": [
            {"type": "message", "content": [{"type": "output_text", "text": text}]}
        ], "usage": {"input_tokens": 10, "output_tokens": 20, "total_tokens": 30}}
        data.update(changes)
        return io.BytesIO(json.dumps(data).encode())

    @override_settings(OPENAI_API_KEY="")
    @patch("apps.assistant.provider._opener.open")
    def test_missing_key_never_calls_network(self, remote):
        with self.assertRaises(provider.ProviderUnavailable):
            provider.generate_plan(event=self.event, prompt="Preparar")
        remote.assert_not_called()

    @patch("apps.assistant.provider._opener.open")
    def test_structured_payload_and_observed_usage(self, remote):
        expected = {"title": "Prueba", "summary": "Sin fecha confirmada",
                    "sessions": [], "tasks": [], "risks": ["Falta fecha"]}
        remote.return_value = self.response(json.dumps(expected))
        self.assertEqual(provider.generate_plan(event=self.event, prompt="Preparar"), expected)
        req = remote.call_args.args[0]
        sent = json.loads(req.data)
        self.assertEqual(req.full_url, provider.ENDPOINT)
        self.assertFalse(sent["store"])
        self.assertTrue(sent["text"]["format"]["strict"])
        self.assertNotIn("tools", sent)
        self.assertEqual(provider.pop_usage()["total_tokens"], 30)
        self.assertEqual(provider.pop_usage(), {})

    @patch("apps.assistant.provider._opener.open")
    def test_http_failure_does_not_expose_remote_body_or_key(self, remote):
        remote.side_effect = HTTPError(provider.ENDPOINT, 401, "secret-body", {}, None)
        with self.assertRaises(provider.ProviderUnavailable) as failure:
            provider.generate_plan(event=self.event, prompt="Preparar")
        self.assertNotIn("secret-body", str(failure.exception))
        self.assertNotIn("test-only-key", str(failure.exception))

    @patch("apps.assistant.provider._opener.open")
    def test_timeout_and_network_errors_are_safe(self, remote):
        for exception in [TimeoutError(), URLError("private connection data")]:
            with self.subTest(exception=exception):
                remote.side_effect = exception
                with self.assertRaises(provider.ProviderUnavailable):
                    provider.generate_plan(event=self.event, prompt="Preparar")

    @patch("apps.assistant.provider._opener.open")
    def test_incomplete_retains_observed_usage(self, remote):
        remote.return_value = self.response("", status="incomplete")
        with self.assertRaises(provider.ProviderError):
            provider.generate_plan(event=self.event, prompt="Preparar")
        self.assertEqual(provider.pop_usage()["input_tokens"], 10)

    @patch("apps.assistant.provider._opener.open")
    def test_refusal_is_not_treated_as_plan(self, remote):
        remote.return_value = self.response("", output=[
            {"type": "message", "content": [{"type": "refusal", "refusal": "No"}]}
        ])
        with self.assertRaises(provider.ProviderError):
            provider.generate_plan(event=self.event, prompt="Preparar")

    @patch("apps.assistant.provider._opener.open")
    def test_bad_json_and_non_object_plan_are_rejected(self, remote):
        for text in ["not-json", "[]", '{"bad":NaN}']:
            with self.subTest(text=text):
                remote.return_value = self.response(text)
                with self.assertRaises(provider.ProviderError):
                    provider.generate_plan(event=self.event, prompt="Preparar")

    @patch("apps.assistant.provider._opener.open")
    def test_oversized_reply_is_rejected(self, remote):
        remote.return_value = io.BytesIO(b"x" * (provider.MAX_RESPONSE_BYTES + 1))
        with self.assertRaises(provider.ProviderError):
            provider.generate_plan(event=self.event, prompt="Preparar")

    @patch("apps.assistant.provider._opener.open")
    def test_usage_does_not_leak_to_later_failed_request(self, remote):
        remote.return_value = self.response("{}")
        provider.generate_plan(event=self.event, prompt="Preparar")
        remote.side_effect = URLError("failure")
        with self.assertRaises(provider.ProviderError):
            provider.generate_plan(event=self.event, prompt="Preparar")
        self.assertEqual(provider.pop_usage(), {})

    def test_redirects_are_refused_before_forwarding_credentials(self):
        req = provider.request.Request(provider.ENDPOINT, headers={"Authorization": "Bearer test"})
        redirect = provider._NoRedirect().redirect_request(
            req, None, 302, "Found", {}, "https://another-origin.invalid/"
        )
        self.assertIsNone(redirect)
