from unittest.mock import patch
from django.test import SimpleTestCase
from apps.notifications.email.tasks import process_pending_emails_task

class EmailTaskTests(SimpleTestCase):
    @patch("apps.notifications.email.tasks.process_pending_emails")
    def test_task_delegates_to_worker(self, worker):
        worker.return_value = 5

        result = process_pending_emails_task.run(limit=20)

        self.assertEqual(result, 5)
        worker.assert_called_once_with(limit=20)

    @patch("apps.notifications.email.tasks.process_pending_emails")
    def test_task_uses_default_limit(self, worker):
        worker.return_value = 0

        result = process_pending_emails_task.run()

        self.assertEqual(result, 0)
        worker.assert_called_once_with(limit=100)
