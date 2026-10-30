from decimal import Decimal

from django.db import transaction
from django.db.models import Sum
from rest_framework.exceptions import ValidationError

from apps.bookings.models import Booking
from .models import Payment, PaymentReversal
import logging
from django.utils import timezone
from .providers.mpesa import MpesaClient, MpesaError
from apps.events.dispatcher import dispatch
from apps.events.events import PaymentSucceeded, PaymentFailed

logger = logging.getLogger(__name__)

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
            allow_customer=False,
    ):
        booking = PaymentService._get_locked_booking(booking_id)
        if not (allow_customer and booking.customer_id == recorded_by.pk):
            PaymentService._check_business_owner(
                booking=booking,
                user=recorded_by,
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
        if new_status == Payment.Status.SUCCEEDED:
            event = PaymentSucceeded(
                payment_id=payment.pk,
                booking_id=booking.pk,
                customer_id=booking.customer_id,
                amount=payment.amount
            )
        else:
            event = PaymentFailed(
                payment_id=payment.pk,
                booking_id=booking.pk,
                customer_id=booking.customer_id,
                amount=payment.amount
            )
        transaction.on_commit(
            lambda event=event: dispatch(event),
            robust=True,
        )
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


class MpesaPaymentService:

    @staticmethod
    def initiate_payment(
        *,
        booking_id,
        amount,
        phone_number,
        recorded_by,
    ):
        # Create the pending payment first. This transaction finishes
        # before making the external HTTP request.
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
            # The provider might have received the request even if
            # our HTTP client timed out. Keep the payment pending.
            # Do not automatically issue another STK Push.
            payment.provider_result_description = str(exc)[:255]
            payment.save(
                update_fields=[
                    "provider_result_description",
                    "updated_at",
                ]
            )
            raise

        payment.checkout_request_id = result["CheckoutRequestID"]
        payment.merchant_request_id = result.get(
            "MerchantRequestID", ""
        )
        payment.provider_result_code = result.get("ResponseCode", "")
        payment.provider_result_description = result.get(
            "ResponseDescription", ""
        )[:255]
        payment.save(
            update_fields=[
                "checkout_request_id",
                "merchant_request_id",
                "provider_result_code",
                "provider_result_description",
                "updated_at",
            ]
        )

        return payment


    @staticmethod
    def process_callback(callback_data):
        """
        Process a Daraja STK callback.

        Repeated callbacks for an already processed payment are harmless.
        This validates the callback data but does not cryptographically
        authenticate its source.
        """
        stk_callback = (
            callback_data.get("Body", {}).get("stkCallback", {})
        )

        checkout_id = stk_callback.get("CheckoutRequestID")
        merchant_id = stk_callback.get("MerchantRequestID")
        result_code = stk_callback.get("ResultCode")
        result_description = str(
            stk_callback.get("ResultDesc", "")
        )[:255]

        if not checkout_id or result_code is None:
            logger.warning("Received an incomplete M-Pesa callback.")
            return False

        # First locate the payment without acquiring a lock. Then lock
        # the booking followed by the payment, consistently.
        initial_payment = Payment.objects.filter(
            checkout_request_id=checkout_id,
            method=Payment.Method.MPESA,
        ).only("pk", "booking_id").first()

        if initial_payment is None:
            logger.warning(
                "M-Pesa callback has an unknown checkout request ID."
            )
            return False

        with transaction.atomic():
            booking = Booking.objects.select_for_update().get(
                pk=initial_payment.booking_id
            )

            payment = Payment.objects.select_for_update().get(
                pk=initial_payment.pk
            )

            # Another callback may have processed this payment while
            # this request was waiting for the database locks.
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

            # Non-zero ResultCode means the STK transaction did not
            # complete successfully according to this callback.
            if str(result_code) != "0":
                payment.status = Payment.Status.FAILED
                payment.save(update_fields=[
                    "status",
                    "callback_received_at",
                    "provider_result_code",
                    "provider_result_description",
                    "updated_at",
                ])

                event = PaymentFailed(
                    payment_id=payment.pk,
                    booking_id=booking.pk,
                    customer_id=booking.customer_id,
                    amount=payment.amount
                )
                transaction.on_commit(
                    lambda event=event: dispatch(event),
                    robust=True
                )
                return True

            # Extract the metadata without assuming every field exists.
            metadata = (
                stk_callback.get("CallbackMetadata", {}).get("Item", [])
            )
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

            # Compare the amount actually reported with the requested amount.
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

            # Normalize both phone numbers before comparing them.
            try:
                normalized_phone = MpesaClient.normalize_phone_number(
                    callback_phone
                )
                expected_phone = MpesaClient.normalize_phone_number(
                    payment.phone_number
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

            # Never attach one M-Pesa receipt to multiple payments.
            duplicate_receipt = Payment.objects.filter(
                method=Payment.Method.MPESA,
                mpesa_receipt_number=receipt,
            ).exclude(pk=payment.pk).exists()

            if duplicate_receipt:
                logger.warning(
                    "Duplicate M-Pesa receipt received for payment %s.",
                    payment.pk,
                )
                return False

            # Ensure this payment does not exceed the booking's remaining
            # balance if other payments succeeded while the STK was pending.
            net_paid = PaymentService._get_net_paid_amount(booking)
            outstanding = booking.price_at_booking - net_paid

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
            payment.status = Payment.Status.SUCCEEDED
            payment.save(update_fields=[
                "status",
                "mpesa_receipt_number",
                "callback_received_at",
                "provider_result_code",
                "provider_result_description",
                "updated_at",
            ])

            event = PaymentSucceeded(
                payment_id=payment.pk,
                booking_id=booking.pk,
                customer_id=booking.customer_id,
                amount=payment.amount
            )

            transaction.on_commit(
                lambda event=event: dispatch(event),
                robust=True
            )

            return True
