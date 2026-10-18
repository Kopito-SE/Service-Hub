from rest_framework import serializers

from apps.businesses.models import Business, StaffMember
from apps.service_catalog.models import Service

from .models import Booking
from .services import BookingService

class BookingSerializer(serializers.ModelSerializer):

    business = serializers.PrimaryKeyRelatedField(
        queryset=Business.objects.filter(is_active=True)
    )

    service = serializers.PrimaryKeyRelatedField(
        queryset=Service.objects.filter(is_active=True)
    )

    staff_member = serializers.PrimaryKeyRelatedField(
        queryset=StaffMember.objects.filter(is_active=True),
        required=False,
        allow_null=True,
    )

    class Meta:
        model = Booking
        fields = [
            "id",
            "business",
            "service",
            "staff_member",
            "start_time",
            "end_time",
            "status",
            "notes",
            "price_at_booking",
            "created_at",
            "updated_at"
        ]
        read_only_fields = [
            "id",
            "end_time",
            "status",
            "price_at_booking",
            "created_at",
            "updated_at"

        ]

    def create(self, validated_data):
        customer = self.context["request"].user
        business = validated_data["business"]
        service = validated_data["service"]
        staff_member = validated_data.get("staff_member")

        return BookingService.create_booking(
            customer=customer,
            business_id=business.pk,
            service_id=service.pk,
            staff_member_id=(
                staff_member.pk if staff_member else None
            ),
            start_time=validated_data["start_time"],
            notes=validated_data.get("notes", ""),
        )


