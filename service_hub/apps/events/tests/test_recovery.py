from datetime import timedelta
import uuid
from django.test import TestCase
from django.utils import timezone

from apps.events.models import EventDelivery, EventOutbox
from apps.events.processor import recover_exhausted_deliveries

class ExhaustedDeliveryTests(TestCase):

    def test_expired_delivery_at_max_attempts_becomes_dead(self):
        event = EventOutbox.objects.create(
            event_type="apps.events.events.BookingCreated",
            payload={
                "booking_id": 10,
                "customer_id": 5,
                "service_name": "Haircut"
            },
            status=EventOutbox.Status.PROCESSING,
        )

        delivery = EventDelivery.objects.create(
            event=event,
            handler_key="test.exhausted__handler",
            status=EventDelivery.Status.PROCESSING,
            attempts=5,
            max_attempts=5,
            processing_started_at=(
                timezone.now() - timedelta(minutes=10)
            ),
            processing_token=uuid.uuid4()
        )
        recovered = recover_exhausted_deliveries()

        delivery.refresh_from_db()
        event.refresh_from_db()

        self.assertEqual(recovered, 1)

        self.assertEqual(delivery.status, EventDelivery.Status.DEAD)

        self.assertIsNone(delivery.processing_started_at)
        self.assertIsNone(delivery.processing_token)

        self.assertEqual(event.status, EventOutbox.Status.DEAD)
