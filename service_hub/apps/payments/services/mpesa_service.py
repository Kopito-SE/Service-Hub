import logging
from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from apps.bookings.interfaces import (
    BookingInterfaceError,
    get_booking_for_update
)
from apps.events.interfaces import(
    EventsInterface,
    PaymentFailed,
    PaymentSucceeded
)
from ..models import Payment
from ..providers.mpesa import MpesaClient, MpesaError
from .balances import get_outstanding_amount
from .payment_service import PaymentService

logger = logging.getLogger(__name__)


class MpesaPaymentService:

    @staticmethod
    def initiate_payment(*, booking_id, amount, phone_number, recorded_by):
        payment = PaymentService.create_payment(
            booking_id=booking_id,
            amount=amount,
            method=Payment.Method.MPESA,
            recorded_by=recorded_by,
            allow_customer=True,
        )

        payment.phone_number = phone_number
        payment.save(update_fields=["phone_number", "updated_at"])

        try:
            result = MpesaClient.initiate_stk_push(
                phone_number=phone_number,
                amount=payment.amount,
                account_reference=f"SH{payment.pk}",
                transaction_desc="Service Hub booking",
            )
        except MpesaError as exc:
            payment.provider_result_description = str(exc)[:255]
            payment.save(update_fields=[
                "provider_result_description",
                "updated_at",
            ])
            raise

        payment.checkout_request_id = result["CheckoutRequestID"]
        payment.merchant_request_id = result.get("MerchantRequestID", "")
        payment.provider_result_code = result.get("ResponseCode", "")
        payment.provider_result_description = result.get(
            "ResponseDescription", ""
        )[:255]
        payment.save(update_fields=[
            "checkout_request_id",
            "merchant_request_id",
            "provider_result_code",
            "provider_result_description",
            "updated_at",
        ])
        return payment

    @staticmethod
    def process_callback(callback_data):
        stk_callback = callback_data.get("Body", {}).get("stkCallback", {})
        checkout_id = stk_callback.get("CheckoutRequestID")
        merchant_id = stk_callback.get("MerchantRequestID")
        result_code = stk_callback.get("ResultCode")
        result_description = str(stk_callback.get("ResultDesc", ""))[:255]

        if not checkout_id or result_code is None:
            logger.warning("Received an incomplete M-Pesa callback.")
            return False

        initial_payment = (
            Payment.objects.filter(
                checkout_request_id=checkout_id,
                method=Payment.Method.MPESA,
            )
            .only("pk", "booking_id")
            .first()
        )
        if initial_payment is None:
            logger.warning(
                "M-Pesa callback has an unknown checkout request ID."
            )
            return False

        with transaction.atomic():
            try:
                booking = get_booking_for_update(
                    booking_id=initial_payment.booking_id
                )
            except BookingInterfaceError:
                logger.error(
                    "Booking %s not found during M-Pesa callback",
                    initial_payment.booking_id,
                )
                return False

            payment = Payment.objects.select_for_update().get(
                pk=initial_payment.pk
            )

            if payment.status != Payment.Status.PENDING:
                return True

            if (
                payment.merchant_request_id
                and merchant_id
                and payment.merchant_request_id != merchant_id
            ):
                logger.warning(
                    "M-Pesa callback merchant ID mismatch for payment %s.",
                    payment.pk,
                )
                return False

            payment.callback_received_at = timezone.now()
            payment.provider_result_code = str(result_code)[:20]
            payment.provider_result_description = result_description

            if str(result_code) != "0":
                payment.status = Payment.Status.FAILED
                payment.save(update_fields=[
                    "status",
                    "callback_received_at",
                    "provider_result_code",
                    "provider_result_description",
                    "updated_at",
                ])
                EventsInterface.publish(PaymentFailed(
                    payment_id=payment.pk,
                    booking_id=booking.id,
                    customer_id=booking.customer_id,
                    guest_customer_id=booking.guest_customer_id,
                    amount=payment.amount,
                ))
                return True

            metadata = stk_callback.get("CallbackMetadata", {}).get("Item", [])
            items = {
                item.get("Name"): item.get("Value")
                for item in metadata
                if isinstance(item, dict) and item.get("Name")
            }
            amount = items.get("Amount")
            receipt = items.get("MpesaReceiptNumber")
            callback_phone = items.get("PhoneNumber")

            if amount is None or not receipt or callback_phone is None:
                payment.provider_result_description = (
                    "Successful callback missing required payment metadata; "
                    "manual reconciliation required."
                )
                payment.save(update_fields=[
                    "callback_received_at",
                    "provider_result_code",
                    "provider_result_description",
                    "updated_at",
                ])
                return False

            try:
                callback_amount = Decimal(str(amount))
                expected_amount = Decimal(payment.amount)
            except Exception:
                return False

            if callback_amount != expected_amount:
                payment.provider_result_description = (
                    "Callback amount mismatch; manual reconciliation required."
                )
                payment.save(update_fields=[
                    "callback_received_at",
                    "provider_result_code",
                    "provider_result_description",
                    "updated_at",
                ])
                return False

            try:
                normalized_phone = MpesaClient.normalize_phone_number(
                    str(callback_phone)
                )
                expected_phone = MpesaClient.normalize_phone_number(
                    str(payment.phone_number)
                )
            except MpesaError:
                return False

            if normalized_phone != expected_phone:
                payment.provider_result_description = (
                    "Callback phone mismatch; manual reconciliation required."
                )
                payment.save(update_fields=[
                    "callback_received_at",
                    "provider_result_code",
                    "provider_result_description",
                    "updated_at",
                ])
                return False

            duplicate_receipt = (
                Payment.objects.filter(
                    method=Payment.Method.MPESA,
                    mpesa_receipt_number=receipt,
                )
                .exclude(pk=payment.pk)
                .exists()
            )
            if duplicate_receipt:
                logger.warning(
                    "Duplicate M-Pesa receipt received for payment %s.",
                    payment.pk,
                )
                return False

            outstanding = get_outstanding_amount(booking=booking)
            if payment.amount > outstanding:
                payment.provider_result_description = (
                    "Payment received but booking balance conflicts; "
                    "manual reconciliation required."
                )
                payment.save(update_fields=[
                    "callback_received_at",
                    "provider_result_code",
                    "provider_result_description",
                    "updated_at",
                ])
                return False

            payment.mpesa_receipt_number = str(receipt)[:30]
            payment.transaction_reference = str(receipt)[:30]
            payment.status = Payment.Status.SUCCEEDED
            payment.save(update_fields=[
                "status",
                "mpesa_receipt_number",
                "transaction_reference",
                "callback_received_at",
                "provider_result_code",
                "provider_result_description",
                "updated_at",
            ])
            EventsInterface.publish(PaymentSucceeded(
                payment_id=payment.pk,
                booking_id=booking.id,
                customer_id=booking.customer_id,
                guest_customer_id=booking.guest_customer_id,
                amount=payment.amount,
            ))
            return True