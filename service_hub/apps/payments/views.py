from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.bookings.models import Booking
from .models import Payment
from .selectors import get_business_payments, get_business_payment
from .serializers import (
   BookingPaymentSummarySerializer,
   PaymentCreateSerializer,
   PaymentReversalCreateSerializer,
   PaymentReversalSerializer,
   PaymentSerializer,
   PaymentStatusSerializer
)

from .services import PaymentService

class PaymentViewSet(viewsets.GenericViewSet):
    permission_classes = [IsAuthenticated]
    http_method_names = ["get", "post", "head", "options"]

    def get_queryset(self):
        return get_business_payments(self.request.user)

    def get_serializer_class(self):
        if self.action == "create":
            return PaymentCreateSerializer

        if self.action == "set_status":
            return PaymentStatusSerializer

        if self.action == "reverse":
            return PaymentReversalCreateSerializer

        return PaymentSerializer

    def list(self, request):
        payments = self.get_queryset()
        serializer = PaymentSerializer(payment, many=True)
        return Response(serializer.data)

    def retrieve(self, request, pk=None):
        payment = get_business_payment(
            user=request.user,
            payment_id=pk
        )
        if payment is None:
            from rest_framework.exceptions import NotFound
            raise NotFound("Payment not found.")

        return Response(PaymentSerializer(payment).data)

    def create(self, request):
        serializer = PaymentCreateSerializer(
            data=request.data,
            context={"request": request},
        )
        serializer.is_valid(raise_exception=True)
        payment = serializer.save()

        return Response(
            PaymentSerializer(payment).data,
            status=status.HTTP_201_CREATED
        )

    @action(detail=True, methods=["post"], url_path="status")
    def set_status(self, request, pk=None):
        payment = self.get_queryset().filter(pk=pk).first()

        if payment is None:
            from rest_framework.exceptions import NotFound
            raise NotFound("Payment not found.")

        serializer = PaymentStatusSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        payment = PaymentService.change_payment_status(
            payment_id=payment.pk,
            new_status=serializer.validated_data["status"],
            user=request.user
        )

        return Response(PaymentSerializer(payment).data)

    @action(detail=True, methods=["post"], url_path="reverse")
    def reverse(self, request, pk=None):
        payment = self.get_queryset().filter(pk=pk).first()

        if payment is None:
            from rest_framework.exceptions import NotFound
            raise NotFound("Payment not Found.")

        serializer = PaymentReversalCreateSerializer(
            data=request.data,
            context={
                "request": request,
                "payment_id": payment.pk
            },
        )
        serializer.is_valid(raise_exception=True)
        reversal = serializer.save()

        return Response(
            PaymentReversalSerializer(reversal).data,
            status=status.HTTP_201_CREATED
        )

    @action(detail=False, methods=["get"], url_path="booking-summary")
    def booking_summary(self, request):
        booking_id = request.query_params.get("booking_id")

        if not booking_id:
            raise ValidationError({
                "booking_id": "This query parameter is required."
            })

        try:
            booking = Booking.objects.get(
                pk=booking_id,
                business__owner=request.user
            )
        except(Booking.DoesNotExist, ValueError):
            from rest_framework.exceptions import NotFound
            raise NotFound("Booking not Found")

        summary = PaymentService.get_booking_payment_summary(
            booking=booking,
            user=request.user
        )

        return Response(
            BookingPaymentSummarySerializer(summary).data
        )





