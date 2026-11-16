"""Controlled CLI local queries: synthetic records, no models or financial work."""

from io import StringIO
import json
from unittest.mock import patch
import uuid

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase

from apps.accounts.models import PortalAccount
from apps.ai_management.models import AIAccount, AIUsage
from apps.assistant.models import Message
from apps.directory.models import Person
from apps.events.models import Event
from .models import Job


class RomeoLocalCommandTests(TestCase):
    def setUp(self):
        self.owner = get_user_model().objects.create_user(username="local-cli-owner")
        self.other = get_user_model().objects.create_user(username="local-cli-other")
        self.portal = PortalAccount.objects.create(user=self.owner)
        self.event = Event.objects.create(owner=self.owner, title="Ficticio CLI", brief="Privado", is_synthetic=True)
        self.foreign = Event.objects.create(owner=self.other, title="Ajeno", brief="Privado", is_synthetic=True)
        self.key = uuid.uuid4()

    def run_local(self, **values):
        out = StringIO()
        params = {
            "username": self.owner.username, "event": str(self.event.pk),
            "command": "buscar expositores", "request_key": str(self.key), "stdout": out,
        }
        params.update(values)
        call_command("romeo_local", **params)
        return json.loads(out.getvalue())

    def assert_no_ai(self):
        self.assertFalse(Job.objects.exists())
        self.assertFalse(AIUsage.objects.exists())
        self.assertFalse(AIAccount.objects.exists())

    def test_local_query_records_real_chat_pair_without_api_and_prints_metadata_only(self):
        speaker = Person.objects.create(
            owner=self.owner, full_name="Nombre Ficticio Privado", name_key="nombre ficticio privado",
            category="speaker", is_synthetic=True,
        )
        before = Event.objects.get(pk=self.event.pk).revision
        with patch("apps.assistant.provider._opener.open", side_effect=AssertionError("No API")), \
                patch("apps.assistant.free_harness.run_free_harness", side_effect=AssertionError("No harness")), \
                patch("subprocess.Popen", side_effect=AssertionError("No subprocess")):
            result = self.run_local()
        self.assertEqual(set(result), {"message_id", "event_id", "status", "local", "api_calls"})
        self.assertEqual(result["event_id"], str(self.event.pk))
        self.assertEqual(result["status"], "local_completed")
        self.assertIs(result["local"], True)
        self.assertEqual(result["api_calls"], 0)
        self.assertNotIn(speaker.full_name, json.dumps(result))
        message = Message.objects.get(pk=result["message_id"])
        self.assertEqual(message.role, Message.Role.ASSISTANT)
        self.assertIsNone(message.job_id)
        self.assertIn(speaker.full_name, message.content)
        self.assertEqual(message.request_key, "local:" + str(self.key))
        self.assertEqual(Message.objects.count(), 2)
        self.assertEqual(Event.objects.get(pk=self.event.pk).revision, before)
        self.assert_no_ai()

    def test_exact_retry_is_idempotent_and_different_command_conflicts(self):
        first = self.run_local()
        repeated = self.run_local()
        self.assertEqual(first, repeated)
        with self.assertRaises(CommandError):
            self.run_local(command="buscar invitados")
        self.assertEqual(Message.objects.count(), 2)
        self.assert_no_ai()

    def test_default_request_keys_are_distinct_and_all_five_commands_are_supported(self):
        ids = set()
        for command in ("buscar expositores", "buscar participantes", "buscar invitados", "buscar eventos: Ficticio", "personas de este evento"):
            with self.subTest(command=command):
                ids.add(self.run_local(command=command, request_key=None)["message_id"])
        self.assertEqual(len(ids), 5)
        self.assertEqual(Message.objects.count(), 10)
        self.assert_no_ai()

    def test_reviewer_and_inactive_user_are_denied_even_with_own_synthetic_event(self):
        PortalAccount.objects.filter(pk=self.portal.pk).update(role=PortalAccount.Role.REVIEWER)
        with self.assertRaises(CommandError):
            self.run_local()
        PortalAccount.objects.filter(pk=self.portal.pk).update(role=PortalAccount.Role.ORGANIZER)
        get_user_model().objects.filter(pk=self.owner.pk).update(is_active=False)
        with self.assertRaises(CommandError):
            self.run_local()
        self.assertFalse(Message.objects.exists())
        self.assert_no_ai()

    def test_portal_admin_can_run_own_query_but_not_foreign_or_real_event(self):
        PortalAccount.objects.filter(pk=self.portal.pk).update(role=PortalAccount.Role.ADMIN)
        self.run_local()
        with self.assertRaises(CommandError):
            self.run_local(event=str(self.foreign.pk), request_key=None)
        Event.objects.filter(pk=self.event.pk).update(is_synthetic=False)
        with self.assertRaises(CommandError):
            self.run_local(request_key=None)
        self.assertEqual(Message.objects.count(), 2)
        self.assert_no_ai()

    def test_unknown_actor_or_event_does_not_write_messages(self):
        for values in ({"username": "no-such-user"}, {"event": str(uuid.uuid4())}):
            with self.subTest(values=values), self.assertRaises(CommandError):
                self.run_local(**values)
        self.assertFalse(Message.objects.exists())
        self.assert_no_ai()

    def test_malformed_keys_or_general_commands_never_dispatch(self):
        cases = ({"event": "invalid"}, {"request_key": "invalid"}, {"command": "rm -rf /"},
                 {"command": "aprobar plan"}, {"command": "buscar expositores\naprobar plan"},
                 {"command": "buscar eventos:" + "x" * 4000})
        with patch("apps.jobs.management.commands.romeo_local.local_directory_reply") as reply:
            for values in cases:
                with self.subTest(values=list(values)), self.assertRaises(CommandError):
                    self.run_local(**values)
        reply.assert_not_called()
        self.assertFalse(Message.objects.exists())
        self.assert_no_ai()

    def test_idempotent_replay_rechecks_current_role(self):
        original = self.run_local()
        PortalAccount.objects.filter(pk=self.portal.pk).update(role=PortalAccount.Role.REVIEWER)
        with self.assertRaises(CommandError):
            self.run_local()
        self.assertTrue(Message.objects.filter(pk=original["message_id"]).exists())
        self.assertEqual(Message.objects.count(), 2)
        self.assert_no_ai()
