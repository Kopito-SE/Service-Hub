from decimal import Decimal

from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.checkout.models import Checkout
from apps.payments.interfaces import (
    PaymentInterfaceError,
    get_payment_summary,
)


class SettlementService:

    @staticmethod
    @transaction.atomic
    def refresh_checkout_status(*, checkout_id, user):
        """
        Recalculate Checkout settlement using Payments as the
        source of truth for successful payments and reversals.
        """

        try:
            checkout = (
                Checkout.objects
                .select_for_update()
                .get(pk=checkout_id)
            )
        except Checkout.DoesNotExist as exc:
            raise ValidationError(
                "Checkout session could not be found."
            ) from exc

        # Terminal states cannot be reused.
        if checkout.status in {
            Checkout.Status.FAILED,
            Checkout.Status.EXPIRED,
            Checkout.Status.CANCELLED,
        }:
            return checkout

        # A completed Checkout stays completed.
        # Any later reversal requires a separate reconciliation/
        # refund workflow rather than reopening Checkout.
        if checkout.status == Checkout.Status.COMPLETED:
            return checkout

        # Expire the Checkout when its fixed deadline has passed.
        if timezone.now() >= checkout.expires_at:
            checkout.status = Checkout.Status.EXPIRED
            checkout.save(update_fields=["status", "updated_at"])
            return checkout

        try:
            summary = get_payment_summary(
                booking_id=checkout.booking_id,
                user=user,
            )
        except PaymentInterfaceError as exc:
            raise ValidationError(
                "Unable to retrieve the booking payment summary."
            ) from exc

        # Checkout's amount_due is the amount snapshot taken
        # when the Checkout session was created.
        if summary.booking_price != checkout.amount_due:
            raise ValidationError(
                "Checkout amount does not match the booking price. "
                "Manual reconciliation is required."
            )

        net_paid = summary.net_paid

        if net_paid < Decimal("0.00"):
            raise ValidationError(
                "Net paid amount cannot be negative."
            )

        if net_paid > checkout.amount_due:
            raise ValidationError(
                "The booking has been overpaid. "
                "Manual reconciliation is required."
            )

        outstanding = checkout.amount_due - net_paid

        if outstanding == Decimal("0.00"):
            checkout.status = Checkout.Status.COMPLETED
            checkout.completed_at = timezone.now()

        elif net_paid > Decimal("0.00"):
            checkout.status = Checkout.Status.PARTIALLY_PAID

        else:
            checkout.status = Checkout.Status.PENDING

        checkout.save(
            update_fields=[
                "status",
                "completed_at",
                "updated_at",
            ]
        )

        return checkout
