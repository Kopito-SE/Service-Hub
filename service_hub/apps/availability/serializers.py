from rest_framework import serializers
from apps.businesses.models import StaffMember
from .models import StaffWorkingHours, StaffTimeOff

class OwnedStaffMemberSerializerMixin:
    def validate_staff_member(self, staff_member):
        request = self.context.get("request")

        if request is None or not request.user.is_authenticated:
            raise serializers.ValidationError(
                "Authenticated user required"
            )

        owns_staff_member = StaffMember.objects.filter(
            pk=staff_member.pk,
            business__owner=request.user
        ).exists()

        if not owns_staff_member:
            raise serializers.ValidationError("You can only manage staff member belonging to your business")
        return staff_member

class StaffWorkingHoursSerializer(
    OwnedStaffMemberSerializerMixin,
    serializers.ModelSerializer,
):
    class Meta:
        model=StaffWorkingHours
        fields = [
            "id",
            "staff_member",
            "weekday",
            "opening_time",
            "closing_time"
        ]
        read_only_fields = ["id"]

class StaffTimeOffSerializer(
    OwnedStaffMemberSerializerMixin,
    serializers.ModelSerializer
):
    class Meta:
        model = StaffTimeOff
        fields = [
            "id",
            "staff_member",
            "start_time",
            "end_time",
            "reason",
            "created_at"
        ]
        read_only_fields = [
            "id",
            "created_at"
        ]

    def validate(self, attrs):
        start_time = attrs.get(
            "start_time",
            getattr(self.instance, "start_time", None)
        )
        end_time = attrs.get(
            "end_time",
            getattr(self.instance, "end_time", None)
        )

        if start_time is not None and end_time is not None:
            if end_time <= start_time:
                raise serializers.ValidationError({
                    "end_time":"End time must be after start_time."
                })
        return attrs

    # I used mixins because a mixin shares behaviour across classes without requiring them to inherit
    # from a common domain model