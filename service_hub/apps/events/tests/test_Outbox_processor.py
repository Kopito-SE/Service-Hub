from django.test import TestCase
from apps.events.events import BookingCreated
from apps.events.models import EventDelivery, EventOutbox
from apps.events.outbox import OutboxService
from apps.events.processor import process_pending_deliveries
from unittest.mock import patch
from django.utils import timezone
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from django.db import close_old_connections
from django.test import TransactionTestCase
from apps.events.processor import claim_delivery
from datetime import timedelta
from apps.events.processor import process_delivery
import uuid

from apps.events.dispatcher import handler_key


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

    @patch("apps.events.processor.get_handler")
    def test_expired_claim_does_not_execute_handler(self, mock_get_handler):
        event_record = EventOutbox.objects.create(
            event_type="apps.events.events.BookingCreated",
            payload={
                "booking_id": 25,
                "customer_id": 5,
                "service_name": "Haircut"
            },
        )

        original_claim = timezone.now()

        delivery = EventDelivery.objects.create(
            event=event_record,
            handler_key="test.handler",
            status=EventDelivery.Status.PROCESSING,
            attempts=1,
            processing_started_at=original_claim
        )

        expired_claim_token = uuid.uuid4()
        process_delivery(delivery.pk, expired_claim_token)

        mock_get_handler.assert_not_called()
        delivery.refresh_from_db()

        self.assertEqual(
            delivery.status,
            EventDelivery.Status.PROCESSING
        )

        self.assertEqual(
            delivery.processing_started_at,
            original_claim
        )



class ClaimDeliveryConcurrencyTests(TransactionTestCase):
    def setUp(self):
        self.event = EventOutbox.objects.create(
            event_type="apps.events.events.BookingCreated",
            payload={
                "booking_id": 1,
                "customer_id": 1,
                "service_name": "Haircut",
            },
        )

        for i in range(4):
            EventDelivery.objects.create(
                event=self.event,
                handler_key=f"test.concurrent_handler_{i}",
            )

    def test_multiple_workers_claim_different_deliveries(self):
        worker_count = 4
        barrier = Barrier(worker_count)

        def worker():
            close_old_connections()

            try:
                barrier.wait(timeout=10)
                return claim_delivery()

            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=worker_count) as executor:
            results = list(
                executor.map(
                    lambda _: worker(),
                    range(worker_count)
                )
            )

        delivery_ids = [
            result[0]
            for result in results
            if result is not None
        ]

        self.assertEqual(len(delivery_ids), worker_count)

        self.assertEqual(
            len(delivery_ids),
            len(set(delivery_ids))
        )

    def test_claim_delivery_recovers_expired_lease(self):
        EventDelivery.objects.all().delete()

        event_record = EventOutbox.objects.create(
            event_type="apps.events.events.BookingCreated",
            payload={
                "booking_id": 99,
                "customer_id": 7,
                "service_name": "Haircut"
            },
        )

        old_token = uuid.uuid4()
        dead_worker_time = timezone.now() - timedelta(minutes=10)

        delivery = EventDelivery.objects.create(
            event=event_record,
            handler_key="test.recovery_handler",
            status=EventDelivery.Status.PROCESSING,
            attempts=1,
            max_attempts=3,
            processing_started_at=dead_worker_time,
            processing_token=old_token
        )

        claimed = claim_delivery()

        self.assertIsNotNone(claimed, "claim_delivery should have reclaimed the expired delivery")
        new_delivery_id, new_token = claimed

        self.assertEqual(new_delivery_id, delivery.pk)
        self.assertNotEqual(new_token, old_token)

        delivery.refresh_from_db()

        self.assertEqual(delivery.status, EventDelivery.Status.PROCESSING)
        self.assertEqual(delivery.processing_token, new_token)
        self.assertEqual(delivery.attempts, 2)
        self.assertGreater(delivery.processing_started_at, dead_worker_time)







