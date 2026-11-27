from rest_framework import serializers
from apps.businesses.interfaces import (
    BusinessInterface,
    BusinessInterfaceError,
)
from apps.service_catalog.interfaces import (
    ServiceInterface,
    ServiceInterfaceError,
)

from .models import Booking
from apps.bookings.services import BookingService


class BookingSerializer(serializers.ModelSerializer):

    # Accept IDs instead of resolving foreign-key model instances.
    business = serializers.IntegerField(
        source="business_id",
        min_value=1
    )

    service = serializers.IntegerField(
        source="service_id",
        min_value=1
    )

    staff_member = serializers.IntegerField(
        source="staff_member_id",
        min_value=1,
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
            "updated_at",
        ]

        read_only_fields = [
            "id",
            "end_time",
            "status",
            "price_at_booking",
            "created_at",
            "updated_at",
        ]

    def validate(self, attrs):
        business_id = attrs["business_id"]
        service_id = attrs["service_id"]
        staff_member_id = attrs.get("staff_member_id")

        # 1. Validate the business through its public interface.
        try:
            BusinessInterface.get_active_business(
                business_id=business_id
            )
        except BusinessInterfaceError as exc:
            raise serializers.ValidationError({
                "business": str(exc)
            }) from exc

        # 2. Validate that the service is active and belongs
        #    to the selected business.
        try:
            ServiceInterface.get_active_service(
                service_id=service_id,
                business_id=business_id,
            )
        except ServiceInterfaceError as exc:
            raise serializers.ValidationError({
                "service": str(exc)
            }) from exc

        # 3. Validate staff membership when a staff member
        #    has been provided.
        if staff_member_id is not None:
            try:
                BusinessInterface.get_active_staff_member(
                    staff_member_id=staff_member_id,
                    business_id=business_id,
                )
            except BusinessInterfaceError as exc:
                raise serializers.ValidationError({
                    "staff_member": str(exc)
                }) from exc

        return attrs

    def create(self, validated_data):
        customer = self.context["request"].user

        return BookingService.create_booking(
            customer=customer,
            business_id=validated_data["business_id"],
            service_id=validated_data["service_id"],
            staff_member_id=validated_data.get("staff_member_id"),
            start_time=validated_data["start_time"],
            notes=validated_data.get("notes", ""),
        )
