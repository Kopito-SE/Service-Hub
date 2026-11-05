from django.db import transaction
from django.utils import timezone

from apps.events.models import (EventDelivery, EventDeliveryRetry, EventOutbox)

class DeliveryNotRetryableError(Exception):
    pass

@transaction.atomic
def retry_dead_delivery(delivery_id, requested_by, reason):
    delivery = (
        EventDelivery.objects.select_for_update().get(pk=delivery_id)
    )
    if delivery.status != EventDelivery.Status.DEAD:
        raise DeliveryNotRetryableError(
            f"Only Dead deliveries can be manually retried."
            f"Current Status is :{delivery.status}"
        )

    reason = reason.strip()

    if not reason:
        raise ValueError("A retry reason is required.")

    next_retry_number = delivery.manual_retry_count + 1

    # Preserve the previous failure information
    EventDeliveryRetry.objects.create(
        delivery=delivery,
        requested_by=requested_by,
        retry_number=next_retry_number,
        previous_attempts=delivery.attempts,
        previous_error=delivery.last_error,
        reason=reason
    )

    #Reopen the delivery.
    delivery.status = EventDelivery.Status.PENDING
    delivery.attempts = 0
    delivery.manual_retry_count=next_retry_number

    delivery.next_attempt_at = timezone.now()

    delivery.last_error = ""
    delivery.processing_started_at = None
    delivery.process_token = None
    delivery.processed_at = None

    # Allow a new alert if this delivery eventually becomes dead
    delivery.alerted_at = None

    delivery.save(update_fields = [
        "status",
        "attempts",
        "manual_retry_count",
        "next_attempt_at",
        "last_error",
        "processing_started_at",
        "processing_token",
        "processed_at",
        "alerted_at",
        "updated_at"
    ])

    # Reopen the parent event
    EventOutbox.objects.filter(
        pk=delivery.event_id
    ).update(
        status=EventOutbox.Status.PROCESSING,
        completed_at=None
    )

    return delivery