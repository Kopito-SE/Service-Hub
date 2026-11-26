from datetime import timedelta
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.checkout.models import Checkout
from apps.checkout.services.settlement_service import SettlementService
from apps.payments.interfaces import PaymentInterfaceError


class SettlementServiceTests(TestCase):

    def setUp(self):
        self.checkout = Checkout.objects.create(
            booking_id=101,
            customer_id=25,
            amount_due=Decimal("1500.00"),
            currency="KES",
            status=Checkout.Status.PENDING,
            expires_at=timezone.now() + timedelta(minutes=15),
        )

        self.user = SimpleNamespace(pk=25)

    def make_summary(self, net_paid):
        return SimpleNamespace(
            booking_id=101,
            booking_price=Decimal("1500.00"),
            net_paid=Decimal(net_paid),
            outstanding_balance=Decimal("1500.00") - Decimal(net_paid),
        )

    # 1.
    @patch("apps.checkout.services.settlement_service.get_payment_summary")
    def test_no_payment_keeps_checkout_pending(self, mock_summary):
        mock_summary.return_value = self.make_summary("0.00")

        checkout = SettlementService.refresh_checkout_status(
            checkout_id=self.checkout.id,
            user=self.user,
        )

        self.assertEqual(checkout.status, Checkout.Status.PENDING)
        self.assertIsNone(checkout.completed_at)

    # 2.
    @patch("apps.checkout.services.settlement_service.get_payment_summary")
    def test_partial_payment_updates_checkout_status(self, mock_summary):
        mock_summary.return_value = self.make_summary("500.00")

        checkout = SettlementService.refresh_checkout_status(
            checkout_id=self.checkout.id,
            user=self.user,
        )

        self.assertEqual(
            checkout.status,
            Checkout.Status.PARTIALLY_PAID,
        )
        self.assertIsNone(checkout.completed_at)

    # 3.
    @patch("apps.checkout.services.settlement_service.confirm_booking")
    @patch("apps.checkout.services.settlement_service.get_payment_summary")
    def test_full_payment_completes_checkout(self, mock_summary, mock_confirm_booking):
        mock_summary.return_value = self.make_summary("1500.00")

        checkout = SettlementService.refresh_checkout_status(
            checkout_id=self.checkout.id,
            user=self.user,
        )

        self.assertEqual(checkout.status, Checkout.Status.COMPLETED)
        self.assertIsNotNone(checkout.completed_at)
        mock_confirm_booking.assert_called_once_with(
            booking_id=self.checkout.booking_id
        )

    # 4.
    @patch("apps.checkout.services.settlement_service.get_payment_summary")
    def test_overpayment_is_rejected(self, mock_summary):
        mock_summary.return_value = self.make_summary("1600.00")

        with self.assertRaises(ValidationError):
            SettlementService.refresh_checkout_status(
                checkout_id=self.checkout.id,
                user=self.user,
            )

        self.checkout.refresh_from_db()
        self.assertEqual(
            self.checkout.status,
            Checkout.Status.PENDING,
        )

    # 5.
    @patch("apps.checkout.services.settlement_service.get_payment_summary")
    def test_negative_net_payment_is_rejected(self, mock_summary):
        mock_summary.return_value = self.make_summary("-100.00")

        with self.assertRaises(ValidationError):
            SettlementService.refresh_checkout_status(
                checkout_id=self.checkout.id,
                user=self.user,
            )

    # 6.
    @patch("apps.checkout.services.settlement_service.get_payment_summary")
    def test_mismatched_booking_price_is_rejected(self, mock_summary):
        mock_summary.return_value = SimpleNamespace(
            booking_id=101,
            booking_price=Decimal("2000.00"),
            net_paid=Decimal("0.00"),
            outstanding_balance=Decimal("2000.00"),
        )

        with self.assertRaises(ValidationError):
            SettlementService.refresh_checkout_status(
                checkout_id=self.checkout.id,
                user=self.user,
            )

    # 7.
    @patch("apps.checkout.services.settlement_service.expire_pending_booking")
    @patch("apps.checkout.services.settlement_service.get_payment_summary")
    def test_expired_checkout_is_marked_expired(self, mock_summary, mock_expire_booking):
        self.checkout.expires_at = timezone.now() - timezone.timedelta(seconds=1)
        self.checkout.save(update_fields=["expires_at"])

        checkout = SettlementService.refresh_checkout_status(
            checkout_id=self.checkout.id,
            user=self.user,
        )

        self.assertEqual(checkout.status, Checkout.Status.EXPIRED)
        mock_expire_booking.assert_called_once_with(
            booking_id=self.checkout.booking_id
        )
        mock_summary.assert_not_called()

    # 8.
    @patch("apps.checkout.services.settlement_service.get_payment_summary")
    def test_completed_checkout_is_not_reopened(self, mock_summary):
        self.checkout.status = Checkout.Status.COMPLETED
        self.checkout.save(update_fields=["status"])

        checkout = SettlementService.refresh_checkout_status(
            checkout_id=self.checkout.id,
            user=self.user,
        )

        self.assertEqual(checkout.status, Checkout.Status.COMPLETED)
        mock_summary.assert_not_called()

    # 9.
    @patch("apps.checkout.services.settlement_service.get_payment_summary")
    def test_cancelled_checkout_is_not_reopened(self, mock_summary):
        self.checkout.status = Checkout.Status.CANCELLED
        self.checkout.save(update_fields=["status"])

        checkout = SettlementService.refresh_checkout_status(
            checkout_id=self.checkout.id,
            user=self.user,
        )

        self.assertEqual(checkout.status, Checkout.Status.CANCELLED)
        mock_summary.assert_not_called()

    # 10.
    @patch("apps.checkout.services.settlement_service.get_payment_summary")
    def test_payment_interface_error_is_converted(self, mock_summary):
        mock_summary.side_effect = PaymentInterfaceError(
            "Payment summary unavailable."
        )

        with self.assertRaises(ValidationError):
            SettlementService.refresh_checkout_status(
                checkout_id=self.checkout.id,
                user=self.user,
            )
