"""Local web shutdown requires an owned runtime and an explicit trusted action."""

import errno
import http.client
import io
import socket
import threading
import time
from html.parser import HTMLParser
from unittest.mock import Mock, patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.core import signing
from django.core.exceptions import PermissionDenied
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import Client, RequestFactory, SimpleTestCase, TestCase, override_settings
from django.urls import reverse

from apps.accounts.models import PortalAccount
from config.local_runtime import LocalRuntime, local_shutdown_available


FAST_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
TOKEN_SALT = "sparkx.local-shutdown"


class _ElementCollector(HTMLParser):
    def __init__(self):
        super().__init__()
        self.elements = []

    def handle_starttag(self, tag, attrs):
        self.elements.append((tag, dict(attrs)))


@override_settings(DEBUG=True)
class LocalRuntimeAvailabilityTests(SimpleTestCase):
    def setUp(self):
        self.runtime = LocalRuntime(8000)
        self.factory = RequestFactory()
        self.user = get_user_model()(pk=7, username="local-owner", is_active=True, is_superuser=True)
        self.runtime_patch = patch("config.local_runtime._runtime", self.runtime)
        self.runtime_patch.start()
        self.addCleanup(self.runtime_patch.stop)

    def request(self, **meta):
        request = self.factory.get("/local/shutdown/", HTTP_HOST="127.0.0.1:8000", REMOTE_ADDR="127.0.0.1", **meta)
        request.user = self.user
        return request

    def test_shutdown_only_marks_its_own_runtime_and_is_idempotent(self):
        unrelated = LocalRuntime(8001)
        self.assertFalse(self.runtime.stop_requested.is_set())
        self.runtime.request_shutdown()
        self.runtime.request_shutdown()
        self.assertTrue(self.runtime.stop_requested.is_set())
        self.assertFalse(unrelated.stop_requested.is_set())

    def test_completion_is_separate_from_request_and_stream_registration_is_idempotent(self):
        self.assertFalse(self.runtime.shutdown_succeeded)
        self.assertFalse(self.runtime.shutdown_complete.is_set())
        self.assertEqual(self.runtime.shutdown_stream_ids(), set())
        self.runtime.register_shutdown_stream()
        self.assertIn(threading.get_ident(), self.runtime.shutdown_stream_ids())
        self.runtime.request_shutdown()
        self.assertFalse(self.runtime.shutdown_complete.is_set())
        self.assertFalse(self.runtime.shutdown_succeeded)
        self.runtime.unregister_shutdown_stream()
        self.runtime.unregister_shutdown_stream()
        self.assertEqual(self.runtime.shutdown_stream_ids(), set())

    def test_loopback_owner_is_available_without_touching_database(self):
        self.assertTrue(local_shutdown_available(self.request()))
        request = self.request()
        request.META["HTTP_HOST"] = "localhost:8000"
        self.assertTrue(local_shutdown_available(request))

    def test_default_http_port_allows_the_browser_host_without_a_port(self):
        with patch("config.local_runtime._runtime", LocalRuntime(80)):
            for host in ("127.0.0.1", "localhost", "127.0.0.1:80", "localhost:80"):
                request = self.request()
                request.META["HTTP_HOST"] = host
                with self.subTest(host=host):
                    self.assertTrue(local_shutdown_available(request))

    def test_feature_is_absent_without_owned_runtime_or_outside_debug(self):
        with patch("config.local_runtime._runtime", None):
            self.assertFalse(local_shutdown_available(self.request()))
        with override_settings(DEBUG=False):
            self.assertFalse(local_shutdown_available(self.request()))

    def test_access_requires_an_active_authenticated_technical_superuser(self):
        request = self.request()
        for user in (
            AnonymousUser(),
            get_user_model()(is_active=False, is_superuser=True),
            get_user_model()(is_active=True, is_staff=True, is_superuser=False),
            get_user_model()(is_active=True, is_superuser=False),
        ):
            with self.subTest(user=user):
                request.user = user
                self.assertFalse(local_shutdown_available(request))

    def test_remote_clients_and_other_hosts_or_ports_cannot_expose_shutdown(self):
        for address in ("203.0.113.20", "192.168.1.7", "", "127.0.0.1, 203.0.113.20"):
            request = self.request()
            request.META["REMOTE_ADDR"] = address
            with self.subTest(address=address):
                self.assertFalse(local_shutdown_available(request))
        for host in ("example.test:8000", "127.0.0.1:8001", "localhost", "127.0.0.1:8000.example.test"):
            request = self.request()
            request.META["HTTP_HOST"] = host
            with self.subTest(host=host):
                self.assertFalse(local_shutdown_available(request))

    def test_forwarding_headers_are_not_a_way_to_gain_local_access(self):
        for header in (
            "HTTP_FORWARDED", "HTTP_VIA", "HTTP_X_FORWARDED_FOR",
            "HTTP_X_FORWARDED_HOST", "HTTP_X_FORWARDED_PROTO", "HTTP_X_FORWARDED_PORT",
        ):
            for value in ("127.0.0.1", ""):
                request = self.request()
                request.META[header] = value
                with self.subTest(header=header, value=value):
                    self.assertFalse(local_shutdown_available(request))


@override_settings(DEBUG=True, PASSWORD_HASHERS=FAST_HASHERS)
class LocalShutdownHttpTests(TestCase):
    def setUp(self):
        self.runtime = LocalRuntime(8000)
        self.runtime_patch = patch("config.local_runtime._runtime", self.runtime)
        self.runtime_patch.start()
        self.addCleanup(self.runtime_patch.stop)
        self.admin = get_user_model().objects.create_superuser(
            username="local-owner", email="local@example.test", password="Test-Local-Only!2947",
        )
        PortalAccount.objects.update_or_create(user=self.admin, defaults={"role": "admin", "must_change_password": False})
        self.client = Client(HTTP_HOST="127.0.0.1:8000", REMOTE_ADDR="127.0.0.1")
        self.client.force_login(self.admin)
        self.url = reverse("local_shutdown")

    def token(self, **changes):
        return signing.dumps({"run_id": self.runtime.run_id, "user_id": self.admin.pk, **changes}, salt=TOKEN_SALT)

    def post(self, **changes):
        response = self.client.post(self.url, {
            "confirmation_token": self.token(), "confirm_shutdown": "yes", **changes,
        })
        self.addCleanup(response.close)
        return response

    def completed_body(self, response, *, success=True):
        """Only body assertions simulate the command completing; never wait 300s."""
        self.runtime.shutdown_succeeded = success
        self.runtime.shutdown_complete.set()
        return b"".join(response.streaming_content).decode()

    def assert_running(self):
        self.assertFalse(self.runtime.stop_requested.is_set())

    def test_get_only_presents_confirmation_and_never_stops_runtime(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["shutdown_token"])
        self.assertIn("no-store", response.get("Cache-Control", ""))
        payload = signing.loads(response.context["shutdown_token"], salt=TOKEN_SALT, max_age=120)
        self.assertEqual(payload, {"run_id": self.runtime.run_id, "user_id": self.admin.pk})
        self.assert_running()

    def test_confirmed_post_requests_shutdown_without_other_process_actions(self):
        response = self.post()
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.streaming)
        self.assertTrue(self.runtime.stop_requested.is_set())
        self.assertFalse(self.runtime.shutdown_complete.is_set())
        self.assertFalse(self.runtime.shutdown_succeeded)
        self.assertIn("no-store", response.get("Cache-Control", ""))

    def test_shutdown_acknowledgement_needs_no_follow_up_assets_and_uses_unique_nonces(self):
        responses = (self.post(), self.post())
        nonces = []
        for response in responses:
            self.assertEqual(response.status_code, 200)
            self.assertTrue(response.streaming)
            nonce = response.local_shutdown_style_nonce
            self.assertTrue(nonce)
            self.assertEqual(response.local_shutdown_script_nonce, nonce)
            nonces.append(nonce)
            policy = {
                values[0]: values[1:]
                for part in response["Content-Security-Policy"].split(";")
                if (values := part.split())
            }
            self.assertEqual(set(policy["style-src"]), {"'self'", f"'nonce-{nonce}'"})
            self.assertEqual(set(policy["script-src"]), {"'self'", f"'nonce-{nonce}'"})
            self.assertNotIn("'unsafe-inline'", response["Content-Security-Policy"])
            parser = _ElementCollector()
            parser.feed(self.completed_body(response))
            styles, scripts = [], []
            for tag, attrs in parser.elements:
                if tag == "style":
                    styles.append(attrs.get("nonce"))
                if tag == "script":
                    scripts.append(attrs.get("nonce"))
                if tag == "link":
                    self.assertNotIn("stylesheet", attrs.get("rel", "").split())
                for attribute in ("href", "src", "srcset", "poster"):
                    resource = attrs.get(attribute)
                    if resource:
                        self.assertTrue(resource.startswith(("data:", "#")), (tag, attribute, resource))
                self.assertFalse(any(attribute.startswith("on") for attribute in attrs))
            self.assertEqual(styles, [nonce])
            self.assertGreaterEqual(len(scripts), 2)
            self.assertEqual(set(scripts), {nonce})
        self.assertNotEqual(*nonces)

    def test_stream_waits_for_completion_and_does_not_claim_success_in_initial_chunk(self):
        response = self.post()
        stream = iter(response.streaming_content)
        initial = next(stream)
        self.assertIn(b"window.sparkxShutdownReceipt", initial)
        self.assertNotIn(b"window.sparkxShutdownReceipt(true)", initial)
        received = []
        finished = threading.Event()

        def read_receipt():
            try:
                received.append(next(stream))
            finally:
                finished.set()

        reader = threading.Thread(target=read_receipt)
        try:
            reader.start()
            self.assertFalse(finished.wait(.05))
            self.runtime.shutdown_succeeded = True
            self.runtime.shutdown_complete.set()
            self.assertTrue(finished.wait(2))
            self.assertEqual(len(received), 1)
            self.assertIn(b"window.sparkxShutdownReceipt(true)", received[0])
        finally:
            self.runtime.shutdown_complete.set()
            reader.join(timeout=2)
            response.close()
        self.assertFalse(reader.is_alive())
        self.assertEqual(self.runtime.shutdown_stream_ids(), set())

    def test_failed_shutdown_emits_false_receipt_without_success(self):
        response = self.post()
        body = self.completed_body(response, success=False)
        self.assertIn("window.sparkxShutdownReceipt(false)", body)
        self.assertNotIn("window.sparkxShutdownReceipt(true)", body)
        self.assertEqual(self.runtime.shutdown_stream_ids(), set())

    def test_timeout_emits_false_receipt_without_fabricating_completion(self):
        response = self.post()
        with patch.object(self.runtime.shutdown_complete, "wait", return_value=False) as wait:
            body = b"".join(response.streaming_content).decode()
        wait.assert_called_once_with(timeout=300)
        self.assertIn("window.sparkxShutdownReceipt(false)", body)
        self.assertNotIn("window.sparkxShutdownReceipt(true)", body)
        self.assertFalse(self.runtime.shutdown_complete.is_set())
        self.assertFalse(self.runtime.shutdown_succeeded)
        self.assertEqual(self.runtime.shutdown_stream_ids(), set())

    def test_disconnected_unconsumed_response_unregisters_its_stream(self):
        response = self.post()
        self.assertIn(threading.get_ident(), self.runtime.shutdown_stream_ids())
        response.close()
        self.assertEqual(self.runtime.shutdown_stream_ids(), set())
        self.assertFalse(self.runtime.shutdown_complete.is_set())

    def test_render_failure_does_not_request_shutdown_or_register_a_stream(self):
        with patch("config.local_views.render_to_string", side_effect=RuntimeError("Synthetic render failure")):
            with self.assertRaisesMessage(RuntimeError, "Synthetic render failure"):
                self.post()
        self.assert_running()
        self.assertEqual(self.runtime.shutdown_stream_ids(), set())

    def test_confirmation_page_keeps_strict_style_policy_without_client_controlled_nonce(self):
        response = self.client.get(self.url, {"shutdown_style_nonce": "client-selected"})
        self.assertEqual(response.status_code, 200)
        policy = response["Content-Security-Policy"]
        self.assertIn("style-src 'self';", policy)
        self.assertNotIn("'nonce-", policy)
        self.assertNotIn("'unsafe-inline'", policy)
        self.assertFalse(hasattr(response, "local_shutdown_style_nonce"))
        self.assertFalse(hasattr(response, "local_shutdown_script_nonce"))
        self.assert_running()

    def test_anonymous_request_requires_login_and_cannot_stop_runtime(self):
        self.client.logout()
        self.assertEqual(self.client.get(self.url).status_code, 302)
        self.assertEqual(self.post().status_code, 302)
        self.assert_running()

    def test_portal_administrator_staff_organizer_and_reviewer_are_not_runtime_owners(self):
        for username, role, staff in (
            ("portal-admin", "admin", False), ("technical-staff", "admin", True),
            ("organizer", "organizer", False), ("reviewer", "reviewer", False),
        ):
            user = get_user_model().objects.create_user(username=username, is_staff=staff)
            PortalAccount.objects.update_or_create(user=user, defaults={"role": role, "must_change_password": False})
            self.client.force_login(user)
            with self.subTest(role=username):
                self.assertEqual(self.client.get(self.url).status_code, 403)
                self.assertEqual(self.post().status_code, 403)
                self.assert_running()

    def test_service_not_started_with_runlocal_or_production_cannot_be_stopped(self):
        with patch("config.local_runtime._runtime", None):
            self.assertEqual(self.client.get(self.url).status_code, 404)
            self.assertEqual(self.post().status_code, 404)
        with override_settings(DEBUG=False, SECURE_SSL_REDIRECT=False):
            self.assertEqual(self.client.get(self.url).status_code, 404)
            self.assertEqual(self.post().status_code, 404)
        self.assert_running()

    def test_confirmation_and_valid_signature_are_required(self):
        for changes in (
            {"confirmation_token": ""}, {"confirmation_token": "invalid"},
            {"confirmation_token": self.token() + "tampered"},
            {"confirm_shutdown": ""}, {"confirm_shutdown": "no"},
        ):
            with self.subTest(changes=changes):
                self.assertEqual(self.post(**changes).status_code, 400)
                self.assert_running()

    def test_token_for_another_user_or_previous_run_cannot_stop_current_runtime(self):
        for token in (self.token(user_id=self.admin.pk + 1), self.token(run_id="previous-run")):
            with self.subTest(token_kind=signing.loads(token, salt=TOKEN_SALT)):
                self.assertEqual(self.post(confirmation_token=token).status_code, 400)
                self.assert_running()

    def test_expired_confirmation_cannot_stop_runtime(self):
        token = self.token()
        with patch("django.core.signing.time.time", return_value=time.time() + 121):
            self.assertEqual(self.post(confirmation_token=token).status_code, 400)
        self.assert_running()

    def test_csrf_is_required_even_with_a_valid_confirmation(self):
        client = Client(enforce_csrf_checks=True, HTTP_HOST="127.0.0.1:8000", REMOTE_ADDR="127.0.0.1")
        client.force_login(self.admin)
        self.assertEqual(client.post(self.url, {"confirmation_token": self.token(), "confirm_shutdown": "yes"}).status_code, 403)
        self.assert_running()
        response = client.get(self.url)
        self.assertEqual(response.status_code, 200)
        csrf = client.cookies["csrftoken"].value
        stopped = client.post(self.url, {
            "confirmation_token": response.context["shutdown_token"], "confirm_shutdown": "yes",
            "csrfmiddlewaretoken": csrf,
        })
        self.addCleanup(stopped.close)
        self.assertEqual(stopped.status_code, 200)
        self.assertTrue(self.runtime.stop_requested.is_set())

    def test_remote_and_forwarded_requests_cannot_stop_runtime(self):
        for meta in (
            {"REMOTE_ADDR": "203.0.113.1"}, {"HTTP_HOST": "localhost:8001"},
            {"HTTP_X_FORWARDED_FOR": "127.0.0.1"}, {"HTTP_FORWARDED": "for=127.0.0.1"},
            {"HTTP_VIA": "1.1 local-proxy"},
        ):
            with self.subTest(meta=meta):
                response = self.client.post(self.url, {
                    "confirmation_token": self.token(), "confirm_shutdown": "yes",
                }, **meta)
                self.assertEqual(response.status_code, 403)
                self.assert_running()

    def test_privileges_revoked_since_confirmation_are_checked_again(self):
        token = self.client.get(self.url).context["shutdown_token"]
        get_user_model().objects.filter(pk=self.admin.pk).update(is_superuser=False, is_staff=False)
        self.assertEqual(self.post(confirmation_token=token).status_code, 403)
        self.assert_running()

    def test_operation_rechecks_database_even_if_request_user_is_stale(self):
        from config.local_views import shutdown

        for changes in ({"is_superuser": False}, {"is_active": False}):
            get_user_model().objects.filter(pk=self.admin.pk).update(is_superuser=True, is_active=True)
            # Simulate a request already authenticated before privilege revocation.
            self.admin.refresh_from_db()
            request = RequestFactory().post(self.url, {
                "confirmation_token": self.token(), "confirm_shutdown": "yes",
            }, HTTP_HOST="127.0.0.1:8000", REMOTE_ADDR="127.0.0.1")
            request.user = self.admin
            get_user_model().objects.filter(pk=self.admin.pk).update(**changes)
            with self.subTest(changes=changes), self.assertRaises(PermissionDenied):
                shutdown(request)
            self.assert_running()

    def test_other_http_methods_cannot_stop_runtime(self):
        for method in ("put", "delete", "patch", "options"):
            with self.subTest(method=method):
                self.assertEqual(getattr(self.client, method)(self.url).status_code, 405)
                self.assert_running()

    def test_sidebar_button_requires_the_owned_local_runtime(self):
        response = self.client.get(reverse("events:index"))
        self.assertTrue(response.context["local_shutdown_visible"])
        self.assertContains(response, self.url)
        with patch("config.local_runtime._runtime", None):
            response = self.client.get(reverse("events:index"))
            self.assertFalse(response.context["local_shutdown_visible"])
            self.assertNotContains(response, self.url)


@override_settings(DEBUG=True)
class LocalLaunchCommandTests(SimpleTestCase):
    def setUp(self):
        self.runtime_patch = patch("config.local_runtime._runtime", None)
        self.runtime_patch.start()
        self.addCleanup(self.runtime_patch.stop)

    def test_production_and_invalid_ports_are_rejected_before_binding(self):
        with patch("apps.events.management.commands.runlocal.LocalServer") as server:
            with override_settings(DEBUG=False), self.assertRaises(CommandError):
                call_command("runlocal", stdout=io.StringIO())
            for port in (0, -1, 65536):
                with self.subTest(port=port), self.assertRaises(CommandError):
                    call_command("runlocal", port=port, stdout=io.StringIO())
            server.assert_not_called()

    def test_existing_runtime_cannot_be_overwritten(self):
        runtime = LocalRuntime(8000)
        with (
            patch("config.local_runtime._runtime", runtime),
            patch("apps.events.management.commands.runlocal.LocalServer") as server,
        ):
            with self.assertRaises(CommandError):
                call_command("runlocal", stdout=io.StringIO())
            server.assert_not_called()
            self.assertFalse(runtime.stop_requested.is_set())

    def test_pending_migrations_prevent_start_without_applying_them(self):
        with (
            patch("apps.events.management.commands.runlocal.MigrationExecutor") as executor,
            patch("apps.events.management.commands.runlocal.LocalServer") as server,
        ):
            executor.return_value.migration_plan.return_value = [(object(), False)]
            with self.assertRaises(CommandError):
                call_command("runlocal", stdout=io.StringIO())
            server.assert_not_called()
            executor.return_value.migrate.assert_not_called()

    def test_occupied_port_is_reported_without_registering_runtime(self):
        from config.local_runtime import get_runtime

        with (
            patch("apps.events.management.commands.runlocal.MigrationExecutor") as executor,
            patch("apps.events.management.commands.runlocal.connections.close_all"),
            patch("apps.events.management.commands.runlocal.LocalServer", side_effect=OSError(errno.EADDRINUSE, "test port busy")),
        ):
            executor.return_value.migration_plan.return_value = []
            with self.assertRaises(CommandError) as error:
                call_command("runlocal", port=8765, stdout=io.StringIO())
            self.assertIn("El puerto 8765 ya está en uso", str(error.exception))
            self.assertIn("versión anterior", str(error.exception))
            self.assertIn("vuelve a iniciar", str(error.exception))
            self.assertIn("No se detuvo ningún proceso", str(error.exception))
            self.assertIsNone(get_runtime())

    def test_owned_runtime_binds_loopback_and_cleans_up_on_shutdown(self):
        from config.local_runtime import get_runtime
        from apps.events.management.commands.runlocal import Command

        with (
            patch("apps.events.management.commands.runlocal.MigrationExecutor") as executor,
            patch("apps.events.management.commands.runlocal.connections.close_all"),
            patch("apps.events.management.commands.runlocal.get_internal_wsgi_application", return_value=lambda environ, start_response: []),
            patch("apps.events.management.commands.runlocal.LocalServer") as server,
            patch.object(Command, "on_server_stopping") as stop_worker,
        ):
            executor.return_value.migration_plan.return_value = []
            server.return_value.server_port = 8765
            observed = []
            stages = []

            def request_stop():
                runtime = get_runtime()
                observed.append(runtime)
                self.assertEqual(runtime.port, 8765)
                runtime.request_shutdown()

            def worker_finished():
                self.assertFalse(observed[0].shutdown_complete.is_set())
                stages.append("worker")

            def drain(runtime):
                self.assertIs(runtime, observed[0])
                self.assertFalse(runtime.shutdown_complete.is_set())
                stages.append("drain")

            def close_listener():
                self.assertFalse(observed[0].shutdown_complete.is_set())
                stages.append("listener")

            def join_streams():
                self.assertTrue(observed[0].shutdown_complete.is_set())
                self.assertTrue(observed[0].shutdown_succeeded)
                stages.append("join_streams")

            stop_worker.side_effect = worker_finished
            server.return_value.drain_shutdown_requests.side_effect = drain
            server.return_value.socket.close.side_effect = close_listener
            server.return_value.server_close.side_effect = join_streams
            server.return_value.handle_request.side_effect = request_stop
            call_command("runlocal", port=8765, stdout=io.StringIO())
            self.assertEqual(server.call_args.args[0], ("127.0.0.1", 8765))
            server.return_value.server_close.assert_called_once()
            server.return_value.drain_shutdown_requests.assert_called_once_with(observed[0])
            server.return_value.socket.close.assert_called_once()
            self.assertEqual(stages, ["worker", "drain", "listener", "join_streams"])
            self.assertTrue(observed[0].stop_requested.is_set())
            self.assertTrue(observed[0].shutdown_complete.is_set())
            self.assertTrue(observed[0].shutdown_succeeded)
            self.assertIsNone(get_runtime())

    def test_failed_drain_signals_failure_before_joining_streams_without_hanging(self):
        from config.local_runtime import get_runtime

        with (
            patch("apps.events.management.commands.runlocal.MigrationExecutor") as executor,
            patch("apps.events.management.commands.runlocal.connections.close_all"),
            patch("apps.events.management.commands.runlocal.get_internal_wsgi_application", return_value=lambda environ, start_response: []),
            patch("apps.events.management.commands.runlocal.LocalServer") as server,
        ):
            executor.return_value.migration_plan.return_value = []
            server.return_value.server_port = 8765
            observed = []

            def request_stop():
                runtime = get_runtime()
                observed.append(runtime)
                runtime.request_shutdown()

            def join_after_failure():
                self.assertTrue(observed[0].shutdown_complete.is_set())
                self.assertFalse(observed[0].shutdown_succeeded)

            server.return_value.handle_request.side_effect = request_stop
            server.return_value.drain_shutdown_requests.side_effect = RuntimeError("Synthetic drain failure")
            server.return_value.server_close.side_effect = join_after_failure
            try:
                call_command("runlocal", port=8765, stdout=io.StringIO(), stderr=io.StringIO())
            except RuntimeError as failure:
                self.assertEqual(str(failure), "Synthetic drain failure")
            server.return_value.server_close.assert_called_once()
            self.assertTrue(observed[0].shutdown_complete.is_set())
            self.assertFalse(observed[0].shutdown_succeeded)
            self.assertIsNone(get_runtime())

    def test_keyboard_interrupt_cleans_up_owned_runtime_and_listener(self):
        from config.local_runtime import get_runtime

        with (
            patch("apps.events.management.commands.runlocal.MigrationExecutor") as executor,
            patch("apps.events.management.commands.runlocal.connections.close_all"),
            patch("apps.events.management.commands.runlocal.get_internal_wsgi_application", return_value=lambda environ, start_response: []),
            patch("apps.events.management.commands.runlocal.LocalServer") as server,
        ):
            executor.return_value.migration_plan.return_value = []
            server.return_value.server_port = 8765
            server.return_value.handle_request.side_effect = KeyboardInterrupt
            call_command("runlocal", port=8765, stdout=io.StringIO())
            server.return_value.server_close.assert_called_once()
            self.assertIsNone(get_runtime())


class LocalServerSocketTests(SimpleTestCase):
    def test_drain_waits_for_pending_and_active_http_request_but_excludes_live_ack(self):
        from apps.events.management.commands.runlocal import LocalRequestHandler, LocalServer

        runtime = LocalRuntime(0)
        ack_started, ack_release, ack_finished = threading.Event(), threading.Event(), threading.Event()
        pending_started, enter_handler = threading.Event(), threading.Event()
        ordinary_started, ordinary_release = threading.Event(), threading.Event()
        drained = threading.Event()
        failures = []
        gate_lock = threading.Lock()
        entered = 0

        def application(environ, start_response):
            if environ["PATH_INFO"] == "/ack/":
                runtime.register_shutdown_stream()
                try:
                    start_response("200 OK", [("Content-Type", "text/plain")])
                    ack_started.set()
                    yield b"ack"
                    if not ack_release.wait(5):
                        failures.append("ack gate timed out")
                    yield b"done"
                finally:
                    runtime.unregister_shutdown_stream()
                    ack_finished.set()
            else:
                ordinary_started.set()
                if not ordinary_release.wait(5):
                    failures.append("ordinary gate timed out")
                start_response("200 OK", [("Content-Type", "text/plain")])
                yield b"ordinary"

        server = LocalServer(("127.0.0.1", 0), LocalRequestHandler)
        server.set_app(application)
        server.timeout = 1
        original_handler = server.process_request_thread

        def before_handler(*args):
            nonlocal entered
            with gate_lock:
                entered += 1
                position = entered
            # Pause the second accepted socket before the real tracker moves it
            # from pending into active. The first socket is the live ACK stream.
            if position == 2:
                pending_started.set()
                if not enter_handler.wait(5):
                    failures.append("pending gate timed out")
            original_handler(*args)

        def accept_two():
            for _ in range(2):
                server.handle_request()

        def drain():
            server.drain_shutdown_requests(runtime)
            drained.set()

        acceptor = threading.Thread(target=accept_two)
        drainer = threading.Thread(target=drain)
        ack = http.client.HTTPConnection("127.0.0.1", server.server_port, timeout=3)
        ordinary = http.client.HTTPConnection("127.0.0.1", server.server_port, timeout=3)
        try:
            with patch.object(server, "process_request_thread", side_effect=before_handler), \
                 patch.object(LocalRequestHandler, "log_message"), patch.object(server, "handle_error") as server_error:
                acceptor.start()
                ack.request("GET", "/ack/")
                self.assertTrue(ack_started.wait(2))
                acknowledgement = ack.getresponse()
                self.assertEqual(acknowledgement.read(3), b"ack")
                ordinary.request("GET", "/ordinary/")
                self.assertTrue(pending_started.wait(2))
                with server._request_condition:
                    self.assertEqual(server._pending_requests, 1)
                drainer.start()
                self.assertFalse(drained.wait(.05), "Accepted pre-handler request was missed")
                enter_handler.set()
                self.assertTrue(ordinary_started.wait(2))
                self.assertFalse(drained.wait(.05), "Active non-ACK request was skipped")
                ordinary_release.set()
                self.assertTrue(drained.wait(2), "Drain incorrectly waited for the ACK stream")
                self.assertFalse(ack_finished.is_set())
                self.assertTrue(runtime.shutdown_stream_ids())
                response = ordinary.getresponse()
                self.assertEqual(response.status, 200)
                self.assertEqual(response.read(), b"ordinary")
                ack_release.set()
                self.assertEqual(acknowledgement.read(), b"done")
                self.assertTrue(ack_finished.wait(2))
                acceptor.join(timeout=2)
                drainer.join(timeout=2)
                server_error.assert_not_called()
        finally:
            enter_handler.set()
            ordinary_release.set()
            ack_release.set()
            ack.close()
            ordinary.close()
            if acceptor.ident is not None:
                acceptor.join(timeout=3)
            if drainer.ident is not None:
                drainer.join(timeout=3)
            server.server_close()
        self.assertFalse(acceptor.is_alive())
        self.assertFalse(drainer.is_alive())
        self.assertEqual(runtime.shutdown_stream_ids(), set())
        self.assertEqual(failures, [])

    def test_idle_browser_preconnection_closes_without_server_exception(self):
        from apps.events.management.commands.runlocal import LocalRequestHandler, LocalServer

        server = LocalServer(("127.0.0.1", 0), LocalRequestHandler)
        application = Mock()
        server.set_app(application)
        original_get_request = server.get_request

        def short_timeout():
            connection, address = original_get_request()
            connection.settimeout(.05)
            return connection, address

        server.get_request = short_timeout
        server.timeout = 1
        thread = threading.Thread(target=server.handle_request)
        client = None
        try:
            with patch.object(server, "handle_error") as error:
                thread.start()
                client = socket.create_connection(server.server_address, timeout=2)
                self.assertEqual(client.recv(1), b"")
                thread.join(timeout=2)
                self.assertFalse(thread.is_alive())
                server.server_close()
                error.assert_not_called()
                application.assert_not_called()
        finally:
            if client:
                client.close()
            thread.join(timeout=2)
            server.server_close()

    def test_second_listener_cannot_take_the_running_servers_port(self):
        from apps.events.management.commands.runlocal import LocalRequestHandler, LocalServer

        server = LocalServer(("127.0.0.1", 0), LocalRequestHandler)
        try:
            with self.assertRaises(OSError):
                duplicate = LocalServer(server.server_address, LocalRequestHandler)
                duplicate.server_close()
        finally:
            server.server_close()

    def test_idle_client_socket_has_a_finite_read_timeout(self):
        from apps.events.management.commands.runlocal import LocalServer, ThreadedWSGIServer

        server = LocalServer.__new__(LocalServer)
        connection = Mock()
        address = ("127.0.0.1", 12345)
        with patch.object(ThreadedWSGIServer, "get_request", return_value=(connection, address)):
            self.assertEqual(server.get_request(), (connection, address))
        connection.settimeout.assert_called_once_with(10)

    def test_http_response_closes_connection_and_request_thread_is_joinable(self):
        from apps.events.management.commands.runlocal import LocalRequestHandler, LocalServer

        daemon_flags = []

        def application(environ, start_response):
            daemon_flags.append(threading.current_thread().daemon)
            start_response("200 OK", [("Content-Type", "text/plain"), ("Content-Length", "2")])
            return [b"ok"]

        server = LocalServer(("127.0.0.1", 0), LocalRequestHandler)
        server.set_app(application)
        server.timeout = 1
        thread = threading.Thread(target=server.handle_request)
        connection = http.client.HTTPConnection("127.0.0.1", server.server_port, timeout=3)
        try:
            with patch.object(LocalRequestHandler, "log_message"):
                thread.start()
                connection.request("GET", "/health/")
                response = connection.getresponse()
                self.assertEqual(response.status, 200)
                self.assertEqual(response.read(), b"ok")
                self.assertEqual(response.version, 10)
                self.assertTrue(response.will_close)
            thread.join(timeout=3)
            self.assertFalse(thread.is_alive())
            self.assertEqual(daemon_flags, [False])
            self.assertTrue(server.block_on_close)
        finally:
            connection.close()
            thread.join(timeout=3)
            server.server_close()
