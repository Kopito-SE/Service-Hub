from decimal import Decimal

from django.db import transaction
from django.db.models import Sum
from rest_framework.exceptions import ValidationError

from apps.bookings.models import Booking
from .models import Payment, PaymentReversal


class PaymentService:

    @staticmethod
    def _get_locked_booking(booking_id):
        try:
            return (
                Booking.objects.select_for_update()
                .select_related("business")
                .get(pk=booking_id)
            )
        except Booking.DoesNotExist:
            raise ValidationError({
                "booking": "The selected booking does not exist."
            })

    @staticmethod
    def _check_business_owner(*, booking, user):
        if booking.business.owner_id != user.pk:
            raise ValidationError({
                "booking": (
                    "You are not authorized to manage payments for this booking"
                )
            })
    @staticmethod
    def _get_net_paid_amount(*, booking):
        successful_payments = Payment.objects.filter(
            booking=booking,
            status=Payment.Status.SUCCEEDED
        )

        total_successful = (
            successful_payments.aggregate(total=Sum("amount"))["total"]
            or Decimal("0.00")
        )
        total_reversed = (
            PaymentReversal.objects.filter(
                payment__booking=booking,
                payment__status=Payment.Status.SUCCEEDED
            ).aggregate(total=Sum("amount"))["total"]
            or Decimal("0.00")
        )
        return total_successful - total_reversed

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
    ):
        booking = PaymentService._get_locked_booking(booking_id)
        PaymentService._check_business_owner(
            booking=booking,
            user=recorded_by
        )

        if booking.status in [
            Booking.Status.CANCELLED,
            Booking.Status.COMPLETED
        ]:
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

        net_paid = PaymentService._get_net_paid_amount(booking=booking)
        outstanding = booking.price_at_booking - net_paid

        if amount > outstanding:
            raise ValidationError({
                "amount":(
                    f"Payment exceeds the outstanding balance "
                    f"of {outstanding}."
                )
            })

        return Payment.objects.create(
            booking=booking,
            amount=amount,
            method=method,
            status=Payment.Status.PENDING,
            recorded_by=recorded_by,
            transaction_reference=transaction_reference,
            currency=currency
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
            net_paid = PaymentService._get_net_paid_amount(booking=booking)

            outstanding = booking.price_at_booking - net_paid
            
            if payment.amount > outstanding:
                raise ValidationError({
                    "amount": f"This payment would exceed the remaining booking balance of {outstanding}."
                })


        if payment.method == Payment.Method.MPESA and new_status == Payment.Status.SUCCEEDED:
            raise ValidationError({
                "status": "M-Pesa success must be confirmed by a verified Daraja callback, not manually."
            })


        payment.status = new_status
        payment.save(update_fields=["status", "updated_at"])
        return payment

    @staticmethod
    @transaction.atomic
    def reverse_payment(
            *,
            payment_id,
            amount,
            reason,
            recorded_by
    ):
        try:
            initial_payment = Payment.objects.get(pk=payment_id)

        except Payment.DoesNotExist:
            raise ValidationError({
                "payment":" The selected payment does not exist"
            })

        booking = PaymentService._get_locked_booking(
            initial_payment.booking_id
        )
        PaymentService._check_business_owner(
            booking=booking,
            user=recorded_by,
        )

        payment = Payment.objects.select_for_update().get(
            pk=payment_id
        )
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
            recorded_by=recorded_by
        )

    @staticmethod
    def get_booking_payment_summary(*, booking, user):
        PaymentService._check_business_owner(
            booking=booking,
            user=user
        )

        net_paid = PaymentService._get_net_paid_amount(
            booking=booking
        )
        outstanding = booking.price_at_booking - net_paid

        return {
            "booking_id": booking.pk,
            "booking_price": booking.price_at_booking,
            "net_paid": net_paid,
            "outstanding_balance": max(
                outstanding,
                Decimal("0.00"),
            ),
        }


















