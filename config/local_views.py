"""Authenticated, CSRF-protected confirmation for a local server's own stop event."""
import secrets

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.core import signing
from django.core.exceptions import PermissionDenied
from django.http import Http404, StreamingHttpResponse
from django.shortcuts import render
from django.template.loader import render_to_string
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods

from .local_runtime import get_runtime, local_shutdown_available


TOKEN_SALT = "sparkx.local-shutdown"
TOKEN_MAX_AGE = 120


class _ShutdownResponse(StreamingHttpResponse):
    def __init__(self, *args, runtime, **kwargs):
        super().__init__(*args, **kwargs)
        self.runtime = runtime
        self.stream_id = runtime.register_shutdown_stream()

    def close(self):
        try:
            super().close()
        finally:
            # Also handles a browser disconnect before the first chunk: close()
            # on an unstarted generator does not execute its finally block.
            self.runtime.unregister_shutdown_stream(self.stream_id)


@login_required
@never_cache
@require_http_methods(["GET", "POST"])
def shutdown(request):
    from apps.assistant.execution import deny_agent_admin
    deny_agent_admin()
    runtime = get_runtime()
    if runtime is None:
        raise Http404
    if not local_shutdown_available(request):
        # Production must never expose this operation even if the module has
        # been imported or a runtime is accidentally registered there.
        if not settings.DEBUG:
            raise Http404
        raise PermissionDenied
    # Recheck the technical permission at the operation boundary. A portal
    # administrator is deliberately insufficient for process control.
    if not get_user_model().objects.filter(
        pk=request.user.pk, is_active=True, is_superuser=True,
    ).exists():
        raise PermissionDenied

    if request.method == "POST":
        try:
            payload = signing.loads(
                request.POST.get("confirmation_token", ""),
                salt=TOKEN_SALT, max_age=TOKEN_MAX_AGE,
            )
        except (signing.BadSignature, TypeError, ValueError):
            payload = None
        if payload != {"run_id": runtime.run_id, "user_id": request.user.pk} or request.POST.get("confirm_shutdown") != "yes":
            return render(request, "local_runtime/confirm_shutdown.html", {
                "shutdown_token": _token(runtime, request.user),
                "error": "Confirma de nuevo el apagado. La confirmación caduca a los dos minutos y al reiniciar SparkX.",
            }, status=400)
        # Send the page first, then a completion receipt in the same connection.
        # No new asset/status request is needed after the listener has closed.
        nonce = secrets.token_urlsafe(24)
        page = render_to_string("local_runtime/shutdown_requested.html", {
            "shutdown_style_nonce": nonce,
            "shutdown_script_nonce": nonce,
        }, request=request)

        def acknowledgement():
            try:
                yield page
                ready = runtime.shutdown_complete.wait(timeout=300)
                result = "true" if ready and runtime.shutdown_succeeded else "false"
                yield (f'<script nonce="{nonce}">window.sparkxShutdownReceipt({result});</script>'
                       '</body></html>')
            finally:
                runtime.unregister_shutdown_stream(response.stream_id)

        response = _ShutdownResponse(acknowledgement(), runtime=runtime, content_type="text/html; charset=utf-8")
        response.local_shutdown_style_nonce = nonce
        response.local_shutdown_script_nonce = nonce
        response["X-Accel-Buffering"] = "no"
        runtime.request_shutdown()
        return response

    return render(request, "local_runtime/confirm_shutdown.html", {
        "shutdown_token": _token(runtime, request.user),
    })


def _token(runtime, user):
    return signing.dumps({"run_id": runtime.run_id, "user_id": user.pk}, salt=TOKEN_SALT)
