import uuid
from datetime import timedelta
from unittest.mock import MagicMock
from django.test import TestCase
from django.utils import timezone
from apps.notifications.models import EmailDelivery

from apps.notifications.email.processor import (
    EmailDeliveryProcessor,
    BASE_RETRY_DELAY,
    MAX_RETRY_DELAY,
    RECOVERY_TIMEOUT
)

from apps.notifications.email.providers.base import EmailProvider, EmailSendResult
from apps.notifications.email.providers.exceptions import (
    TemporaryEmailProviderError,
    PermanentEmailProviderError
)

class EmailDeliveryProcessingTests(TestCase):
    def setUp(self):
        self.provider = MagicMock(spec=EmailProvider)

        self.provider.send.return_value = EmailSendResult(
            provider_message_id="smtp-message-001"
        )

        self.processor = EmailDeliveryProcessor(
            provider=self.provider
        )

        self.now = timezone.now()

    def create_delivery(self, **kwargs):
        defaults = {
            "recipient_email": "customer@example.com",
            "subject": "Test email",
            "body": "This is a test email",
            "purpose": EmailDelivery.Purpose.NOTIFICATION,
            "status": EmailDelivery.Status.PROCESSING,
            "attempts": 1,
            "max_attempts": 3,
            "processing_started_at": self.now,
            "processing_token": "12345678-1234-5678-1234-567812345678",
            "next_attempt_at": self.now
        }
        defaults.update(kwargs)

        return EmailDelivery.objects.create(**defaults)
    #=====================================================
    # 1. Successful email delivery
    #====================================================
    def test_successful_delivery_is_marked_as_sent(self):
        delivery = self.create_delivery()

        result = self.processor.process_delivery(
            delivery.pk,
            delivery.processing_token
        )

        self.assertTrue(result)

        self.provider.send.assert_called_once_with(
            recipient=delivery.recipient_email,
            subject=delivery.subject,
            body=delivery.body
        )
        delivery.refresh_from_db()

        self.assertEqual(delivery.status,  EmailDelivery.Status.SENT)
        self.assertEqual(delivery.provider_message_id, "smtp-message-001")

        self.assertIsNone(delivery.processing_started_at)
        self.assertIsNotNone(delivery.sent_at)

        self.assertIsNone(delivery.processing_token)
        self.assertEqual(delivery.last_error, "")

    #===============================================================
    # 2. Temporary Provider Failure
    #================================================================
    def test_temporary_failure_schedules_retry(self):
        self.provider.send.side_effect = TemporaryEmailProviderError(
            "SMTP server temporarily unavailable."
        )
        delivery = self.create_delivery()

        result = self.processor.process_delivery(
            delivery.pk,
            delivery.processing_token
        )

        self.assertTrue(result)
        delivery.refresh_from_db()

        self.assertEqual(delivery.status, EmailDelivery.Status.FAILED)
        self.assertEqual(delivery.attempts, 1)

        self.assertIsNotNone(delivery.next_attempt_at)
        self.assertGreater(delivery.next_attempt_at, timezone.now())

        self.assertIsNone(delivery.processing_started_at)
        self.assertIsNone(delivery.processing_token)

        self.assertIn("temporarily unavailable", delivery.last_error)

    #=======================================================================
    # 3. Permanent Provider Failure
    #=======================================================================

    def test_permanent_failure_marks_delivery_dead(self):

        self.provider.send.side_effect = PermanentEmailProviderError(
            "Recipient email address rejected."
        )

        delivery = self.create_delivery()

        result = self.processor.process_delivery(
            delivery.pk,
            delivery.processing_token
        )

        self.assertTrue(result)

        delivery.refresh_from_db()

        self.assertEqual(
            delivery.status,
            EmailDelivery.Status.DEAD
        )

        self.assertIn("rejected", delivery.last_error)

        self.assertIsNone(delivery.processing_token)
        self.assertIsNone(delivery.processing_started_at)

    #=======================================================================
    # 4. Temporary failure on the final attempt
    #=======================================================================
    def test_exhausted_attempts_mark_delivery_dead(self):

        self.provider.send.side_effect = TemporaryEmailProviderError(
            "SMTP server unavailable."
        )

        delivery = self.create_delivery(
            attempts=3,
            max_attempts=3
        )

        result = self.processor.process_delivery(
            delivery.pk,
            delivery.processing_token
        )

        self.assertTrue(result)

        delivery.refresh_from_db()

        self.assertEqual(delivery.status, EmailDelivery.Status.DEAD)

    #============================================================================
    # 5. Invalid claim token prevents sending
    #============================================================================
    def test_invalid_claim_token_prevents_processing(self):
        delivery = self.create_delivery()
        invalid_token = "87654321-4321-8765-4321-876543218765"

        result = self.processor.process_delivery(
            delivery.pk,
            invalid_token
        )

        self.assertFalse(result)
        self.provider.send.assert_not_called()

        delivery.refresh_from_db()

        self.assertEqual(
            delivery.status,
            EmailDelivery.Status.PROCESSING
        )

    #============================================================================
    # 6. Old worker cannot update a reclaimed delivery
    #==========================================================================
    def test_old_claim_token_cannot_update_delivery(self):

        delivery = self.create_delivery()
        old_token = delivery.processing_token
        new_token = uuid.UUID("87654321-4321-8765-4321-876543218765")

        delivery.processing_token = new_token
        delivery.save(update_fields=["processing_token"])

        result = self.processor.mark_as_sent(
            delivery_id=delivery.pk,
            claim_token=old_token,
            result=EmailSendResult(
                provider_message_id="old-worker-message"
            ),
        )

        self.assertFalse(result)

        delivery.refresh_from_db()

        self.assertEqual(delivery.status, EmailDelivery.Status.PROCESSING)
        self.assertEqual(delivery.processing_token, new_token)

    #=======================================================
    # 7. Exponential retry Calculation
    #======================================================
    def test_retry_calculation_uses_exponential_backoff(self):
        attempts = [1, 2, 3, 4]

        for attempt in attempts:
            before = timezone.now()

            retry_time = self.processor.calculate_retry_time(attempt)

            after = timezone.now()

            expected_delay = min(
                BASE_RETRY_DELAY * (2 ** (attempt - 1)),
                MAX_RETRY_DELAY
            )

            self.assertGreaterEqual(
                retry_time,
                before + timedelta(seconds=expected_delay)
            )

            self.assertLessEqual(
                retry_time,
                after + timedelta(seconds=expected_delay)
            )

    #========================================================================
    # 8. Retry delay is capped at one hour
    #========================================================================
    def test_retry_delay_does_not_exceed_maximum(self):

        before = timezone.now()
        retry_time=self.processor.calculate_retry_time(20)
        after=timezone.now()

        expected_delay = timedelta(
            seconds=MAX_RETRY_DELAY
        )
        self.assertGreaterEqual(
            retry_time,
            before + expected_delay
        )
        self.assertLessEqual(
            retry_time,
            after + expected_delay
        )

    #==============================================================================
    # 9. Exhausted FAILED deliveries are recovered.
    #==============================================================================
    def test_exhausted_failed_delivery_is_marked_dead(self):
        delivery = self.create_delivery(
            status=EmailDelivery.Status.FAILED,
            attempts=3,
            max_attempts=3,
            processing_started_at=None,
            processing_token=None
        )

        recovered = self.processor.recover_exhausted_deliveries()
        self.assertEqual(recovered, 1)

        delivery.refresh_from_db()

        self.assertEqual(
            delivery.status,
            EmailDelivery.Status.DEAD
        )

        self.assertIn("Maximum delivery attempts exhausted.", delivery.last_error)

    #=================================================================================
    # 10. Expired exhausted deliveries are recovered
    #================================================================================
    def test_exhausted_processing_delivery_is_recovered(self):
        expired_time = (timezone.now() - RECOVERY_TIMEOUT - timedelta(seconds=1))

        delivery = self.create_delivery(
            status=EmailDelivery.Status.PROCESSING,
            attempts=3,
            max_attempts=3,
            processing_started_at=expired_time
        )

        recovered = self.processor.recover_exhausted_deliveries()

        self.assertEqual(recovered, 1)
        delivery.refresh_from_db()

        self.assertEqual(
            delivery.status,
            EmailDelivery.Status.DEAD
        )

        self.assertIsNone(delivery.processing_started_at)
        self.assertIsNone(delivery.processing_token)

    #==============================================================================
    # 11. Fresh exhausted PROCESSING delivery is not Recovered
    #===============================================================================
    def test_fresh_exhausted_processing_delivery_is_not_recovered(self):
        delivery = self.create_delivery(
            status=EmailDelivery.Status.PROCESSING,
            attempts=3,
            max_attempts=3,
            processing_started_at=timezone.now()
        )

        recovered = self.processor.recover_exhausted_deliveries()
        self.assertEqual(recovered, 0)

        delivery.refresh_from_db()

        self.assertEqual(delivery.status, EmailDelivery.Status.PROCESSING)


    #======================================================================
    # 12. Unexpected provider errors propagate.
    #======================================================================

    def test_unexpected_provider_error_propagates(self):
        self.provider.send.side_effect = TypeError(
            "Unexpected programming error."
        )

        delivery = self.create_delivery()
        with self.assertRaises(TypeError):
            self.processor.process_delivery(
                delivery.pk,
                delivery.processing_token
            )

        delivery.refresh_from_db()

        self.assertEqual(delivery.status, EmailDelivery.Status.PROCESSING)
