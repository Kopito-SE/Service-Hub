
from django.test import TestCase
from  django.contrib.auth import get_user_model
from django.utils import timezone

from apps.notifications.models import Notification, EmailDelivery
from apps.notifications.email.processor import EmailDeliveryProcessor
from apps.notifications.email.providers.base import EmailSendResult

User = get_user_model()

class NotificationDeliverySyncTests(TestCase):

    def setUp(self):
        self.customer = User.objects.create_user(
            username="sync_customer",
            email="sync@example.com",
            password="test_password"
        )
        self.notification = Notification.objects.create(
            recipient=self.customer,
            channel=Notification.EventType.BOOKING_CREATED,
            subject="Booking received",
            message="Your booking has been received.",
            status=Notification.Status.PENDING
        )

        self.delivery = EmailDelivery.objects.create(
            notification=self.notification,
            recipient_email=self.customer.email,
            subject="Booking received",
            body="Your booking has been received.",
            purpose=EmailDelivery.Purpose.NOTIFICATION,
            status=EmailDelivery.Status.PROCESSING,
            attempts=1,
            max_attempts=5
        )

        self.claim_token = self.delivery.processing_token = (
            __import__("uuid").uuid4()
        )

        self.delivery.processing_started_at = timezone.now()
        self.delivery.save(
            update_fields=[
                "processing_token",
                "processing_started_at"
            ]
        )
        self.processor = EmailDeliveryProcessor(provider=None)

    def test_successful_delivery_marks_notification_sent(self):
        result = EmailSendResult(provider_message_id="test-message-123")

        updated = self.processor.mark_as_sent(
            delivery_id=self.delivery.pk,
            claim_token=self.claim_token,
            result=result
        )

        self.assertTrue(updated)

        self.delivery.refresh_from_db()
        self.notification.refresh_from_db()

        self.assertEqual(
            self.delivery.status,
            EmailDelivery.Status.SENT
        )

        self.assertEqual(
            self.notification.status,
            Notification.Status.SENT
        )

        self.assertIsNotNone(self.notification.sent_at)
        self.assertEqual(
            self.delivery.provider_message_id,
            "test-message-123"
        )

    def test_temporary_failure_keeps_notification_pending(self):
        updated = self.processor.mark_as_failed(
            delivery_id=self.delivery.pk,
            claim_token=self.claim_token,
            error=Exception("Temporary SMTP failure"),
            attempts=1,
            max_attempts=5
        )

        self.assertTrue(updated)

        self.delivery.refresh_from_db()
        self.notification.refresh_from_db()

        self.assertEqual(self.notification.status, Notification.Status.PENDING)
        self.assertEqual(self.notification.failure_reason, "")

    def test_exhausted_failure_marks_notification_failed(self):
        updated = self.processor.mark_as_failed(
            delivery_id=self.delivery.pk,
            claim_token=self.claim_token,
            error=Exception("SMTP permanently Unavailable"),
            attempts=5,
            max_attempts=5
        )
        self.assertTrue(updated)
        self.delivery.refresh_from_db()
        self.notification.refresh_from_db()

        self.assertEqual(self.delivery.status, EmailDelivery.Status.DEAD)
        self.assertEqual(self.notification.status, Notification.Status.FAILED)
        self.assertTrue(self.notification.failure_reason)

    def test_stale_claim_cannot_update_notification(self):
        import uuid

        wrong_token = uuid.uuid4()
        updated = self.processor.mark_as_sent(
            delivery_id=self.delivery.pk,
            claim_token=wrong_token,
            result=EmailSendResult(
                provider_message_id="stale-message"
            ),
        )
        self.assertFalse(updated)

        self.delivery.refresh_from_db()
        self.notification.refresh_from_db()

        self.assertEqual(
            self.delivery.status,
            EmailDelivery.Status.PROCESSING
        )

        self.assertEqual(
            self.notification.status,
            Notification.Status.PENDING
        )

    def test_delivery_without_notification_still_succeeds(self):
        standalone_delivery = EmailDelivery.objects.create(
            notification=None,
            recipient_email="standalone@example.com",
            subject="Authentication code",
            body="Your authentication code is 123456.",
            purpose=EmailDelivery.Purpose.AUTHENTICATION,
            status=EmailDelivery.Status.PROCESSING,
            attempts=1,
            max_attempts=5,
            processing_token=self.claim_token,
            processing_started_at=timezone.now()
        )
        updated = self.processor.mark_as_sent(
            delivery_id=standalone_delivery.pk,
            claim_token=self.claim_token,
            result=EmailSendResult()
        )

        self.assertTrue(updated)

        standalone_delivery.refresh_from_db()

        self.assertEqual(standalone_delivery.status, EmailDelivery.Status.SENT)

    def test_recovery_synchronizes_exhausted_notification(self):
        self.delivery.attempts = 5
        self.delivery.max_attempts = 5
        self.delivery.status = EmailDelivery.Status.FAILED
        self.delivery.save(
            update_fields=["attempts", "max_attempts", "status"]
        )

        recovered = self.processor.recover_exhausted_deliveries()
        self.assertEqual(recovered, 1)

        self.delivery.refresh_from_db()
        self.notification.refresh_from_db()

        self.assertEqual(
            self.delivery.status,
            EmailDelivery.Status.DEAD
        )
        self.assertEqual(
            self.notification.status,
            Notification.Status.FAILED
        )