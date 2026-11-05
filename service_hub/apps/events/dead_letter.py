import logging
from django.contrib.auth import get_user_model
from django.utils import timezone

from apps.notifications.models import Notification
from apps.notifications.services import NotificationService

logger = logging.getLogger(__name__)

User = get_user_model()

def notify_dead_delivery(delivery):
    """
    Create an in-app system alert for every active platform administrator.

    Each administrator receives at most one alert for a particular
    dead-letter delivery
    """
    administrators = User.objects.filter(
        is_staff=True,
        is_active=True
    )

    if not administrators.exists():
        logger.warning(
            "Dead-letter delivery %s has no active platform administrators.",
            delivery.pk
        )
        return False
    event_type = delivery.event.event_type

    subject = "Service Hub: Event delivery permanently failed"

    message = (
        f"An event delivery has permanently failed.\n\n"
        f"Delivery ID: {delivery.pk}\n"
        f"Event_type: {event_type}\n"
        f"Handler: {delivery.handler_key}\n"
        f"Attempts:{delivery.attempts}/{delivery.max_attempts}\n"
        f"Last error: {delivery.last_error}\n\n"
        "This failure requires manual Intervention, please look at it in System logs"
    )

    for administrator in administrators.iterator():
        NotificationService.create_notification(
            recipient=administrator,
            event_type=Notification.EventType.SYSTEM_ALERT,
            subject=subject,
            message=message,
            idempotency_key=(
                f"dead-letter-{delivery.pk}-admin-{administrator.pk}"
                if delivery.manual_retry_count == 0
                else (
                    f"dead-letter-{delivery.pk}-retry-"
                    f"{delivery.manual_retry_count}-admin-{administrator.pk}"
                )
            ),
        )
    return True

def mark_delivery_alerted(delivery_id):
    """
    Mark a delivery as alerted after its administrator notifications
    have been successfully recorded.
    """
    from apps.events.models import EventDelivery

    return EventDelivery.objects.filter(
        pk=delivery_id,
        status=EventDelivery.Status.DEAD,
        alerted_at__isnull=True,
    ).update(alerted_at=timezone.now())