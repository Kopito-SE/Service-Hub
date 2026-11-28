import logging
from decimal import Decimal

from django.db import transaction
from django.db.models import Sum
from rest_framework.exceptions import ValidationError

from apps.payments.models import Payment, PaymentReversal
from .balances import get_net_paid_amount, get_outstanding_amount

from apps.bookings.interfaces import (
    BookingInterfaceError,
    get_booking_for_update,
    get_booking
)
from apps.events.interfaces import EventsInterface, PaymentFailed, PaymentSucceeded

logger = logging.getLogger(__name__)


class PaymentService:

    # Kept as a static method so existing callers
    # (e.g. MpesaPaymentService) don't need to change.
    @staticmethod
    def _get_net_paid_amount(*, booking):
        return get_net_paid_amount(booking=booking)

    @staticmethod
    def _get_locked_booking(booking_id):
        try:
            return get_booking_for_update(booking_id=booking_id)

        except BookingInterfaceError:
            raise ValidationError({
                "booking": "The selected booking does not exist."
            })

    @staticmethod
    def _check_business_owner(*, booking, user):
        if booking.business_owner_id != user.pk:
            raise ValidationError({
                "booking": (
                    "You are not authorized to manage payments for this booking"
                )
            })

    @staticmethod
    @transaction.atomic
    def create_payment(
        *,
        booking_id,
        amount,
        method,
        recorded_by,
        transaction_reference="",
        currency="KES",
        allow_customer=False,
    ):
        booking = PaymentService._get_locked_booking(booking_id)
        if not (allow_customer and booking.customer_id == recorded_by.pk):
            PaymentService._check_business_owner(
                booking=booking,
                user=recorded_by,
            )

        if booking.status in {"cancelled", "completed"}:
            raise ValidationError({
                "booking": (
                    "Payments cannot be added to a cancelled "
                    "or completed booking"
                )
            })

        amount = Decimal(str(amount))
        if amount <= 0:
            raise ValidationError({
                "amount": "Payment amount must be greater than zero."
            })

        outstanding = get_outstanding_amount(booking=booking)
        if amount > outstanding:
            raise ValidationError({
                "amount": (
                    f"Payment exceeds the outstanding balance "
                    f"of {outstanding}."
                )
            })

        return Payment.objects.create(
            booking_id=booking.id,
            amount=amount,
            method=method,
            status=Payment.Status.PENDING,
            recorded_by=recorded_by,
            transaction_reference=transaction_reference,
            currency=currency,
        )

    @staticmethod
    @transaction.atomic
    def change_payment_status(*, payment_id, new_status, user):
        allowed_statuses = {Payment.Status.SUCCEEDED, Payment.Status.FAILED}
        if new_status not in allowed_statuses:
            raise ValidationError({"status": "Chose succeeded or failed"})

        try:
            initial_payment = Payment.objects.get(pk=payment_id)
        except Payment.DoesNotExist:
            raise ValidationError({"payment": "The selected Payment does not exist"})

        booking = PaymentService._get_locked_booking(initial_payment.booking_id)
        PaymentService._check_business_owner(booking=booking, user=user)

        payment = Payment.objects.select_for_update().get(pk=payment_id)

        if payment.status == new_status:
            return payment

        if payment.status != Payment.Status.PENDING:
            raise ValidationError({
                "status": "Only pending payments can transition to succeeded or failed."
            })

        if new_status == Payment.Status.SUCCEEDED:
            outstanding = get_outstanding_amount(booking=booking)
            if payment.amount > outstanding:
                raise ValidationError({
                    "amount": (
                        "This payment would exceed the remaining booking "
                        f"balance of {outstanding}."
                    )
                })

        if (
            payment.method == Payment.Method.MPESA
            and new_status == Payment.Status.SUCCEEDED
        ):
            raise ValidationError({
                "status": (
                    "M-Pesa success must be confirmed by a verified Daraja "
                    "callback, not manually."
                )
            })

        payment.status = new_status
        payment.save(update_fields=["status", "updated_at"])

        if new_status == Payment.Status.SUCCEEDED:
            event = PaymentSucceeded(
                payment_id=payment.pk,
                booking_id=booking.id,
                customer_id=booking.customer_id,
                guest_customer_id=booking.guest_customer_id,
                amount=payment.amount,
            )

        else:
            event = PaymentFailed(
                payment_id=payment.pk,
                booking_id=booking.id,
                customer_id=booking.customer_id,
                guest_customer_id=booking.guest_customer_id,
                amount=payment.amount,
            )

        EventsInterface.publish(event)

        return payment

    @staticmethod
    @transaction.atomic
    def reverse_payment(*, payment_id, amount, reason, recorded_by):
        try:
            initial_payment = Payment.objects.get(pk=payment_id)
        except Payment.DoesNotExist:
            raise ValidationError({
                "payment": "The selected payment does not exist"
            })

        booking = PaymentService._get_locked_booking(initial_payment.booking_id)
        PaymentService._check_business_owner(booking=booking, user=recorded_by)

        payment = Payment.objects.select_for_update().get(pk=payment_id)
        if payment.status != Payment.Status.SUCCEEDED:
            raise ValidationError({
                "payment": "Only successful payments can be reversed"
            })

        amount = Decimal(str(amount))
        if amount <= 0:
            raise ValidationError({
                "amount": "Reversal amount must be greater than zero"
            })

        already_reversed = (
            PaymentReversal.objects.filter(payment=payment)
            .aggregate(total=Sum("amount"))["total"]
            or Decimal("0.00")
        )
        remaining_reversible = payment.amount - already_reversed
        if amount > remaining_reversible:
            raise ValidationError({
                "amount": (
                    "Reversal exceeds the amount still available "
                    f"to reverse: {remaining_reversible}."
                )
            })

        return PaymentReversal.objects.create(
            payment=payment,
            amount=amount,
            reason=reason,
            recorded_by=recorded_by,
        )

    @staticmethod
    def get_booking_payment_summary(*, booking, user):
        try:
            booking = get_booking(booking_id=booking.id)

        except BookingInterfaceError:
            raise ValidationError({
                "booking": "The selected booking does not exist."
            })

        if booking.customer_id != user.pk:
            PaymentService._check_business_owner(booking=booking, user=user)

        net_paid = get_net_paid_amount(booking=booking)
        outstanding = booking.price_at_booking - net_paid

        return {
            "booking_id": booking.id,
            "booking_price": booking.price_at_booking,
            "net_paid": net_paid,
            "outstanding_balance": max(outstanding, Decimal("0.00")),
        }
