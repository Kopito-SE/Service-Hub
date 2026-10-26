from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.businesses.models import Business
from apps.bookings.models import Booking
from apps.service_catalog.models import Service

from ..models import Payment, PaymentReversal
from ..services import PaymentService


User = get_user_model()


class PaymentServiceTests(TestCase):

    def setUp(self):
        self.owner = User.objects.create_user(
            username="business_owner",
            password="test-password-123",
        )
        self.other_user = User.objects.create_user(
            username="other_owner",
            password="test-password-123",
        )
        self.customer = User.objects.create_user(
            username="booking_customer",
            password="test-password-123",
        )

        self.business = Business.objects.create(
            owner=self.owner,
            name="Service Hub Test Business",
        )

        self.service = Service.objects.create(
            business=self.business,
            name="Consultation",
            price=Decimal("1000.00"),
            duration_minutes=60,
        )

        start_time = timezone.now() + timedelta(days=7)

        self.booking = Booking.objects.create(
            customer=self.customer,
            business=self.business,
            service=self.service,
            start_time=start_time,
            end_time=start_time + timedelta(hours=1),
            price_at_booking=Decimal("1000.00"),
            status=Booking.Status.PENDING,
        )

    def create_payment(
        self,
        *,
        amount="500.00",
        method=Payment.Method.CASH,
        reference="",
    ):
        return PaymentService.create_payment(
            booking_id=self.booking.pk,
            amount=Decimal(amount),
            method=method,
            recorded_by=self.owner,
            transaction_reference=reference,
        )

    def test_owner_can_create_pending_payment(self):
        payment = self.create_payment()

        self.assertEqual(payment.status, Payment.Status.PENDING)
        self.assertEqual(payment.amount, Decimal("500.00"))
        self.assertEqual(payment.booking, self.booking)

    def test_payment_cannot_exceed_outstanding_balance(self):
        with self.assertRaises(ValidationError):
            self.create_payment(amount="1000.01")

        self.assertEqual(Payment.objects.count(), 0)

    def test_other_business_owner_cannot_create_payment(self):
        with self.assertRaises(ValidationError):
            PaymentService.create_payment(
                booking_id=self.booking.pk,
                amount=Decimal("100.00"),
                method=Payment.Method.CASH,
                recorded_by=self.other_user,
            )

        self.assertEqual(Payment.objects.count(), 0)
     #
    def test_pending_cash_payment_can_be_marked_succeeded(self):
        payment = self.create_payment()

        updated = PaymentService.change_payment_status(
            payment_id=payment.pk,
            new_status=Payment.Status.SUCCEEDED,
            user=self.owner,
        )

        self.assertEqual(updated.status, Payment.Status.SUCCEEDED)

    def test_pending_payment_can_be_marked_failed(self):
        payment = self.create_payment()

        updated = PaymentService.change_payment_status(
            payment_id=payment.pk,
            new_status=Payment.Status.FAILED,
            user=self.owner,
        )

        self.assertEqual(updated.status, Payment.Status.FAILED)

    def test_failed_payment_cannot_later_be_marked_succeeded(self):
        payment = self.create_payment()

        PaymentService.change_payment_status(
            payment_id=payment.pk,
            new_status=Payment.Status.FAILED,
            user=self.owner,
        )

        with self.assertRaises(ValidationError):
            PaymentService.change_payment_status(
                payment_id=payment.pk,
                new_status=Payment.Status.SUCCEEDED,
                user=self.owner,
            )

    def test_successful_payment_reduces_outstanding_balance(self):
        payment = self.create_payment(amount="300.00")

        PaymentService.change_payment_status(
            payment_id=payment.pk,
            new_status=Payment.Status.SUCCEEDED,
            user=self.owner,
        )

        summary = PaymentService.get_booking_payment_summary(
            booking=self.booking,
            user=self.owner,
        )

        self.assertEqual(summary["net_paid"], Decimal("300.00"))
        self.assertEqual(
            summary["outstanding_balance"],
            Decimal("700.00"),
        )

    def test_m_pesa_payment_cannot_be_manually_marked_succeeded(self):
        payment = self.create_payment(method=Payment.Method.MPESA)

        with self.assertRaises(ValidationError):
            PaymentService.change_payment_status(
                payment_id=payment.pk,
                new_status=Payment.Status.SUCCEEDED,
                user=self.owner,
            )

    def test_owner_can_reverse_successful_payment(self):
        payment = self.create_payment(amount="500.00")

        PaymentService.change_payment_status(
            payment_id=payment.pk,
            new_status=Payment.Status.SUCCEEDED,
            user=self.owner,
        )

        reversal = PaymentService.reverse_payment(
            payment_id=payment.pk,
            amount=Decimal("200.00"),
            reason="Partial refund",
            recorded_by=self.owner,
        )

        self.assertEqual(reversal.amount, Decimal("200.00"))
        self.assertEqual(
            PaymentReversal.objects.filter(payment=payment).count(),
            1,
        )

        summary = PaymentService.get_booking_payment_summary(
            booking=self.booking,
            user=self.owner,
        )

        self.assertEqual(summary["net_paid"], Decimal("300.00"))
        self.assertEqual(
            summary["outstanding_balance"],
            Decimal("700.00"),
        )

    def test_reversal_cannot_exceed_remaining_payment_amount(self):
        payment = self.create_payment(amount="500.00")

        PaymentService.change_payment_status(
            payment_id=payment.pk,
            new_status=Payment.Status.SUCCEEDED,
            user=self.owner,
        )

        PaymentService.reverse_payment(
            payment_id=payment.pk,
            amount=Decimal("300.00"),
            reason="Partial refund",
            recorded_by=self.owner,
        )

        with self.assertRaises(ValidationError):
            PaymentService.reverse_payment(
                payment_id=payment.pk,
                amount=Decimal("200.01"),
                reason="Excess refund",
                recorded_by=self.owner,
            )

        self.assertEqual(
            PaymentReversal.objects.filter(payment=payment).count(),
            1,
        )
