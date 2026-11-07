
import smtplib
import socket

from django.conf import settings
from django.core.mail import BadHeaderError, EmailMessage

from apps.notifications.email.providers.base import (
    EmailProvider,
    EmailSendResult,
)

from apps.notifications.email.providers.exceptions import (
    TemporaryEmailProviderError,
    PermanentEmailProviderError,
)


class SMTPProvider(EmailProvider):

    def send(
        self,
        recipient: str,
        subject: str,
        body: str,
    ) -> EmailSendResult:

        try:
            email = EmailMessage(
                subject=subject,
                body=body,
                from_email=settings.DEFAULT_FROM_EMAIL,
                to=[recipient],
            )

            send_count = email.send(fail_silently=False)

            if send_count != 1:
                raise TemporaryEmailProviderError(
                    "SMTP backend did not report a successful send."
                )

            return EmailSendResult()

        except BadHeaderError as e:
            raise PermanentEmailProviderError(
                f"Invalid email header: {e}"
            ) from e

        except smtplib.SMTPRecipientsRefused as e:
            response_codes = [
                code
                for code, _message in e.recipients.values()
            ]

            if response_codes and all(
                400 <= code < 500 for code in response_codes
            ):
                raise TemporaryEmailProviderError(
                    f"Recipient temporarily refused: {e.recipients}"
                ) from e

            raise PermanentEmailProviderError(
                f"Recipient permanently refused: {e.recipients}"
            ) from e

        except smtplib.SMTPResponseException as e:
            if 400 <= e.smtp_code < 500:
                raise TemporaryEmailProviderError(
                    f"Temporary SMTP error "
                    f"{e.smtp_code}: {e.smtp_error}"
                ) from e

            raise PermanentEmailProviderError(
                f"Permanent SMTP error "
                f"{e.smtp_code}: {e.smtp_error}"
            ) from e

        except smtplib.SMTPServerDisconnected as e:
            raise TemporaryEmailProviderError(
                f"SMTP server disconnected: {e}"
            ) from e

        except (
            socket.timeout,
            TimeoutError,
            ConnectionError,
            OSError,
        ) as e:
            raise TemporaryEmailProviderError(
                f"SMTP network error "
                f"{type(e).__name__}: {e}"
            ) from e

        except smtplib.SMTPException as e:
            raise TemporaryEmailProviderError(
                f"Unclassified SMTP error "
                f"{type(e).__name__}: {e}"
            ) from e
