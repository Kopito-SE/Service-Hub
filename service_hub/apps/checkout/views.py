from celery.bin.result import result
from rest_framework.views import APIView
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated

from .serializers import GuestCheckoutSerializer
from .serializers import AuthenticatedCheckoutSerializer

class GuestCheckoutCreateAPIView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        serializer = GuestCheckoutSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        result = serializer.save()

        booking = result.booking
        checkout_result = result.checkout
        checkout = checkout_result.checkout

        response_data = {
            "booking": {
                "id": booking.id,
                "business_id": booking.business_id,
                "status": booking.status,
                "price_at_booking": str(booking.price_at_booking)
            },

            "checkout": {
                "id": str(checkout.id),
                "booking_id": checkout.booking_id,
                "amount_due": str(checkout.amount_due),
                "currency": checkout.currency,
                "status": checkout.status,
                "expires_at": checkout.expires_at.isoformat()
            },
            "guest_access_token": checkout_result.guest_access_token
        }
        return Response(
            response_data,
            status=status.HTTP_201_CREATED
        )

class AuthenticatedCheckoutCreateAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = AuthenticatedCheckoutSerializer(
            data=request.data,
            context={"request": request},
        )

        serializer.is_valid(raise_exception=True)

        result = serializer.save()

        booking = result.booking
        checkout_result = result.checkout
        checkout = checkout_result.checkout

        response_data = {
            "booking": {
                "id": booking.id,
                "business_id": booking.business_id,
                "status": booking.status,
                "price_at_booking": str(booking.price_at_booking)
            },
            "checkout": {
                "id": str(checkout.id),
                "booking_id": checkout.booking_id,
                "amount_due": str(checkout.amount_due),
                "currency": checkout.currency,
                "status": checkout.status,
                "expires_at": checkout.expires_at.isoformat()
            },
        }
        return Response(
            response_data,
            status=status.HTTP_201_CREATED
        )