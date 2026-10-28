from rest_framework import serializers
from apps.notifications.models import Notification

class NotificationSerializer(serializers.ModelSerializer):
    is_read = serializers.SerializerMethodField()

    class Meta:
        model = Notification
        fields = [
            "id",
            "channel",
            "event_type",
            "subject",
            "status",
            "sent_at",
            "read_at",
            "is_read",
            "created_at"
        ]
        read_only_fields = fields

    def get_is_read(self, obj):
        return obj.read_at is not None
