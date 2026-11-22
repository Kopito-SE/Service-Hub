import logging
from django.db.models import Q
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError, NotFound
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt

from apps.bookings.models import Booking
from .models import Payment
from .selectors import get_business_payment
from .serializers import (
    BookingPaymentSummarySerializer,
    PaymentCreateSerializer,
    PaymentReversalCreateSerializer,
    PaymentReversalSerializer,
    PaymentSerializer,
    PaymentStatusSerializer,
    MpesaInitiateSerializer
)
from .services import PaymentService, MpesaPaymentService

logger = logging.getLogger(__name__)

class PaymentViewSet(viewsets.GenericViewSet):
    permission_classes = [IsAuthenticated]
    http_method_names = ["get", "post", "head", "options"]

    def get_queryset(self):
        user = self.request.user

        # Allow when they are the business owner or Customer who booked
        return Payment.objects.filter(
            Q(booking__business__owner=user) | Q(booking__customer=user)
        ).distinct()

    def get_serializer_class(self):
        if self.action == "create":
            return PaymentCreateSerializer

        if self.action == "set_status":
            return PaymentStatusSerializer

        if self.action == "reverse":
            return PaymentReversalCreateSerializer

        return PaymentSerializer

    def list(self, request):
        payment = self.get_queryset()
        serializer = PaymentSerializer(payment, many=True)
        return Response(serializer.data)

    def retrieve(self, request, pk=None):
        payment = self.get_queryset().filter(pk=pk).first()
        if payment is None:
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



    @action(detail=False, methods=["post"], url_path="mpesa/initiate")
    def initiate_mpesa(self, request):
        serializer = MpesaInitiateSerializer(
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
            # Allow if they are the owner OR the customer
            booking = Booking.objects.get(
                Q(business__owner=request.user) | Q(customer=request.user),
                pk=booking_id
            )

        except(Booking.DoesNotExist, ValueError):
            raise NotFound("Booking not Found")

        summary = PaymentService.get_booking_payment_summary(
            booking=booking,
            user=request.user
        )

        return Response(
            BookingPaymentSummarySerializer(summary).data
        )

@method_decorator(csrf_exempt, name="dispatch")
class MpesaCallbackView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request):
        if not isinstance(request.data, dict):
            return Response(
                {"detail": "Invalid callback payload."},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            processed = MpesaPaymentService.process_callback(request.data)

        except Exception:
            logger.exception("Unexpected error processing M-Pesa callback.")

            return Response(
                {"detail": "Callback processing failed"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

        if not processed:
            logger.warning("M-Pesa callback was not processed.")

        return Response(
            {"ResultCode": 0, "ResultDesc": "Accepted"},
            status=status.HTTP_200_OK
        )


