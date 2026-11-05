import time
import uuid
from django.test import TransactionTestCase
from django.utils import timezone

from apps.events.models import EventDelivery, EventOutbox
from apps.events.processor import (
     renew_delivery_lease,
     _execute_handler_with_heartbeat
)

class DeliveryLeaseTests(TransactionTestCase):

    def setUp(self):
        self.event = EventOutbox.objects.create(
            event_type="apps.events.events.BookingCreated",
            payload={
                "booking_id": 1,
                "customer_id": 1,
                "service_name": "Nail Polishing"
            },
        )

        self.claim_token = uuid.uuid4()

        self.delivery = EventDelivery.objects.create(
            event=self.event,
            handler_key="test.lease_handler",
            status=EventDelivery.Status.PROCESSING,
            attempts=1,
            max_attempts=5,
            processing_started_at=timezone.now(),
            processing_token=self.claim_token
        )

    def test_valid_worker_can_renew_lease(self):
        old_timestamp = self.delivery.processing_started_at

        renewed = renew_delivery_lease(
            self.delivery.pk,
            self.claim_token
        )

        self.delivery.refresh_from_db()

        self.assertTrue(renewed)
        self.assertGreater(
            self.delivery.processing_started_at,
            old_timestamp
        )

    def test_old_token_cannot_renew_reclaimed_delivery(self):
        new_token = uuid.uuid4()

        EventDelivery.objects.filter(
            pk=self.delivery.pk
        ).update(processing_token=new_token)

        renewed = renew_delivery_lease(
            self.delivery.pk,
            self.claim_token
        )

        self.assertFalse(renewed)

    def test_non_processing_delivery_cannot_renew_lease(self):
        self.delivery.status = EventDelivery.Status.SUCCEEDED
        self.delivery.save(update_fields=["status"])

        renewed = renew_delivery_lease(
            self.delivery.pk,
            self.claim_token
        )

        self.assertFalse(renewed)

    def test_heartbeat_renews_lease_during_long_handler(self):
        old_timestamp = self.delivery.processing_started_at

        def slow_handler(event, *, delivery_id):
            time.sleep(0.2)

        from unittest.mock import patch

        with patch(
            "apps.events.processor.LEASE_RENEWAL_INTERVAL",
            0.05,
        ):
            _execute_handler_with_heartbeat(
                handler=slow_handler,
                event=None,
                delivery_id=self.delivery.pk,
                claim_token=self.claim_token
            )
        self.delivery.refresh_from_db()
        self.assertGreater(
            self.delivery.processing_started_at,
            old_timestamp
        )