from django.test import TestCase
from apps.events.events import BookingCreated
from apps.events.models import EventDelivery, EventOutbox
from apps.events.outbox import OutboxService
from apps.events.processor import process_pending_deliveries
from unittest.mock import patch
from django.utils import timezone


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

        def test_handler(event, *, delivery_id):
            self.received.append((event, delivery_id))

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
        self.assertEqual(self.received, [(self.event, delivery.pk)])

    def test_failed_handler_is_recorded_for_retry(self):
        from apps.events.dispatcher import subscribe

        def failing_handler(event, *, delivery_id):
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

    @patch("apps.events.processor.notify_dead_delivery")
    def test_dead_delivery_generate_admin_alert(self, mock_notify):
        mock_notify.return_value = True

        event_record = EventOutbox.objects.create(
            event_type="apps.events.events.BookingCreated",
            payload={
                "booking_id": 20,
                "customer_id": 5,
                "service_name": "Haircut"
            },
        )

        delivery = EventDelivery.objects.create(
            event = event_record,
            handler_key="apps.notifications.handlers.handle_booking_created",
            status=EventDelivery.Status.DEAD,
            attempts=5,
            max_attempts=5,
            last_error="Simulated permanent failure",
        )

        from apps.events.processor import process_dead_letter_alerts

        result = process_dead_letter_alerts()

        delivery.refresh_from_db()

        self.assertEqual(result["alerted"], 1)
        self.assertEqual(result["failed"], 0)
        self.assertIsNotNone(delivery.alerted_at)
        mock_notify.assert_called_once()

    @patch("apps.events.processor.notify_dead_delivery")
    def test_failed_alert_remains_pending(self, mock_notify):
        mock_notify.side_effect = RuntimeError("Notification service unavailability")

        event_record = EventOutbox.objects.create(
            event_type = "apps.events.events.BookingCreated",
            payload={
                "booking_id": 20,
                "customer_id": 5,
                "service_name": "Haircut"
            },
        )

        delivery = EventDelivery.objects.create(
            event=event_record,
            handler_key="apps.notifications.handlers.handle_booking_created",
            status=EventDelivery.Status.DEAD,
            attempts=5,
            max_attempts=5,
            last_error="Simulated permanents failure"
        )
        from apps.events.processor import process_dead_letter_alerts

        result = process_dead_letter_alerts()

        delivery.refresh_from_db()

        self.assertEqual(result["alerted"], 0)
        self.assertEqual(result["failed"], 1)
        self.assertIsNone(delivery.alerted_at)







