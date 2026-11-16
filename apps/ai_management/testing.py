"""Explicit inert configuration for tests; never a runtime budget bypass."""

from decimal import Decimal

from .models import AIAccount, AIProfile, OpenAIPilotLock


def configure_test_account(owner, *, budget="10", token_limit=2_000_000, paid=True):
    # TransactionTestCase flushes data-migration seeds. Restore only the isolated
    # test mutex; production code deliberately refuses to recreate this record.
    OpenAIPilotLock.objects.get_or_create(pk=1)
    profile = AIProfile.objects.create(
        owner=owner, name="Perfil de prueba sin red", provider="openai", model="gpt-6-luna",
        mode="paid", max_input_tokens=24000, max_output_tokens=2500,
        input_rate=Decimal("1"), cached_rate=Decimal("0.1"), output_rate=Decimal("2"),
    )
    account, _created = AIAccount.objects.get_or_create(owner=owner)
    account.active_profile = profile
    account.paid_enabled = paid
    account.monthly_budget_usd = Decimal(budget)
    account.monthly_token_limit = token_limit
    account.save()
    return account
