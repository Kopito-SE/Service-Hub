
from rest_framework import serializers

from apps.bookings.models import Booking
from .models import Payment, PaymentReversal
from .services import PaymentService
from decimal import Decimal

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
            "transaction_reference",
            "recorded_by",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields


class PaymentCreateSerializer(serializers.Serializer):
    booking = serializers.PrimaryKeyRelatedField(
        queryset=Booking.objects.none()
    )
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

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        request = self.context.get("request")

        if request and request.user.is_authenticated:
            self.fields["booking"].queryset = Booking.objects.filter(
                business__owner=request.user
            )

    def create(self, validated_data):
        request = self.context["request"]

        return PaymentService.create_payment(
            booking_id=validated_data["booking"].pk,
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


