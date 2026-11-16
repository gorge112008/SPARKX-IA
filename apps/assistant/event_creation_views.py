"""Same-origin human-only JSON endpoint for the local event interview."""

from django import forms
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.http import JsonResponse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_POST

from .event_creation import ALLOWED_OPERATIONS, STEP_KEYS, creation_turn
from .local_commands import human_organizer


class CreationTurnForm(forms.Form):
    text = forms.CharField(required=False, max_length=300)
    request_id = forms.UUIDField()
    draft_id = forms.UUIDField(required=False)
    expected_revision = forms.IntegerField(min_value=0)
    operation = forms.ChoiceField(choices=[(op, op) for op in sorted(ALLOWED_OPERATIONS)])
    field = forms.ChoiceField(required=False, choices=[("", ""), *((key, key) for key in STEP_KEYS)])


@never_cache
@login_required
@require_POST
def turn(request):
    actor = human_organizer(request.user)
    allowed = {*CreationTurnForm.base_fields, "csrfmiddlewaretoken"}
    if set(request.POST) - allowed or any(len(request.POST.getlist(key)) > 1 for key in allowed):
        return JsonResponse({"handled": True, "status": "invalid", "reply": "Envía una sola respuesta y únicamente los campos permitidos.", "error_code": "invalid_payload"}, status=400)
    form = CreationTurnForm(request.POST)
    if not form.is_valid():
        return JsonResponse({"handled": True, "status": "invalid", "reply": "Revisa la respuesta, sus identificadores y la revisión del borrador.", "error_code": "invalid_payload"}, status=400)
    values = form.cleaned_data
    try:
        result = creation_turn(actor, **values)
    except ValidationError as exc:
        return JsonResponse({"handled": True, "status": "invalid", "reply": " ".join(exc.messages)[:280], "error_code": "invalid_payload"}, status=400)
    status = 409 if result.get("status") == "conflict" else 410 if result.get("status") == "expired" else 200
    return JsonResponse(result, status=status)
