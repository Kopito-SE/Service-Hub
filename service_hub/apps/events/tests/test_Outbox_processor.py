from django.test import TestCase

from apps.events.events import BookingCreated
from apps.events.models import EventDelivery, EventOutbox
from apps.events.outbox import OutboxService
from apps.events.processor import process_pending_deliveries

class OutboxProcessorTests(TestCase):

    def setUp(self):
        from apps.events.dispatcher import _handlers

        # Isolate from global handler registry: registry.py auto-registers
        # production handlers on import, so we must clear and restore them
        # to test with only the handlers each test explicitly subscribes.
        self._original_handlers = {k: v.copy() for k, v in _handlers.items()}
        _handlers.clear()

        self.received = []

        self.event = BookingCreated(
            booking_id=20,
            customer_id=5,
            service_name="Haircut"
        )

    def tearDown(self):
        from apps.events.dispatcher import _handlers

        _handlers.clear()
        _handlers.update(self._original_handlers)



    def test_processor_executes_registered_handlers(self):
        from apps.events.dispatcher import subscribe

        def test_handler(event):
            self.received.append(event)

        subscribe(BookingCreated, test_handler)
        event_record = OutboxService.record_event(self.event)

        delivery = EventDelivery.objects.get(
            event=event_record,
            handler_key=(
                f"{test_handler.__module__}."
                f"{test_handler.__qualname__}"
            ),
        )
        result = process_pending_deliveries()

        delivery.refresh_from_db()
        event_record.refresh_from_db()

        self.assertEqual(result["succeeded"], 1)
        self.assertEqual(delivery.status, EventDelivery.Status.SUCCEEDED)
        self.assertEqual(event_record.status, EventOutbox.Status.COMPLETED)
        self.assertEqual(self.received, [self.event])

    def test_failed_handler_is_recorded_for_retry(self):
        from apps.events.dispatcher import subscribe

        def failing_handler(event):
            raise RuntimeError("Simulated failure")

        subscribe(BookingCreated, failing_handler)

        event_record = OutboxService.record_event(self.event)

        delivery = EventDelivery.objects.get(
            event=event_record,
            handler_key=(
                f"{failing_handler.__module__}."
                f"{failing_handler.__qualname__}"
            ),
        )

        result = process_pending_deliveries()

        delivery.refresh_from_db()
        event_record.refresh_from_db()

        self.assertEqual(result["failed"], 1)
        self.assertEqual(delivery.status, EventDelivery.Status.FAILED)
        self.assertEqual(delivery.attempts, 1)
        self.assertIn("Simulated failure", delivery.last_error)
        self.assertEqual(event_record.status, EventOutbox.Status.PROCESSING)

