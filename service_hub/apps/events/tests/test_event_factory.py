from decimal import Decimal
from django.test import SimpleTestCase

from apps.events.event_factory import reconstruct_event
from apps.events.events import (
   BookingCreated,
   PaymentSucceeded
)

class EventFactoryTest(SimpleTestCase):
    def test_reconstruct_booking_created(self):
        payload = {
            "booking_id": 10,
            "customer_id": 5,
            "service_name": "Haircut"
        }
        event = reconstruct_event(
            "apps.events.events.BookingCreated",
            payload
        )

        self.assertEqual(
            event,
            BookingCreated(
                booking_id=10,
                customer_id=5,
                service_name="Haircut"
            ),
        )

    def test_reconstruct_payment_converts_amount_to_decimal(self):
        payload = {
            "payment_id": 1,
            "booking_id": 10,
            "customer_id": 5,
            "amount": "1500.50"
        }

        event = reconstruct_event(
            "apps.events.events.PaymentSucceeded",
            payload
        )

        self.assertIsInstance(event.amount, Decimal)
        self.assertEqual(event.amount, Decimal("1500.50"))

    def test_unknown_event_type_is_rejected(self):
        with self.assertRaises(ValueError):
            reconstruct_event(
                "unknown.event.Type",
                {}
            )