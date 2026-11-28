from django.utils import timezone
from apps.notifications.models import Notification, EmailDelivery
from django.db import transaction

from apps.notifications.email.policies import can_send_email


class NotificationService:
    """
    Public service interface for creating notifications.

    Supports both registered customers and guest customers.

    Registered customers:
        - IN_APP notifications
        - EMAIL notifications

    Guest customers:
        - EMAIL notifications only
    """
    @staticmethod
    @transaction.atomic
    def create_notification(
            recipient=None,
            event_type=None,
            subject=None,
            message=None,
            channel=Notification.Channel.IN_APP,
            idempotency_key=None,
            severity=Notification.Severity.INFO,
            recipient_email=None
    ):
        # Validate the requested channel
        if channel not in Notification.Channel.values:
            raise ValueError(f"Unsupported notification channel: {channel}")

        # Validate the event type
        if event_type not in Notification.EventType.values:
            raise ValueError(f"Unsupported notification event: {event_type}")

        # Validate severity
        if severity not in Notification.Severity.values:
            raise ValueError(f"Unsupported notification severity: {severity}")

        # Resolve the destination email.
        resolved_email = (
            recipient_email or getattr(recipient, "email", None)
        )

        if channel == Notification.Channel.IN_APP:
            if recipient is None:
                raise ValueError(
                    "In-app notifications require a registered user."
                )

            if recipient_email is not None:
                raise ValueError(
                    "recipient_email is only supported for email notifications."
                )

            status = Notification.Status.SENT
            sent_at = timezone.now()

        # Validate email Notification
        else:
            if not can_send_email(event_type, severity):
                raise ValueError(
                    "This notification type or severity does not support email delivery"
                )

            if not resolved_email:
                raise ValueError(
                    "An email address required for email notification."
                )

            status = Notification.Status.PENDING
            sent_at = None

        fields = {
            "recipient": recipient,
            "recipient_email": (
                resolved_email
                if channel == Notification.Channel.EMAIL
                else None
            ),
            "channel": channel,
            "event_type": event_type,
            "subject": subject,
            "message": message,
            "status": status,
            "sent_at": sent_at,
            "severity": severity
        }

        # Idempotent or plain create - key decides, Not Channel

        if idempotency_key:
            notification, _created = Notification.objects.get_or_create(
                idempotency_key=idempotency_key,
                defaults=fields
            )

        else:
            notification = Notification.objects.create(**fields)

        # Create email delivery only for email notifications
        if channel == Notification.Channel.EMAIL:
            delivery_key = f"notification-email-{notification.pk}"

            EmailDelivery.objects.get_or_create(
                idempotency_key=delivery_key,
                defaults={
                    "notification": notification,
                    "recipient_email": recipient.email,
                    "subject": subject,
                    "body": message,
                    "purpose": EmailDelivery.Purpose.NOTIFICATION
                },
            )
        return notification