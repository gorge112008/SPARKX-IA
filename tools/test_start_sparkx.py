"""One platform entry point; credentials are configured in its private panel."""
from contextlib import redirect_stdout
from io import StringIO
import os
import unittest
from unittest.mock import MagicMock, patch
from tools.start_sparkx import main


class PlatformLauncherTests(unittest.TestCase):
    @patch.dict(os.environ, {}, clear=True)
    @patch("tools.start_sparkx.socket.create_connection", side_effect=ConnectionRefusedError)
    @patch("django.core.management.execute_from_command_line")
    def test_platform_and_agent_start_without_console_credential(self, execute, port):
        with redirect_stdout(StringIO()):
            self.assertEqual(main(), 0)
        execute.assert_called_once_with(["manage.py", "runromeo"])
        self.assertNotIn("OPENAI_API_KEY", os.environ)

    @patch.dict(os.environ, {"OPENAI_API_KEY": "private-inherited-test-key"}, clear=True)
    @patch("tools.start_sparkx.socket.create_connection", side_effect=ConnectionRefusedError)
    @patch("django.core.management.execute_from_command_line")
    def test_inherited_secret_never_appears_in_console(self, execute, port):
        output = StringIO()
        with redirect_stdout(output):
            self.assertEqual(main(), 0)
        self.assertNotIn("private-inherited-test-key", output.getvalue())
        self.assertNotIn("OPENAI_API_KEY", os.environ)

    @patch("tools.start_sparkx.socket.create_connection", return_value=MagicMock())
    @patch("django.core.management.execute_from_command_line")
    def test_existing_listener_is_preserved(self, execute, port):
        with redirect_stdout(StringIO()):
            self.assertEqual(main(), 1)
        execute.assert_not_called()
