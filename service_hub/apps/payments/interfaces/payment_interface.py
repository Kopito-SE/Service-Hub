from dataclasses import dataclass
from decimal import Decimal

from rest_framework.exceptions import ValidationError

from apps.bookings.interfaces import (
    BookingInterfaceError,
    get_booking
)

from apps.payments.models import Payment
from apps.payments.services.payment_service import PaymentService
from apps.payments.services.mpesa_service import MpesaPaymentService

class PaymentInterfaceError(Exception):
    """Raised when a payment operation fails through the public interface."""

@dataclass(frozen=True)
class PaymentDTO:
    id: int
    booking_id: int
    amount: Decimal
    status: str
    method: str

@dataclass(frozen=True)
class PaymentSummaryDTO:
    booking_id: int
    booking_price: Decimal
    net_paid: Decimal
    outstanding_balance: Decimal

def _to_payment_dto(payment):
    return PaymentDTO(
        id=payment.pk,
        booking_id=payment.booking_id,
        amount=payment.amount,
        status=payment.status,
        method=payment.method
    )

def initiate_payment(
        *,
        booking_id,
        amount,
        method,
        recorded_by
):
    """
    Create a not-M-Pesa payment attempt
    """
    try:
        payment = PaymentService.create_payment(
            booking_id=booking_id,
            amount=amount,
            method=method,
            recorded_by=recorded_by,
            allow_customer=True
        )
    except ValidationError as exc:
        raise PaymentInterfaceError(str(exc)) from exc

    return _to_payment_dto(payment)

def initiate_mpesa_payment(
        *,
        booking_id,
        amount,
        phone_number,
        recorded_by
):
    """
    Initiate an M-Pesa STK Push Payment attempt.
    """
    try:
        payment = MpesaPaymentService.initiate_payment(
            booking_id=booking_id,
            amount=amount,
            phone_number=phone_number,
            recorded_by=recorded_by
        )
    except ValidationError as exc:
        raise PaymentInterfaceError(str(exc)) from exc

    return _to_payment_dto(payment)

def get_payment(*, payment_id):
    """
    Retrieve a payment as a DTO
    """
    try:
        payment = Payment.objects.get(pk=payment_id)

    except Payment.DoesNotExist as exc:
        raise PaymentInterfaceError(
            f"Payment #{payment_id} does not exist."
        ) from exc

    return _to_payment_dto(payment)

def get_payment_summary(*, booking_id, user):
    """
    Retrieve the payment summary for a booking
    Authorization is performed by the existing PaymentService.
    """
    try:
        booking = get_booking(booking_id=booking_id)

        summary = PaymentService.get_booking_payment_summary(
            booking=booking,
            user=user
        )

    except (BookingInterfaceError, ValidationError) as exc:
        raise PaymentInterfaceError(str(exc)) from exc

    return PaymentSummaryDTO(
        booking_id=summary["booking_id"],
        booking_price=summary["booking_price"],
        net_paid=summary["net_paid"],
        outstanding_balance=summary["outstanding_balance"]
    )