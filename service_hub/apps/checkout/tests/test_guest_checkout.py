import hashlib
from datetime import timedelta
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.checkout.models import Checkout
from apps.checkout.services.checkout_service import CheckoutService

class GuestCheckoutCreationTests(TestCase):
    """Create-checkout paths specific to guest bookings."""
    def setUp(self):
        self.booking = SimpleNamespace(
            id=100,
            customer_id=None,
            guest_customer_id=77,
            status="pending",
            price_at_booking=Decimal("1500.00")
        )
    # 1.
    @patch("apps.checkout.services.checkout_service.get_booking")
    def test_guest_checkout_returns_token_and_stores_hash(self, mock_get_booking):
        mock_get_booking.return_value = self.booking

        result = CheckoutService.create_checkout(booking_id=self.booking.id)
        checkout = result.checkout

        self.assertIsInstance(result.guest_access_token, str)
        self.assertTrue(result.guest_access_token)

        self.assertIsNone(checkout.customer_id)
        self.assertEqual(checkout.guest_customer_id, 77)

        self.assertIsNotNone(checkout.guest_access_token_hash)
        self.assertNotEqual(
            checkout.guest_access_token_hash,
            result.guest_access_token
        )
        self.assertEqual(
            checkout.guest_access_token_hash,
            hashlib.sha256(result.guest_access_token.encode()).hexdigest()
        )
    # 2.
    @patch("apps.checkout.services.checkout_service.get_booking")
    def test_both_identities_is_rejected(self, mock_get_booking):
        self.booking.customer_id = 25
        mock_get_booking.return_value = self.booking

        with self.assertRaises(ValidationError):
            CheckoutService.create_checkout(booking_id=self.booking.id)

        self.assertEqual(Checkout.objects.count(), 0)

    # 3.
    @patch("apps.checkout.services.checkout_service.get_booking")
    def test_no_identity_is_rejected(self, mock_get_booking):
        self.booking.guest_customer_id = None
        mock_get_booking.return_value = self.booking

        with self.assertRaises(ValidationError):
            CheckoutService.create_checkout(booking_id=self.booking.id)

        self.assertEqual(Checkout.objects.count(), 0)

    # 4.
    @patch("apps.checkout.services.checkout_service.get_booking")
    def test_negative_amount_is_rejected(self, mock_get_booking):
        self.booking.price_at_booking = Decimal("-10.00")
        mock_get_booking.return_value = self.booking

        with self.assertRaises(ValidationError):
            CheckoutService.create_checkout(booking_id=self.booking.id)

        self.assertEqual(Checkout.objects.count(), 0)

class VerifyGuestAccessTests(TestCase):
    """verify_guest_access() branches."""
    RAW_TOKEN = "test-token-abc"

    def setUp(self):
        self.checkout = Checkout.objects.create(
            booking_id=201,
            customer_id=None,
            guest_customer_id=88,
            guest_access_token_hash=hashlib.sha256(
                self.RAW_TOKEN.encode()
            ).hexdigest(),
            amount_due=Decimal("500.00"),
            currency="KES",
            status=Checkout.Status.PENDING,
            expires_at=timezone.now() + timedelta(minutes=15)
        )

    # 1. Valid Tokens Return Checkout
    def test_valid_token_returns_checkout(self):
        result = CheckoutService.verify_guest_access(
            checkout_id=self.checkout.id,
            access_token=self.RAW_TOKEN
        )
        self.assertEqual(result.id, self.checkout.id)

    # 2. Wrong Token is Rejected
    def test_wrong_token_is_rejected(self):
        with self.assertRaises(ValidationError):
            CheckoutService.verify_guest_access(
                checkout_id=self.checkout.id,
                access_token="wrong-token"
            )

    # 3. Missing or Invalid Token is Rejected
    def test_missing_or_invalid_token_is_rejected(self):
        for bad in (None, "", 123, b"bytes"):
            with self.subTest(access_token=bad):
                with self.assertRaises(ValidationError):
                    CheckoutService.verify_guest_access(
                        checkout_id=self.checkout.id,
                        access_token=bad
                    )

    # 4. Unknown Checkout is Rejected
    def test_unknown_checkout_is_rejected(self):
        with self.assertRaises(ValidationError):
            CheckoutService.verify_guest_access(
                checkout_id=99999,
                access_token=self.RAW_TOKEN
            )

    # 5.
    def test_registered_customer_checkout_is_rejected(self):
        # Same row, but now a registered customer with no guest hash
        self.checkout.customer_id = 25
        self.checkout.guest_customer_id = None
        self.checkout.guest_access_token_hash = None
        self.checkout.save()

        with self.assertRaises(ValidationError):
            CheckoutService.verify_guest_access(
                checkout_id=self.checkout.id,
                access_token=self.RAW_TOKEN
            )