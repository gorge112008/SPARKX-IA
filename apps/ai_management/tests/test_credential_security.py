"""Private transport and DEBUG redaction; synthetic strings and no network/DB."""
import sys

from django.core.exceptions import PermissionDenied
from django.test import RequestFactory, SimpleTestCase, override_settings

from apps.ai_management.credential_security import (
    AlwaysActiveCredentialFilter, force_redact_request, require_private_transport,
)


@override_settings(DEBUG=True, ALLOWED_HOSTS=["localhost", "127.0.0.1", "[::1]", "portal.example"],
                   SECURE_PROXY_SSL_HEADER=None)
class CredentialTransportTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()

    def request(self, *, host="localhost:8000", peer="127.0.0.1", port="8000", secure=False, **headers):
        return self.factory.post("/ai/private/", {}, HTTP_HOST=host, REMOTE_ADDR=peer,
                                 SERVER_PORT=port, secure=secure, **headers)

    def test_direct_loopback_accepts_only_matching_host_and_port(self):
        for host, peer, port in (("localhost:8000", "127.0.0.1", "8000"),
                                 ("127.0.0.1:8000", "127.0.0.1", "8000"),
                                 ("[::1]:8000", "::1", "8000"),
                                 ("localhost", "127.0.0.1", "80")):
            with self.subTest(host=host):
                self.assertIsNone(require_private_transport(self.request(host=host, peer=peer, port=port)))

    def test_allowed_remote_https_succeeds_without_claiming_loopback(self):
        self.assertIsNone(require_private_transport(self.request(host="portal.example", peer="192.0.2.4", port="443", secure=True)))

    def test_remote_plaintext_wrong_ports_invalid_peers_or_hosts_are_denied(self):
        cases = [{"peer": "192.0.2.4"}, {"host": "portal.example:8000"},
                 {"host": "localhost:8001"}, {"host": "localhost"},
                 {"peer": ""}, {"peer": "127.0.0.1.attacker.example"},
                 {"port": "invalid"}, {"port": "65536"},
                 {"host": "untrusted.example", "secure": True}]
        for values in cases:
            with self.subTest(values=values), self.assertRaises(PermissionDenied):
                require_private_transport(self.request(**values))

    def test_proxy_headers_never_convert_plain_http_to_local(self):
        for name, value in (("HTTP_FORWARDED", "for=127.0.0.1"), ("HTTP_VIA", "proxy"),
                            ("HTTP_X_FORWARDED_FOR", "127.0.0.1"),
                            ("HTTP_X_FORWARDED_PROTO", "https"),
                            ("HTTP_X_FORWARDED_HOST", "localhost:8000")):
            with self.subTest(header=name), self.assertRaises(PermissionDenied):
                require_private_transport(self.request(**{name: value}))

    @override_settings(DEBUG=False)
    def test_production_requires_https_even_on_loopback(self):
        with self.assertRaises(PermissionDenied):
            require_private_transport(self.request())
        self.assertIsNone(require_private_transport(self.request(host="portal.example", secure=True, port="443")))


@override_settings(DEBUG=True)
class CredentialRedactionTests(SimpleTestCase):
    def setUp(self):
        self.marker = "synthetic-private-" + "never-render-this-value"
        self.request = RequestFactory().post("/ai/private/", {"api_key": self.marker,
                                                             "unexpected_alias": self.marker})

    def test_all_fields_are_redacted_in_debug_without_mutating_live_post(self):
        force_redact_request(self.request)
        filter_ = self.request.exception_reporter_filter
        self.assertTrue(filter_.is_active(self.request))
        self.assertIsInstance(filter_, AlwaysActiveCredentialFilter)
        self.assertEqual(set(filter_.get_post_parameters(self.request).values()), {filter_.cleansed_substitute})
        self.assertEqual(self.request.POST["api_key"], self.marker)
        self.assertEqual(self.request.sensitive_post_parameters, "__ALL__")

    def test_debug_html_and_text_omit_post_locals_and_exception_message(self):
        force_redact_request(self.request)
        def controlled_failure(value):
            arbitrary_alias = {"unlabelled": value}
            raise ValueError(arbitrary_alias)
        try:
            controlled_failure(self.marker)
        except ValueError:
            reporter = self.request.exception_reporter_class(self.request, *sys.exc_info())
            for report in (reporter.get_traceback_text(), reporter.get_traceback_html()):
                self.assertNotIn(self.marker, report)
                self.assertIn("Error al procesar la credencial privada", report)

    def test_redaction_is_scoped_to_one_request(self):
        force_redact_request(self.request)
        other = RequestFactory().post("/ordinary/", {"name": "Public value"})
        self.assertFalse(hasattr(other, "exception_reporter_filter"))
        self.assertFalse(hasattr(other, "sensitive_post_parameters"))
