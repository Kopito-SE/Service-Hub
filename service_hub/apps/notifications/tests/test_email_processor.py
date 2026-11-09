import uuid
import threading
from datetime import timedelta
from unittest.mock import MagicMock

from django.test import TestCase, TransactionTestCase
from django.utils import timezone
from django.db import connections

from apps.notifications.models import EmailDelivery
from apps.notifications.email.providers.base import EmailProvider
from apps.notifications.email.processor import (
    EmailDeliveryProcessor,
    RECOVERY_TIMEOUT,
)

class EmailDeliveryProcessorTests(TestCase):

    def setUp(self):
        self.provider = MagicMock(spec=EmailProvider)
        self.processor = EmailDeliveryProcessor(
            provider=self.provider
        )
        self.now = timezone.now()

    def create_delivery(self, **kwargs):
        defaults = {
            "recipient_email": "customer@example.com",
            "subject": "Test email",
            "body": "Testing email",
            "purpose": EmailDelivery.Purpose.NOTIFICATION,
            "status": EmailDelivery.Status.PENDING,
            "next_attempt_at": self.now - timedelta(minutes=1),
            "attempts": 0,
            "max_attempts": 3
        }
        defaults.update(kwargs)

        return EmailDelivery.objects.create(**defaults)

    #---------------------------------------------------
    # 1. Pending Email is created successfully.
    #---------------------------------------------------

    def test_pending_email_is_claimed(self):
        delivery = self.create_delivery()

        result = self.processor.claim_delivery()
        self.assertIsNotNone(result)

        pk, token = result

        self.assertEqual(pk, delivery.pk)
        self.assertIsInstance(token, uuid.UUID)

        delivery.refresh_from_db()

        self.assertEqual(delivery.status, EmailDelivery.Status.PROCESSING)
        self.assertEqual(delivery.attempts, 1)
        self.assertIsNotNone(delivery.processing_started_at)

    #------------------------------------------------------
    # 2. Future-schedule email is not claimed
    #------------------------------------------------------

    def test_future_scheduled_email_is_not_claimed(self):
        self.create_delivery(
            next_attempt_at=self.now + timedelta(hours=1)
        )

        result = self.processor.claim_delivery()
        self.assertIsNone(result)

    #-------------------------------------------------------
    # 3.  Fresh processing lease is not reclaimed.
    #-------------------------------------------------------

    def test_fresh_processing_lease_is_not_claimed(self):
        original_token = uuid.uuid4()

        delivery = self.create_delivery(
            status=EmailDelivery.Status.PROCESSING,
            processing_started_at=self.now,
            processing_token=original_token,
            attempts=1
        )

        result = self.processor.claim_delivery()
        self.assertIsNone(result)

        delivery.refresh_from_db()

        self.assertEqual(delivery.status, EmailDelivery.Status.PROCESSING)
        self.assertEqual(delivery.processing_token, original_token)
        self.assertEqual(delivery.attempts, 1)

    #----------------------------------------------------------
    # 4. Expired processing lease can be reclaimed
    #----------------------------------------------------------

    def test_expired_processing_lease_can_be_reclaimed(self):
        expired_time = self.now - RECOVERY_TIMEOUT - timedelta(seconds=1)
        old_token = uuid.uuid4()

        delivery = self.create_delivery(
            status=EmailDelivery.Status.PROCESSING,
            processing_started_at=expired_time,
            processing_token=old_token,
            next_attempt_at=self.now + timedelta(hours=1),
            attempts=1
        )

        result = self.processor.claim_delivery()

        self.assertIsNotNone(result)

        pk, new_token = result

        self.assertEqual(pk, delivery.pk)
        self.assertIsInstance(new_token, uuid.UUID)
        self.assertNotEqual(new_token, old_token)

        delivery.refresh_from_db()

        self.assertEqual(delivery.status, EmailDelivery.Status.PROCESSING)
        self.assertEqual(delivery.attempts, 2)
        self.assertEqual(delivery.processing_token, new_token)
        self.assertGreater(delivery.processing_started_at, expired_time)

    #------------------------------------------------------------------
    # 5. Exhausted attempts cannot be claimed .
    #------------------------------------------------------------------

    def test_exhausted_attempts_cannot_be_claimed(self):
        self.create_delivery(
            status=EmailDelivery.Status.FAILED,
            attempts=3,
            max_attempts=3
        )

        result = self.processor.claim_delivery()
        self.assertIsNone(result)

    #------------------------------------------------------------------
    # 6. Failed Email due for retry can be claimed .
    #------------------------------------------------------------------
    def test_failed_email_due_for_retry_is_claimed(self):
        delivery = self.create_delivery(
            status=EmailDelivery.Status.FAILED,
            attempts=1,
            max_attempts=3
        )
        result = self.processor.claim_delivery()
        self.assertIsNotNone(result)

        pk, token = result

        self.assertEqual(pk, delivery.pk)

        delivery.refresh_from_db()

        self.assertEqual(delivery.status, EmailDelivery.Status.PROCESSING)
        self.assertEqual(delivery.attempts, 2)
        self.assertEqual(delivery.processing_token, token)

    #----------------------------------------------------------------------
    # 7. Empty queue returns None Safely .
    #----------------------------------------------------------------------

    def test_empty_queue_returns_none(self):
        result = self.processor.claim_delivery()

        self.assertIsNone(result)

#-----------------------------------------------------------------------
# CONCURRENCY TESTs
#-----------------------------------------------------------------------

class EmailDeliveryConcurrencyTests(TransactionTestCase):

    def setUp(self):
        self.provider = MagicMock(spec=EmailProvider)
        self.now = timezone.now()

    def test_two_workers_cannot_claim_same_delivery(self):
        delivery = EmailDelivery.objects.create(
            recipient_email="customer@example.com",
            subject="Concurrency test",
            body="Testing concurrency claims.",
            purpose=EmailDelivery.Purpose.NOTIFICATION,
            status=EmailDelivery.Status.PENDING,
            next_attempt_at=self.now - timedelta(minutes=1),
            attempts=0,
            max_attempts=3
        )

        results = []
        errors = []

        barrier = threading.Barrier(2)

        def worker():
            try:
                processor = EmailDeliveryProcessor(
                    provider=self.provider
                )

                barrier.wait()
                claim = processor.claim_delivery()

                results.append(claim)

            except Exception as exc :
                errors.append(exc)

            finally:
                # Close this worker's database connection.
                connections["default"].close()

        thread_one = threading.Thread(target=worker)
        thread_two = threading.Thread(target=worker)

        thread_one.start()
        thread_two.start()

        thread_one.join()
        thread_two.join()

        # No worker should have encountered an Unexpected exception.
        self.assertEqual(errors, [])

        # Both workers should have returned a result.
        self.assertEqual(len(results), 2)

        successful_claims = [
            result for result in results
            if result is not None
        ]

        unsuccessful_claim = [
            result for result in results
            if result is None
        ]
        # Exactly one worker should claim delivery.
        self.assertEqual(len(unsuccessful_claim), 1)

        delivery.refresh_from_db()

        # The delivery should only have been claimed once
        self.assertEqual(delivery.attempts, 1)
        self.assertEqual(delivery.status, EmailDelivery.Status.PROCESSING)

        # The database token should match the successful claim.
        self.assertEqual(
            delivery.processing_token,
            successful_claims[0][1]
        )























