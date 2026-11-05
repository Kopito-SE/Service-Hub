from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from apps.events.models import EventDelivery, EventDeliveryRetry, EventOutbox
from apps.events.retry_service import DeliveryNotRetryableError, retry_dead_delivery


User = get_user_model()

class ManualRetryServiceTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            username="retry_admin",
            password="test-password",
            is_active=True,
            is_staff=True
        )

        self.event = EventOutbox.objects.create(
            event_type="apps.events.events.BookingCreated",
            payload={
                "booking_id": 10,
                "customer_id": 5,
                "service_name": "Haircut"
            },
            status=EventOutbox.Status.DEAD
        )

        self.delivery = EventDelivery.objects.create(
            event=self.event,
            handler_key="apps.notification.handlers.handle_booking_created",
            status=EventDelivery.Status.DEAD,
            attempts=5,
            max_attempts=5,
            last_error="Notification service unavailable.",
            alerted_at=timezone.now()
        )

    def test_dead_deliveries_can_be_retried(self):
        delivery = retry_dead_delivery(
            delivery_id=self.delivery.pk,
            requested_by=self.admin,
            reason="Notification provider has been restored."
        )

        self.assertEqual(delivery.status, EventDelivery.Status.PENDING)
        self.assertEqual(delivery.manual_retry_count, 1)
        self.assertEqual(delivery.attempts, 0)
        self.assertIsNone(delivery.alerted_at)
        self.assertIsNone(delivery.processing_token)
        self.assertEqual(delivery.last_error, "")

        self.event.refresh_from_db()

        self.assertEqual(self.event.status, EventOutbox.Status.PROCESSING)

    def test_retry_creates_audit_record(self):

        retry_dead_delivery(
            delivery_id=self.delivery.pk,
            requested_by=self.admin,
            reason = "Fixed notification configuration."
        )

        retry_record = EventDeliveryRetry.objects.get(delivery=self.delivery)

        self.assertEqual(retry_record.requested_by, self.admin)
        self.assertEqual(retry_record.retry_number, 1)
        self.assertEqual(retry_record.previous_attempts, 5)
        self.assertEqual(
            retry_record.previous_error,
            "Notification service unavailable."
        )

    def test_succeeded_delivery_cannot_be_retried(self):
        self.delivery.status = EventDelivery.Status.SUCCEEDED
        self.delivery.save(update_fields=["status"])

        with self.assertRaises(DeliveryNotRetryableError):
            retry_dead_delivery(
                delivery_id=self.delivery.pk,
                requested_by=self.admin,
                reason="Retrying a successful delivery."
            )

        self.assertEqual(
            EventDeliveryRetry.objects.count(),
            0
        )

    def test_retry_requires_a_reason(self):
        with self.assertRaises(ValueError):
            retry_dead_delivery(
                delivery_id=self.delivery.pk,
                requested_by=self.admin,
                reason="  "

            )

        self.assertEqual(
            EventDeliveryRetry.objects.count(),
            0
        )