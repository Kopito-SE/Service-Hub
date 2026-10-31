import logging
from datetime import timedelta

from django.db import transaction
from django.db.models import F, Q
from django.utils import timezone

from apps.events.dispatcher import get_handler
from apps.events.event_factory import reconstruct_event
from apps.events.models import EventDelivery, EventOutbox

logger = logging.getLogger(__name__)

# Processor configuration
RECOVERY_TIMEOUT = timedelta(minutes=5)
BASE_RETRY_DELAY = 60
MAX_RETRY_DELAY = 3600

def claim_delivery():
    """
    Atomically claim one delivery that is ready for processing.

    Returns:
        (delivery_id, claim_timestamp), or None if no delivery is available.
    """
    now = timezone.now()
    recovery_cutoff = now - RECOVERY_TIMEOUT

    eligible = (
        Q(
            status=EventDelivery.Status.PENDING,
            next_attempt_at__lte=now
        )
        | Q(
            status=EventDelivery.Status.FAILED,
            next_attempt_at__lte=now
        )
        | Q(
            status=EventDelivery.Status.PROCESSING,
            processing_started_at__lte=recovery_cutoff
        )
    )
    with transaction.atomic():
        delivery = (
            EventDelivery.objects
            .select_for_update()
            .filter(eligible, attempts__lt=F("max_attempts"))
            .order_by("next_attempt_at", "created_at")
            .first()
        )
        if delivery is None:
            return None

        delivery.status = EventDelivery.Status.PROCESSING
        delivery.processing_started_at = now
        delivery.attempts += 1

        delivery.save(
            update_fields=[
                "status",
                "processing_started_at",
                "attempts",
                "updated_at"
            ]
        )
        return delivery.pk, now

def calculate_retry_time(attempts):
    """
    Calculate Exponential Backoff with a maximum delay of one hour.

    """
    delay = min(
        BASE_RETRY_DELAY * (2 ** (attempts - 1)),
        MAX_RETRY_DELAY
    )

    return timezone.now() + timedelta(seconds=delay)

def refresh_event_status(event_id):
    """
    Update the overall event status based on its individual deliveries.
    """
    deliveries = EventDelivery.objects.filter(event_id=event_id)
    statuses = list(
        deliveries.values_list("status", flat=True)
    )

    if not statuses:
        return
    terminal_statuses = {
        EventDelivery.Status.SUCCEEDED,
        EventDelivery.Status.DEAD
    }

    if all(status in terminal_statuses for status in statuses):
        if EventDelivery.Status.DEAD in statuses:
            new_status = EventOutbox.Status.DEAD
        else:
            new_status = EventOutbox.Status.COMPLETED

        EventOutbox.objects.filter(pk=event_id).update(
            status=new_status,
            completed_at=timezone.now()
        )
    else:
        EventOutbox.objects.filter(pk=event_id).update(
            status=EventOutbox.Status.PROCESSING,
            completed_at=None
        )

def process_delivery(delivery_id, claim_timestamp):
    """
    Execute one claimed delivery and record its outcome.
    """
    delivery = (EventDelivery.objects.select_related("event").get(pk=delivery_id))
    try:
        event_record = delivery.event
        event = reconstruct_event(event_record.event_type,event_record.payload)
        event_class = type(event)

        handler = get_handler(event_class,delivery.handler_key)

        if handler is None:
            raise LookupError(
                f"Handler not registered: {delivery.handler_key}"
            )
        # Execute outside the database transaction.
        handler(event)

    except Exception as exc:
        logger.exception(
            "Delivering %s failed on attempt %s",
            delivery_id,
            delivery.attempts
        )

        failed_at = timezone.now()

        if delivery.attempts >= delivery.max_attempts:
            new_status = EventDelivery.Status.DEAD
            next_attempt = delivery.next_attempt_at
        else:
            new_status = EventDelivery.Status.FAILED
            next_attempt = calculate_retry_time(delivery.attempts)

        EventDelivery.objects.filter(
            pk=delivery_id,
            status=EventDelivery.Status.PROCESSING,
            processing_started_at=claim_timestamp
        ).update(
            status=new_status,
            last_error=str(exc),
            next_attempt_at=next_attempt,
            processed_at=failed_at,
            processing_started_at=None
        )
    else:
        processed_at = timezone.now()
        EventDelivery.objects.filter(
            pk=delivery_id,
            status=EventDelivery.Status.PROCESSING,
            processing_started_at=claim_timestamp
        ).update(
            status=EventDelivery.Status.SUCCEEDED,
            last_error="",
            processed_at=processed_at,
            processing_started_at=None
        )
    refresh_event_status(delivery.event_id)

def process_pending_deliveries(limit=100):
    """
    Process up to `limit` eligible deliveries.
    Returns a summary of processing outcomes.
    """
    recover_exhausted_deliveries()

    summary = {
        "processed": 0,
        "succeeded": 0,
        "failed": 0,
        "dead": 0
    }
    for _ in range(limit):
        claimed = claim_delivery()

        if claimed is None:
            break

        delivery_id, claim_timestamp = claimed

        process_delivery(
            delivery_id,
            claim_timestamp
        )

        delivery = EventDelivery.objects.get(pk=delivery_id)

        summary["processed"] += 1

        if delivery.status == EventDelivery.Status.SUCCEEDED:
            summary["succeeded"] += 1

        elif delivery.status == EventDelivery.Status.FAILED:
            summary["failed"] += 1

        elif delivery.status == EventDelivery.Status.DEAD:
            summary["dead"] += 1

    return summary

def recover_exhausted_deliveries():
    """
    Mark abandoned processing deliveries as DEAD when no attempts remain.
    """
    cutoff = timezone.now() - RECOVERY_TIMEOUT

    exhausted = EventDelivery.objects.filter(
        status=EventDelivery.Status.PROCESSING,
        processing_started_at__lte=cutoff,
        attempts__gte=F("max_attempts")
    )

    event_ids = list(
        exhausted.values_list("event_id", flat=True).distinct()
    )

    exhausted.update(
        status=EventDelivery.Status.DEAD,
        last_error="Processing abandoned after maximum attempts.",
        processed_at=timezone.now(),
        processing_started_at=None
    )

    for event_id in event_ids:
        refresh_event_status(event_id)

    return len(event_ids)