"""Bounded login attempts stored as HMAC identifiers, never raw credentials."""
from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.utils import timezone
from django.utils.crypto import salted_hmac

from .models import LoginAttemptWindow
from .services import normalize_identifier


def _consume(key, limit, now, window):
    with transaction.atomic():
        LoginAttemptWindow.objects.get_or_create(key=key, defaults={"started_at": now})
        row = LoginAttemptWindow.objects.select_for_update().get(pk=key)
        if row.started_at <= now - timedelta(seconds=window):
            row.started_at, row.attempts = now, 0
        if row.attempts >= limit:
            return False
        row.attempts += 1
        row.save(update_fields=["started_at", "attempts"])
        return True


def allow_login_attempt(request):
    now = timezone.now()
    window = max(1, int(settings.LOGIN_WINDOW_SECONDS))
    ip = request.META.get("REMOTE_ADDR", "")  # Never trust an arbitrary X-Forwarded-For.
    identifier = normalize_identifier(request.POST.get("username", ""))[:254]
    ip_key = salted_hmac("sparkx-login-ip", ip, algorithm="sha256").hexdigest()
    pair_key = salted_hmac("sparkx-login-pair", ip + "\0" + identifier, algorithm="sha256").hexdigest()
    LoginAttemptWindow.objects.filter(started_at__lt=now - timedelta(days=1)).delete()
    return (
        _consume(ip_key, max(1, int(settings.LOGIN_IP_MAX_ATTEMPTS)), now, window)
        and _consume(pair_key, max(1, int(settings.LOGIN_MAX_ATTEMPTS)), now, window)
    )
