from datetime import timedelta
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.checkout.models import Checkout
from apps.checkout.services.checkout_service import CheckoutService
from apps.bookings.interfaces import BookingInterfaceError


class CheckoutServiceTests(TestCase):

    def setUp(self):
        self.booking = SimpleNamespace(
            id=101,
            customer_id=25,
            guest_customer_id=None,
            status="pending",
            price_at_booking=Decimal("1500.00"),
        )

    # 1.
    @patch("apps.checkout.services.checkout_service.get_booking")
    def test_create_checkout_successfully(self, mock_get_booking):
        mock_get_booking.return_value = self.booking

        before_creation = timezone.now()

        result = CheckoutService.create_checkout(booking_id=self.booking.id)
        checkout = result.checkout

        after_creation = timezone.now()

        self.assertIsNone(result.guest_access_token)
        self.assertEqual(checkout.booking_id, self.booking.id)
        self.assertEqual(checkout.customer_id, self.booking.customer_id)
        self.assertEqual(checkout.amount_due, Decimal("1500.00"))
        self.assertEqual(checkout.currency, "KES")
        self.assertEqual(checkout.status, Checkout.Status.PENDING)

        self.assertGreaterEqual(
            checkout.expires_at,
            before_creation + timedelta(minutes=15),
        )
        self.assertLessEqual(
            checkout.expires_at,
            after_creation + timedelta(minutes=15),
        )

    # 2.
    @patch("apps.checkout.services.checkout_service.get_booking")
    def test_nonexistent_booking_is_rejected(self, mock_get_booking):
        mock_get_booking.side_effect = BookingInterfaceError(
            "Booking does not exist."
        )

        with self.assertRaises(ValidationError):
            CheckoutService.create_checkout(booking_id=999)

    # 3.
    @patch("apps.checkout.services.checkout_service.get_booking")
    def test_non_pending_booking_is_rejected(self, mock_get_booking):
        self.booking.status = "confirmed"
        mock_get_booking.return_value = self.booking

        with self.assertRaises(ValidationError):
            CheckoutService.create_checkout(
                booking_id=self.booking.id
            )

        self.assertEqual(Checkout.objects.count(), 0)

    # 4.
    @patch("apps.checkout.services.checkout_service.get_booking")
    def test_zero_booking_amount_is_rejected(self, mock_get_booking):
        self.booking.price_at_booking = Decimal("0.00")
        mock_get_booking.return_value = self.booking

        with self.assertRaises(ValidationError):
            CheckoutService.create_checkout(
                booking_id=self.booking.id
            )

        self.assertEqual(Checkout.objects.count(), 0)

    # 5.
    @patch("apps.checkout.services.checkout_service.get_booking")
    def test_duplicate_checkout_is_rejected(self, mock_get_booking):
        mock_get_booking.return_value = self.booking

        first_result = CheckoutService.create_checkout(
            booking_id=self.booking.id
        )

        with self.assertRaises(ValidationError):
            CheckoutService.create_checkout(
                booking_id=self.booking.id
            )

        self.assertEqual(Checkout.objects.count(), 1)
        self.assertEqual(
            Checkout.objects.first().id,
            first_result.checkout.id,
        )
