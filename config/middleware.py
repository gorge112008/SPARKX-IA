"""Avoid shared caching and active untrusted content in the private UI."""
from django.utils.cache import patch_cache_control, patch_vary_headers
from django.shortcuts import render


class PrivateResponsesMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if (response.status_code == 404 and not response.streaming
                and response.get("Content-Type", "").split(";", 1)[0] == "text/html"):
            # Django's DEBUG 404 exposes URL patterns and uses inline styles.
            # Keep the same non-enumerating denial in local demos and production.
            previous_headers = dict(response.headers)
            response = render(request, "errors/not_found.html", status=404)
            for name in ("Vary", "Cache-Control"):
                if name in previous_headers:
                    response[name] = previous_headers[name]
            response["X-Robots-Tag"] = "noindex, nofollow, noarchive"
            patch_cache_control(response, no_store=True)
        if getattr(request, "user", None) and request.user.is_authenticated:
            patch_cache_control(response, private=True, no_store=True)
            patch_vary_headers(response, ["Cookie", "HX-Request"])
        response["Referrer-Policy"] = "same-origin"
        response["Permissions-Policy"] = "camera=(), geolocation=()"
        # The shutdown stream carries its assets before the listener closes.
        nonce = getattr(response, "local_shutdown_style_nonce", None)
        style_source = f"style-src 'self' 'nonce-{nonce}'; " if nonce else "style-src 'self'; "
        script_nonce = getattr(response, "local_shutdown_script_nonce", None)
        script_source = f"script-src 'self' 'nonce-{script_nonce}'; " if script_nonce else "script-src 'self'; "
        response["Content-Security-Policy"] = (
            "default-src 'self'; " + script_source + style_source +
            "img-src 'self' data:; font-src 'self'; connect-src 'self'; "
            "frame-ancestors 'none'; base-uri 'self'; form-action 'self'"
        )
        return response
