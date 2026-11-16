"""Transport and diagnostic boundaries for a private, ephemeral credential form.

Authorization, CSRF and the secret's lifetime belong to their callers. HTTPS
relies on Django's deployment configuration: a reverse proxy must strip and set
the trusted scheme header correctly. These helpers do not establish a sandbox.
"""
import ipaddress

from django.conf import settings
from django.core.exceptions import DisallowedHost, PermissionDenied
from django.views.debug import ExceptionReporter, SafeExceptionReporterFilter


_DENIED = "Las credenciales requieren HTTPS o el servidor local directo."


def require_private_transport(request):
    """Allow valid-host HTTPS or direct development loopback on its exact port."""
    try:
        host = request.get_host().lower()
    except (DisallowedHost, ValueError, TypeError):
        raise PermissionDenied(_DENIED) from None
    if request.is_secure():
        return
    if not settings.DEBUG or any(
        name in {"HTTP_FORWARDED", "HTTP_VIA"} or name.startswith("HTTP_X_FORWARDED_")
        for name in request.META
    ):
        raise PermissionDenied(_DENIED)
    try:
        peer = ipaddress.ip_address(request.META.get("REMOTE_ADDR", ""))
        port = int(request.META.get("SERVER_PORT", ""))
    except (ValueError, TypeError):
        raise PermissionDenied(_DENIED) from None
    if not peer.is_loopback or not 1 <= port <= 65535:
        raise PermissionDenied(_DENIED)
    hosts = {f"localhost:{port}", f"127.0.0.1:{port}", f"[::1]:{port}"}
    if port == 80:
        hosts.update({"localhost", "127.0.0.1", "[::1]"})
    if host not in hosts:
        raise PermissionDenied(_DENIED)


class AlwaysActiveCredentialFilter(SafeExceptionReporterFilter):
    """Hide all submitted values and stack locals, including in DEBUG reports."""

    def is_active(self, request):
        return True

    def get_post_parameters(self, request):
        if request is None:
            return {}
        cleansed = request.POST.copy()
        for name in cleansed:
            cleansed[name] = self.cleansed_substitute
        return cleansed

    def get_traceback_frame_variables(self, request, tb_frame):
        # Generic names such as value/cleaned_data can also contain a secret.
        # Returning no original values avoids requiring every caller to guess
        # all aliases, and avoids repr() on a private runtime registry.
        return [(name, self.cleansed_substitute) for name in tb_frame.f_locals]


class PrivateCredentialReporter(ExceptionReporter):
    def get_traceback_data(self):
        data = super().get_traceback_data()
        # A third-party exception may interpolate the submitted value. Caller
        # logging must likewise use a fixed message without exc_info/raw repr.
        data["exception_value"] = "Error al procesar la credencial privada."
        return data


def force_redact_request(request):
    """Install before reading POST, including for a request rejected afterwards."""
    request.sensitive_post_parameters = "__ALL__"
    request.exception_reporter_filter = AlwaysActiveCredentialFilter()
    request.exception_reporter_class = PrivateCredentialReporter

