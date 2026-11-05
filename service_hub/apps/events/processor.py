import logging
import threading
from django.db import close_old_connections
from datetime import timedelta
import uuid
from django.db import transaction
from django.db.models import F, Q
from django.utils import timezone

from apps.events.dispatcher import get_handler
from apps.events.event_factory import reconstruct_event
from apps.events.models import EventDelivery, EventOutbox
from apps.events.dead_letter import notify_dead_delivery, mark_delivery_alerted



logger = logging.getLogger(__name__)

# Processor configuration
RECOVERY_TIMEOUT = timedelta(minutes=5)
BASE_RETRY_DELAY = 60
MAX_RETRY_DELAY = 3600

LEASE_RENEWAL_INTERVAL = 60

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
            EventDelivery.objects.select_for_update(skip_locked=True)
            .filter(eligible, attempts__lt=F("max_attempts"))
            .order_by("next_attempt_at", "created_at")
            .first()
        )
        if delivery is None:
            return None

        claim_token = uuid.uuid4()

        delivery.status = EventDelivery.Status.PROCESSING
        delivery.processing_started_at = now
        delivery.processing_token = claim_token
        delivery.attempts += 1

        delivery.save(
            update_fields=[
                "status",
                "processing_started_at",
                "processing_token",
                "attempts",
                "updated_at"
            ]
        )
        return delivery.pk, claim_token

def renew_delivery_lease(delivery_id, claim_token):
    now = timezone.now()

    updated = EventDelivery.objects.filter(
        pk=delivery_id,
        status=EventDelivery.Status.PROCESSING,
        processing_token=claim_token
    ).update(
        processing_started_at=now,
        updated_at=now
    )

    return updated == 1

def _heartbeat_delivery_lease(
        delivery_id,
        claim_token,
        stop_event
):
    while not stop_event.wait(LEASE_RENEWAL_INTERVAL):

        close_old_connections()

        try:
            renewed = renew_delivery_lease(
                delivery_id,
                claim_token
            )

            if not renewed:
                logger.warning(
                    "lease renewal stopped for delivery %s. "
                    "The processing lease is no longer valid.",
                    delivery_id
                )
                return
        except Exception:
            logger.exception(
                "Could not renew lease for delivery %s.",
                delivery_id
            )
        finally:
            close_old_connections()

def _execute_handler_with_heartbeat(
        handler,
        event,
        delivery_id,
        claim_token
):
    stop_event = threading.Event()

    heartbeat_thread = threading.Thread(
        target=_heartbeat_delivery_lease,
        args=(
            delivery_id,
            claim_token,
            stop_event
        ),
        daemon=True,
        name=f"delivery-heartbeat-{delivery_id}"
    )
    heartbeat_thread.start()

    try:
        handler(
            event,
            delivery_id=delivery_id
        )
    finally:
        stop_event.set()

        heartbeat_thread.join(
            timeout=LEASE_RENEWAL_INTERVAL + 5
        )



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

def process_delivery(delivery_id, claim_token):
    """
    Execute one claimed delivery and record its outcome.
    """
    delivery = EventDelivery.objects.select_related("event").filter(
        pk=delivery_id,
        status=EventDelivery.Status.PROCESSING,
        processing_token=claim_token
    ).first()

    if delivery is None:
        logger.warning(
            "Skipping delivery %s because its processing lease is no longer valid.",
            delivery_id
        )
        return

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
        # While automatically renewing the processing lease.
        _execute_handler_with_heartbeat(
            handler=handler,
            event=event,
            delivery_id=delivery_id,
            claim_token=claim_token
        )

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

        updated = EventDelivery.objects.filter(
            pk=delivery_id,
            status=EventDelivery.Status.PROCESSING,
            processing_token=claim_token

        ).update(
            status=new_status,
            last_error=str(exc),
            next_attempt_at=next_attempt,
            processed_at=failed_at,
            processing_started_at=None,
            processing_token=None
        )

        if updated == 0:
            logger.warning(
                "Fencing detected: Delivery % failed, but the lease was already reclaimed. "
                "Failure State discarded.",
                delivery_id
            )
    else:
        processed_at = timezone.now()
        updated = EventDelivery.objects.filter(
            pk=delivery_id,
            status=EventDelivery.Status.PROCESSING,
            processing_token=claim_token

        ).update(
            status=EventDelivery.Status.SUCCEEDED,
            last_error="",
            processed_at=processed_at,
            processing_started_at=None,
            processing_token=None
        )
        if updated == 0:
            logger.warning(
                "Fencing detected:; Delivery %s succeeded, but the lease was already reclaimed. "
                "Success state discarded.",
                delivery_id
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
        "dead": 0,
        "alerts_created": 0,
        "alert_failures": 0
    }

    for _ in range(limit):
        claimed = claim_delivery()

        if claimed is None:
            break

        delivery_id, claim_token = claimed

        process_delivery(delivery_id, claim_token)

        delivery = EventDelivery.objects.get(pk=delivery_id)

        summary["processed"] += 1

        if delivery.status == EventDelivery.Status.SUCCEEDED:
            summary["succeeded"] += 1

        elif delivery.status == EventDelivery.Status.FAILED:
            summary["failed"] += 1

        elif delivery.status == EventDelivery.Status.DEAD:
            summary["dead"] += 1

    alert_summary = process_dead_letter_alerts()
    summary["alerts_created"] = alert_summary["alerted"]
    summary["alert_failures"] = alert_summary["failed"]

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
        processing_started_at=None,
        processing_token=None
    )

    for event_id in event_ids:
        refresh_event_status(event_id)

    return len(event_ids)

def process_dead_letter_alerts(limit=100):
    # Create administrator notifications for
    # dead deliveries that have not been successfully allerted
    deliveries = (
        EventDelivery.objects
        .filter(
            status=EventDelivery.Status.DEAD,
            alerted_at__isnull=True,
        )
        .select_related("event")
        .order_by("created_at")[:limit]
    )
    alerted = 0
    failed = 0

    for delivery in deliveries:
        try:
            created = notify_dead_delivery(delivery)

            if created:
                mark_delivery_alerted(delivery.pk)
                alerted += 1

        except Exception:
            failed += 1

            logger.exception(
                "Could not create administrator alert for delivery %s",
                delivery.pk
            )

    return {
        "alerted": alerted,
        "failed": failed
    }
