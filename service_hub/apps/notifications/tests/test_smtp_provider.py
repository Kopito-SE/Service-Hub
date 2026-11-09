import smtplib
from unittest.mock import patch
from django.test import SimpleTestCase
from django.core.mail import BadHeaderError
from apps.notifications.email.providers.smtp import SMTPProvider
from apps.notifications.email.providers.base import EmailSendResult

from apps.notifications.email.providers.exceptions import (
    TemporaryEmailProviderError,
    PermanentEmailProviderError
)

class SMTPProviderTests(SimpleTestCase):
    def setUp(self):
        self.provider = SMTPProvider()
        self.recipient = "customer@example.com"
        self.subject = "Welcome to Service HUB"
        self.body = "Your Account has been created."

    @patch("apps.notifications.email.providers.smtp.EmailMessage")
    def test_send_email_successfully(self, mock_email):
        mock_email.return_value.send.return_value = 1

        result = self.provider.send(
            self.recipient,
            self.subject,
            self.body
        )
        self.assertIsInstance(result, EmailSendResult)

        mock_email.assert_called_once()
        mock_email.return_value.send.assert_called_once_with(
            fail_silently=False
        )
    @patch("apps.notifications.email.providers.smtp.EmailMessage")
    def test_zero_send_count_raises_temporary_error(self, mock_email):
        mock_email.return_value.send.return_value = 0

        with self.assertRaises(TemporaryEmailProviderError):
            self.provider.send(
                self.recipient,
                self.subject,
                self.body
            )
    @patch("apps.notifications.email.providers.smtp.EmailMessage")
    def test_invalid_header_raises_permanent_error(self, mock_email):
        mock_email.side_effect = BadHeaderError(
            "Invalid email header"
        )

        with self.assertRaises(PermanentEmailProviderError):
            self.provider.send(
                self.recipient,
                self.subject,
                self.body
            )
    @patch("apps.notifications.email.providers.smtp.EmailMessage")
    def test_smtp_4xx_response_is_temporary(self, mock_email):
        mock_email.return_value.send.side_effect = (
            smtplib.SMTPDataError(
                451,
                b"Temporary server failure"
            )
        )
        with self.assertRaises(TemporaryEmailProviderError):
            self.provider.send(
                self.recipient,
                self.subject,
                self.body
            )

    @patch("apps.notifications.email.providers.smtp.EmailMessage")
    def test_smtp_5xx_response_is_permanent(self, mock_email):
        mock_email.return_value.send.side_effect = (
            smtplib.SMTPDataError(
                550,
                b"Mailbox Unavailable"
            )
        )
        with self.assertRaises(PermanentEmailProviderError):
            self.provider.send(
                self.recipient,
                self.subject,
                self.body
            )

    @patch("apps.notifications.email.providers.smtp.EmailMessage")
    def test_temporary_recipient_refusal(self, mock_email):
        mock_email.return_value.send.side_effect = (
            smtplib.SMTPRecipientsRefused({
                self.recipient: (
                    450,
                    b"Mailbox temporarily Unavailable"
                )
            })
        )
        with self.assertRaises(TemporaryEmailProviderError):
            self.provider.send(
                self.recipient,
                self.subject,
                self.body
            )

    @patch("apps.notifications.email.providers.smtp.EmailMessage")
    def test_permanent_recipient_refusal(self, mock_email):
        mock_email.return_value.send.side_effect = (
            smtplib.SMTPRecipientsRefused({
                self.recipient: (
                    550,
                    b"Mailbox Unavailable"
                )
            })
        )
        with self.assertRaises(PermanentEmailProviderError):
            self.provider.send(
                self.recipient,
                self.subject,
                self.body
            )

    @patch("apps.notifications.email.providers.smtp.EmailMessage")
    def test_smtp_server_disconnection_is_temporary(self, mock_email):
        mock_email.return_value.send.side_effect = (
            smtplib.SMTPServerDisconnected(
                "Connection unexpectedly closed"
            )
        )

        with self.assertRaises(TemporaryEmailProviderError):
            self.provider.send(
                self.recipient,
                self.subject,
                self.body
            )

    @patch("apps.notifications.email.providers.smtp.EmailMessage")
    def test_unexpected_programming_error_propagates(self, mock_email):
        mock_email.return_value.send.side_effect = TypeError(
            "Unexpected_programming error"
        )

        with self.assertRaises(TypeError):
            self.provider.send(
                self.recipient,
                self.subject,
                self.body
            )

    @patch("apps.notifications.email.providers.smtp.EmailMessage")
    def test_unknown_smtp_exception_is_temporary(self, mock_email):
        mock_email.return_value.send.side_effect = (
            smtplib.SMTPException(
                "Unknown SMTP failure"
            )
        )

        with self.assertRaises(TemporaryEmailProviderError):
            self.provider.send(
                self.recipient,
                self.subject,
                self.body
            )
