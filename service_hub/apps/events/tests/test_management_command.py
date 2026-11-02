from io import StringIO

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import SimpleTestCase
from unittest.mock import patch

class ProcessOutboxCommandTests(SimpleTestCase):
    @patch("apps.events.management.commands.process_outbox.process_pending_deliveries")
    def test_command_processes_deliveries(self, mock_processor):
        mock_processor.return_value = {
            "processed": 5,
            "succeeded": 3,
            "failed": 1,
            "dead": 1,
            "alerts_created": 0,
            "alert_failures": 0
        }

        output = StringIO()

        call_command(
            "process_outbox",
            stdout=output
        )

        mock_processor.assert_called_once_with(limit=100)

        self.assertIn("Processed: 5", output.getvalue())
        self.assertIn("Succeeded: 3", output.getvalue())
        self.assertIn("Failed: 1", output.getvalue())
        self.assertIn("Dead: 1", output.getvalue())

    @patch("apps.events.management.commands.process_outbox.process_pending_deliveries")
    def test_command_accepts_custom_limit(self, mock_processor):
        mock_processor.return_value = {
            "processed": 0,
            "succeeded": 0,
            "failed": 0,
            "dead": 0,
            "alerts_created": 0,
            "alert_failures": 0
        }

        call_command("process_outbox", limit=25)

        mock_processor.assert_called_once_with(limit=25)

    def test_command_reject_zero_limit(self):
        with self.assertRaises(CommandError):
            call_command("process_outbox", limit=0)



