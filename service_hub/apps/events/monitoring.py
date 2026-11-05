from datetime import timedelta

from OpenSSL.rand import status
from django.db.models import Count, Q
from django.utils import timezone
from apps.events.models import EventDelivery, EventOutbox

def get_outbox_health_summary():
    now = timezone.now()

    stale_cutoff = now - timedelta(minutes=5)
    event_counts = EventOutbox.objects.aggregate(
        pending=Count(
            "id",
            filter=Q(status=EventOutbox.Status.PENDING),
        ),
        processing=Count(
            "id",
            filter=Q(status=EventOutbox.Status.PROCESSING),

        ),
        completed=Count(
            "id",
            filter=Q(status=EventOutbox.Status.COMPLETED)

        ),
        dead=Count(
            "id",
            filter=Q(status=EventOutbox.Status.DEAD),
        ),
    )

    delivery_counts = EventDelivery.objects.aggregate(
        pending=Count(
            "id",
            filter=Q(status=EventDelivery.Status.PENDING),
        ),
        processing=Count(
            "id",
            filter=Q(status=EventDelivery.Status.PROCESSING),
        ),
        succeeded=Count(
            "id",
            filter=Q(status=EventDelivery.Status.SUCCEEDED),
        ),
        failed=Count(
            "id",
            filter=Q(status=EventDelivery.Status.FAILED),
        ),
        dead=Count(
            "id",
            filter=Q(status=EventDelivery.Status.DEAD),
        ),
    )

    stale_deliveries = EventDelivery.objects.filter(
        status=EventDelivery.Status.PROCESSING,
        processing_started_at__lte=stale_cutoff
    ).count()

    unalerted_dead_deliveries = EventDelivery.objects.filter(
        status=EventDelivery.Status.DEAD,
        alerted_at__isnull=True
    ).count()

    return {
        "events": event_counts,
        "deliveries": delivery_counts,
        "stale_deliveries": stale_deliveries,
        "unalerted_dead_deliveries": unalerted_dead_deliveries,
        "generated_at": now
    }