from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .selectors import get_customer_bookings
from .serializers import BookingSerializer
from .services import BookingService

class BookingViewSet(viewsets.ModelViewSet):
    serializer_class = BookingSerializer
    permission_classes = [IsAuthenticated]
    http_method_names = ["get", "post", "head", "options"]

    def get_queryset(self):
        return get_customer_bookings(self.request.user)

    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        booking = self.get_object()
        booking = BookingService.cancel_booking(booking=booking)
        serializer = self.get_serializer(booking)
        return Response(serializer.data, status=status.HTTP_200_OK)