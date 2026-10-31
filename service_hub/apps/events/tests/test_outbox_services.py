from django.test import TestCase
from apps.events.dispatcher import dispatch, subscribe, _handlers
from apps.events.events import BookingCreated
from apps.events.outbox import OutboxService
from apps.events.models import EventOutbox, EventDelivery
from apps.events.dispatcher import get_handler, handler_key
from django.db import transaction


class OutboxServiceTests(TestCase):
    def test_record_event_creates_outbox_and_deliverables(self):
        event = BookingCreated(
            booking_id=15,
            customer_id=8,
            service_name="Haircut"
        )

        event_record = OutboxService.record_event(event)

        self.assertEqual(EventOutbox.objects.count(), 1)

        self.assertEqual(
            event_record.event_type,
            "apps.events.events.BookingCreated"
        )

        self.assertEqual(
            event_record.payload["booking_id"],
            15
        )

        self.assertEqual(
            event_record.payload["customer_id"],
            8
        )

        self.assertEqual(
            event_record.payload["service_name"],
            "Haircut",
        )

        deliveries = EventDelivery.objects.filter(
            event=event_record
        )

        self.assertGreater(deliveries.count(), 0)
        for delivery in deliveries:
            self.assertEqual(
                delivery.status,
                EventDelivery.Status.PENDING
            )
            self.assertEqual(delivery.attempts,0)
    def test_record_events_reject_non_dataclass(self):
        with self.assertRaises(TypeError):
            OutboxService.record_event({"booking_id": 15})

    def test_get_handler_by_key(self):
        def sample_handler(event):
            pass

        subscribe(BookingCreated, sample_handler)
        key = handler_key(sample_handler)

        self.assertIs(
            get_handler(BookingCreated, key),
            sample_handler
        )

    def test_event_is_rolled_back_with_outer_transaction(self):
        event = BookingCreated(
            booking_id=15,
            customer_id=8,
            service_name="Haircut",
        )

        with self.assertRaises(RuntimeError):
            with transaction.atomic():
                OutboxService.record_event(event)
                raise RuntimeError("Simulated booking failure")

        self.assertEqual(EventOutbox.objects.count(), 0)
        self.assertEqual(EventDelivery.objects.count(),0)