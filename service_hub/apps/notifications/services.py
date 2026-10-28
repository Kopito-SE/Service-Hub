from django.utils import timezone
from apps.notifications.models import Notification

class NotificationService:
    """
        Public service interface for creating notifications.

        Other components should use this service instead of
        creating Notification objects directly.
    """
    @staticmethod
    def create_notification(
            recipient,
            event_type,
            subject,
            message,
            channel=Notification.Channel.IN_APP
    ):
        # Validate the requested channel.
        valid_channels = Notification.Channel.values

        if channel not in valid_channels:
            raise ValueError(f"Unsupported notification channel: {channel}")

        # Validate the event type.
        valid_events = Notification.EventType.values

        if event_type not in valid_events:
            raise ValueError(f"Unsupported notification event: {event_type}")

        # In-app notifications are immediately available to the user.
        # Email notifications remain pending until delivery is implemented.

        if channel == Notification.Channel.IN_APP:
            return Notification.objects.create(
                recipient=recipient,
                channel=channel,
                event_type=event_type,
                subject=subject,
                message=message,
                status=Notification.Status.SENT,
                sent_at = timezone.now()
            )

        return Notification.objects.create(
            recipient=recipient,
            channel=channel,
            event_type=event_type,
            subject=subject,
            message=message,
            status=Notification.Status.PENDING
        )