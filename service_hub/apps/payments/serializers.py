from rest_framework import serializers

from apps.bookings.interfaces import BookingInterfaceError, get_booking
from .models import Payment, PaymentReversal
from .services import PaymentService, MpesaPaymentService
from decimal import Decimal

from .providers.mpesa import MpesaClient, MpesaError

def get_authorized_booking(*, booking_id, user, allow_customer=False):
    try:
        booking = get_booking(booking_id=booking_id)

    except BookingInterfaceError:
        raise serializers.ValidationError({
            "booking": "The selected booking does not exist"
        })

    is_owner = booking.business_owner_id == user.pk
    is_customer = booking.customer_id == user.pk

    if not is_owner and not (allow_customer and is_customer):
        raise serializers.ValidationError({
            "booking": "You do not have permission to make a payment for this booking."
        })

    return booking

class PaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Payment
        fields = [
            "id",
            "booking",
            "amount",
            "currency",
            "method",
            "status",
            "mpesa_receipt_number",
            "transaction_reference",
            "recorded_by",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields


class MpesaInitiateSerializer(serializers.Serializer):

    booking = serializers.IntegerField(min_value=1)
    amount = serializers.DecimalField(
        max_digits=10,
        decimal_places=2,
        min_value=1,
    )
    phone_number = serializers.CharField(max_length=20)

    def validate_booking(self, value):
        request = self.context.get("request")

        if not request or not request.user.is_authenticated:
            raise serializers.ValidationError(
                "Authentication is required."
            )
        return get_authorized_booking(
            booking_id=value,
            user=request.user,
            allow_customer=True
        )

    def validate_phone_number(self, value):
        try:
            return MpesaClient.normalize_phone_number(value)
        except MpesaError as exc:
            raise serializers.ValidationError(str(exc))

    def create(self, validated_data):
        request = self.context["request"]

        try:
            return MpesaPaymentService.initiate_payment(
                booking_id=validated_data["booking"].id,
                amount=validated_data["amount"],
                phone_number=validated_data["phone_number"],
                recorded_by=request.user,
            )
        except MpesaError as exc:
            from rest_framework.exceptions import APIException

            error = APIException(
                "The STK Push outcome may be unknown. "
                "Check the payment status before retrying."
            )
            error.status_code = 502
            raise error from exc




class PaymentCreateSerializer(serializers.Serializer):
    booking = serializers.IntegerField(min_value=1)
    amount = serializers.DecimalField(
        max_digits=10,
        decimal_places=2,
        min_value=Decimal("0.01")
    )
    currency = serializers.ChoiceField(
        choices=[("KES", "KES")],
        default="KES",
    )
    method = serializers.ChoiceField(
        choices=Payment.Method.choices
    )
    transaction_reference = serializers.CharField(
        max_length=100,
        required=False,
        allow_blank=True,
    )

    def validate_booking(self, value):
        request = self.context.get("request")

        if not request or not request.user.is_authenticated:
            raise serializers.ValidationError(
                "Authentication is required."
            )
        return get_authorized_booking (
            booking_id=value,
            user=request.user,
            allow_customer=False
        )

    def create(self, validated_data):
        request = self.context["request"]

        return PaymentService.create_payment(
            booking_id=validated_data["booking"].id,
            amount=validated_data["amount"],
            method=validated_data["method"],
            recorded_by=request.user,
            transaction_reference=validated_data.get(
                "transaction_reference", ""
            ),
            currency=validated_data.get("currency", "KES"),
        )


class PaymentStatusSerializer(serializers.Serializer):
    status = serializers.ChoiceField(
        choices=[
            (Payment.Status.SUCCEEDED, "Succeeded"),
            (Payment.Status.FAILED, "Failed"),
        ]
    )


class PaymentReversalCreateSerializer(serializers.Serializer):
    amount = serializers.DecimalField(
        max_digits=10,
        decimal_places=2,
        min_value=Decimal("0.01")
    )
    reason = serializers.CharField(max_length=255)

    def create(self, validated_data):
        request = self.context["request"]

        return PaymentService.reverse_payment(
            payment_id=self.context["payment_id"],
            amount=validated_data["amount"],
            reason=validated_data["reason"],
            recorded_by=request.user,
        )


class PaymentReversalSerializer(serializers.ModelSerializer):
    class Meta:
        model = PaymentReversal
        fields = [
            "id",
            "payment",
            "amount",
            "reason",
            "recorded_by",
            "created_at",
        ]
        read_only_fields = fields


class BookingPaymentSummarySerializer(serializers.Serializer):
    booking_id = serializers.IntegerField()
    booking_price = serializers.DecimalField(
        max_digits=10, decimal_places=2
    )
    net_paid = serializers.DecimalField(
        max_digits=10, decimal_places=2
    )
    outstanding_balance = serializers.DecimalField(
        max_digits=10, decimal_places=2
    )
