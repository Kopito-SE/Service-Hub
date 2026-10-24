from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated

from .models import StaffWorkingHours, StaffTimeOff
from .serializers import(StaffWorkingHoursSerializer, StaffTimeOffSerializer)
from .services import AvailabilityManagementService


class StaffWorkingHoursViewSet(viewsets.ModelViewSet):
    serializer_class = StaffWorkingHoursSerializer
    permission_classes = [IsAuthenticated]
    http_method_names = [
        "get", "post", "put", "patch", "delete", "head", "options"
    ]

    def get_queryset(self):
        return(
            StaffWorkingHours.objects
            .filter(staff_member__business__owner=self.request.user)
            .select_related("staff_member", "staff_member__business")
        )

    def perform_create(self, serializer):
        data = serializer.validated_data

        serializer.instance = (
            AvailabilityManagementService.create_working_hours(
                staff_member_id=data["staff_member"].pk,
                weekday=data["weekday"],
                opening_time=data["opening_time"],
                closing_time=data["closing_time"],
            )
        )
    def perform_update(self, serializer):
        data = serializer.validated_data
        instance = serializer.instance

        if (
            "staff_member" in data
            and data["staff_member"].pk != instance.staff_member_id
        ):
            from rest_framework.exeptions import ValidationError

            raise ValidationError({
                "staff_member": (
                    "You cannot reassign a working-hours record "
                    "to another staff member. Delete it and create "
                    "a new record instead"
                )
            })
        serializer.instance = (
            AvailabilityManagementService.update_working_hours(
                working_hours_id=instance.pk,
                weekday=data.get("weekday", instance.weekday),
                opening_time=data.get("opening_time", instance.opening_time),
                closing_time=data.get("closing_time", instance.closing_time)
            ),
        )

    def perform_destroy(self, instance):
        AvailabilityManagementService.delete_working_hours(
            working_hours_id=instance.pk
        )

class StaffTimeOffViewSet(viewsets.ModelViewSet):
    serializer_class = StaffTimeOffSerializer
    permission_classes = [IsAuthenticated]

    http_method_names = [
        "get", "post", "patch", "put", "delete", "head", "options"
    ]

    def get_queryset(self):
        return(
            StaffTimeOff.objects
            .filter(staff_member__business__owner=self.request.user)
            .select_related("staff_member", "staff_member__business")
        )

    def perform_create(self, serializer):
        data = serializer.validated_data

        serializer.instance = (
            AvailabilityManagementService.create_time_off(
                staff_member_id=data["staff_member"].pk,
                start_time=data["start_time"],
                end_time=data["end_time"],
                reason=data.get("reason", ""),
            )
        )

    def perform_update(self, serializer):
        data = serializer.validated_data
        instance = serializer.instance

        if (
            "staff_member" in data
            and data["staff_member"].pk != instance.staff_member_id
        ):
            from rest_framework.exceptions import ValidationError
            raise ValidationError({
                "staff_member": (
                    "You cannot reassign a time-off record "
                    "to another staff_member. Delete it and create "
                    "a new record instead."
                )
            })
        serializer.instance = (
            AvailabilityManagementService.update_time_off(
                time_off_id=instance.pk,
                start_time=data.get("start_time", instance.start_time),
                end_time=data.get("end_time", instance.end_time),
                reason=data.get("reason", instance.reason)
            )
        )

    def perform_destroy(self, instance):
        AvailabilityManagementService.delete_time_off(
            time_off_id=instance.pk
        )