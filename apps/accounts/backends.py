"""Unambiguous email/username access, retaining Django's password/session hashing."""
from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend
from django.core.exceptions import PermissionDenied

from .services import normalize_identifier


class EmailOrUsernameBackend(ModelBackend):
    def authenticate(self, request, username=None, password=None, **kwargs):
        identifier = normalize_identifier(username)
        User = get_user_model()
        # Legacy email is not unique. Reject ambiguity across both namespaces,
        # including Unicode-normalized usernames and inactive accounts.
        candidates = []
        if identifier and isinstance(password, str):
            identities = User.objects.values_list("pk", "username", "email")
            for pk, name, email in identities:
                if identifier in {normalize_identifier(name), normalize_identifier(email)}:
                    candidates.append(pk)
                    if len(candidates) > 1:
                        break
        if len(candidates) == 1:
            user = User.objects.get(pk=candidates[0])
            if user.check_password(password) and self.user_can_authenticate(user):
                return user
        else:
            # One password hash even when no matching account exists.
            User().set_password(password if isinstance(password, str) else "")
        # Stop other backends from resolving an ambiguous alias differently.
        raise PermissionDenied
