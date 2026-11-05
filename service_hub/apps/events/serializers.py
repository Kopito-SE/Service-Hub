from rest_framework import serializers
from apps.events.models import EventDelivery, EventDeliveryRetry

class EventsCountsSerializer(serializers.Serializer):
    pending = serializers.IntegerField()
    processing = serializers.IntegerField()
    completed = serializers.IntegerField()
    dead = serializers.IntegerField()

class DeliveryCountsSerializer(serializers.Serializer):
    pending = serializers.IntegerField()
    processing = serializers.IntegerField()
    succeeded = serializers.IntegerField()
    failed = serializers.IntegerField()
    dead = serializers.IntegerField()

class OutboxHealthSerializer(serializers.Serializer):
    events = EventsCountsSerializer()
    deliveries = DeliveryCountsSerializer()
    stale_deliveries = serializers.IntegerField()
    unalerted_dead_deliveries = serializers.IntegerField()
    generated_at = serializers.DateTimeField()

class EventDeliverySerializer(serializers.ModelSerializer):
    event_type = serializers.CharField(
        source="event.event_type",
        read_only=True
    )

    class Meta:
        model = EventDelivery
        fields = [
            "id",
            "event",
            "event_type",
            "handler_key",
            "status",
            "attempts",
            "max_attempts",
            "next_attempt_at",
            "last_error",
            "processing_started_at",
            "alerted_at",
            "created_at",
            "updated_at",
            "processed_at"
        ]
        read_only_fields = fields

class ManualRetryRequestSerializer(serializers.Serializer):
    reason = serializers.CharField(
        required=True,
        allow_blank=False,
        trim_whitespace=True,
        max_length=500
    )

class EventDeliveryRetrySerializer(serializers.ModelSerializer):
    class Meta:
        model = EventDeliveryRetry
        fields = [
            "id",
            "delivery",
            "requested_by",
            "retry_number",
            "previous_attempts",
            "previous_error",
            "reason",
            "created_at"
        ]
        read_only_fields = fields