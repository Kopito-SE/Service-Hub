from unittest.mock import patch
from django.test import SimpleTestCase
from apps.notifications.email.providers.smtp import SMTPProvider
from apps.notifications.email.providers.base import EmailSendResult

class SMTPProviderTests(SimpleTestCase):
    @patch("apps.notifications.email.providers.smtp.EmailMessage")
    def test_send_email_successfully(self, mock_email):
        mock_email.return_value.send.return_value = 1

        provider = SMTPProvider()

        result = provider.send(
            recipient="customer@example.com",
            subject="Welcome to Service Hub",
            body="Your account has been created."
        )

        self.assertIsInstance(result, EmailSendResult)
        mock_email.return_value.send.assert_called_once_with(
            fail_silently=False
        )

    @patch("apps.notifications.email.providers.smtp.EmailMessage")
    def test_send_failure_raises_exceptions(self, mock_email):
        mock_email.return_value.send.side_effect = RuntimeError(
            "SMTP server unavailable"
        )
        provider = SMTPProvider()

        with self.assertRaises(RuntimeError):
            provider.send(
                recipient="customer@example.com",
                subject="Welcome",
                body="Welcome Aboard."

            )