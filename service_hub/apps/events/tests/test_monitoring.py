from django.test import TestCase
from apps.events.models import EventDelivery, EventOutbox
from apps.events.monitoring import get_outbox_health_summary

from apps.events.dispatcher import handler_key


class OutboxMonitoringTests(TestCase):
    def setUp(self):
        self.event = EventOutbox.objects.create(
            event_type="apps.events.events.BookingCreated",
            payload={
                "booking_id": 1,
                "customer_id": 1,
                "service_name": "Haircut",
            },
        )

    def test_monitoring_returns_delivery_counts(self):
        EventDelivery.objects.create(
            event=self.event,
            handler_key="test.handler.one",
            status=EventDelivery.Status.PENDING
        )

        EventDelivery.objects.create(
            event=self.event,
            handler_key="test.handler.two",
            status=EventDelivery.Status.SUCCEEDED
        )

        summary = get_outbox_health_summary()

        self.assertEqual(summary["deliveries"]["pending"], 1)
        self.assertEqual(summary["deliveries"]["succeeded"], 1)

    def test_monitoring_detects_unalerted_dead_deliveries(self):
        EventDelivery.objects.create(
            event=self.event,
            handler_key="test.handler.dead",
            status=EventDelivery.Status.DEAD,
            attempts=5,
            max_attempts=5,
            alerted_at=None
        )

        summary = get_outbox_health_summary()

        self.assertEqual(
            summary["unalerted_dead_deliveries"],
            1,
        )

    def test_monitoring_detects_stale_deliveries(self):
        from datetime import timedelta
        from django.utils import timezone

        delivery = EventDelivery.objects.create(
            event=self.event,
            handler_key="test.handler.stale",
            status=EventDelivery.Status.PROCESSING,
            attempts=1,
            processing_started_at=timezone.now() - timedelta(minutes=10)
        )

        summary = get_outbox_health_summary()
        self.assertEqual(summary["stale_deliveries"], 1)
