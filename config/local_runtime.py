"""Process-local control for the explicitly started loopback development server.

No PID, shell command, file, environment flag or external server can be stopped
through this module. The runlocal command owns the listener and its stop event.
"""
import ipaddress
import secrets
import threading

from django.conf import settings
from django.core.exceptions import DisallowedHost


class LocalRuntime:
    def __init__(self, port):
        self.port = port
        self.run_id = secrets.token_urlsafe(32)
        self.stop_requested = threading.Event()
        self.shutdown_complete = threading.Event()
        self.shutdown_succeeded = False
        self._stream_lock = threading.Lock()
        self._shutdown_streams = set()

    def request_shutdown(self):
        self.stop_requested.set()

    def register_shutdown_stream(self):
        thread_id = threading.get_ident()
        with self._stream_lock:
            self._shutdown_streams.add(thread_id)
        return thread_id

    def unregister_shutdown_stream(self, thread_id=None):
        with self._stream_lock:
            self._shutdown_streams.discard(thread_id if thread_id is not None else threading.get_ident())

    def shutdown_stream_ids(self):
        with self._stream_lock:
            return frozenset(self._shutdown_streams)


_runtime = None


def get_runtime():
    return _runtime


def local_shutdown_available(request):
    runtime = get_runtime()
    user = getattr(request, "user", None)
    if not settings.DEBUG or runtime is None or not (
        user and user.is_authenticated and user.is_active and user.is_superuser
    ):
        return False
    # Never treat a proxy's loopback connection as a local browser session.
    if any(
        key in {"HTTP_FORWARDED", "HTTP_VIA"} or key.startswith("HTTP_X_FORWARDED_")
        for key in request.META
    ):
        return False
    try:
        if not ipaddress.ip_address(request.META.get("REMOTE_ADDR", "")).is_loopback:
            return False
        hosts = {
            f"127.0.0.1:{runtime.port}", f"localhost:{runtime.port}",
        }
        if runtime.port == 80:
            hosts.update({"127.0.0.1", "localhost"})
        return request.get_host() in hosts
    except (ValueError, DisallowedHost):
        return False
