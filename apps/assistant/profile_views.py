"""Human-only Gica presentation settings; each account can edit only its own."""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.shortcuts import redirect, render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods

from .local_commands import human_organizer
from .models import GicaProfile
from .profile_forms import GicaProfileForm
from .profile_settings import greeting_for, profile_for


@never_cache
@login_required
@require_http_methods(["GET", "POST"])
def profile(request):
    actor = human_organizer(request.user)
    current = profile_for(actor)
    form = GicaProfileForm(request.POST if request.method == "POST" else None, initial=current)
    if request.method == "POST":
        allowed = {"personality", "appearance", "csrfmiddlewaretoken"}
        unexpected = bool(set(request.POST) - allowed) or any(len(request.POST.getlist(key)) != 1 for key in request.POST)
        if unexpected:
            form.is_valid()
            form.add_error(None, "Sólo puedes cambiar la personalidad y la apariencia de tu Gica.")
        elif form.is_valid():
            with transaction.atomic():
                actor = human_organizer(request.user, lock=True)
                GicaProfile.objects.update_or_create(owner=actor, defaults=form.cleaned_data)
            messages.success(request, "Tu Gica está actualizado. El nuevo saludo se usará al abrir otra conversación.")
            return redirect("assistant:profile")
    return render(request, "assistant/profile.html", {
        "profile_form": form,
        "gica_profile_settings": current,
        "gica_greeting_preview": greeting_for(current["personality"], actor.username),
    }, status=400 if request.method == "POST" else 200)

