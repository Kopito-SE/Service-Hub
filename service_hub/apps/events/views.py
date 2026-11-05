from rest_framework.generics import RetrieveAPIView
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response
from rest_framework.views import APIView
from apps.events.monitoring import get_outbox_health_summary
from apps.events.serializers import OutboxHealthSerializer
from rest_framework import status
from rest_framework.exceptions import NotFound
from rest_framework import generics
from apps.events.models import EventDelivery
from apps.events.serializers import (
    ManualRetryRequestSerializer,
    EventDeliveryRetrySerializer,
    EventDeliverySerializer
)
from apps.events.retry_service import DeliveryNotRetryableError
from apps.events.retry_service import retry_dead_delivery
from django.shortcuts import get_object_or_404

class OutboxMonitoringView(APIView):
    permission_classes = [IsAdminUser]

    def get(self, request):
        summary = get_outbox_health_summary()

        serializer = OutboxHealthSerializer(data=summary)
        serializer.is_valid(raise_exception=True)

        return Response(serializer.data)

class EventDeliveryListView(generics.ListAPIView):
    serializer_class = EventDeliverySerializer
    permission_classes = [IsAdminUser]

    def get_queryset(self):
        queryset = EventDelivery.objects.select_related(
            "event"
        ).order_by("-created_at")

        delivery_status = self.request.query_params.get("status")
        event_type = self.request.query_params.get("event_type")

        if delivery_status:
            queryset = queryset.filter(status=delivery_status)

        if event_type:
            queryset = queryset.filter(event__event_type=event_type)

        return queryset

class EventDeliveryDetailView(generics.RetrieveAPIView):
    serializer_class = EventDeliverySerializer
    permission_classes = [IsAdminUser]

    queryset = EventDelivery.objects.select_related("event")

class EventDeliveryRetryView(APIView):
    permission_classes = [IsAdminUser]

    def post(self, request, pk):
        serializer = ManualRetryRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        reason = serializer.validated_data["reason"]

        try:
            delivery = retry_dead_delivery(
                delivery_id=pk,
                requested_by=request.user,
                reason=reason
            )
        except EventDelivery.DoesNotExist:
            raise NotFound("Event delivery not found.")

        except DeliveryNotRetryableError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_409_CONFLICT)

        response_serializer  = EventDeliverySerializer(delivery)

        return Response(
            response_serializer.data,
            status=status.HTTP_202_ACCEPTED
        )

class EventDeliveryRetryHistoryView(generics.ListAPIView):
    serializer_class = EventDeliveryRetrySerializer
    permission_classes = [IsAdminUser]

    def get_queryset(self):
        delivery = get_object_or_404(
            EventDelivery,
            pk=self.kwargs["pk"]
        )

        return delivery.retry_history.select_related(
            "requested_by"
        ).all()