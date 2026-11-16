from rest_framework.exceptions import ValidationError
from django.utils import timezone
from django.db import transaction
from apps.availability.models import StaffWorkingHours, StaffTimeOff, SlotReservation
from apps.businesses.models import Business, StaffMember
from apps.availability.services.availability_service import AvailabilityService

class AvailabilityManagementService:
    @staticmethod
    @transaction.atomic
    def create_time_off(
            *,
            staff_member_id,
            start_time,
            end_time,
            reason="",
    ):
        # Lock the business before checking for conflicting bookings.
        try:
            staff = StaffMember.objects.select_related(
                "business"
            ).get(pk=staff_member_id)
        except StaffMember.DoesNotExist:
            raise ValidationError({
                "staff_member": "Staff member does not exist."
            })
        Business.objects.select_for_update().get(
            pk=staff.business_id
        )

        # Re-fetch after acquiring the coordination lock.
        staff = StaffMember.objects.get(pk=staff_member_id)

        if end_time <= start_time:
            raise ValidationError({
                "end_time": "End time must be after start time"
            })

        AvailabilityService.validate_time_off_against_bookings(
            staff_member=staff,
            start_time=start_time,
            end_time=end_time
        )

        return StaffTimeOff.objects.create(
            staff_member=staff,
            start_time=start_time,
            end_time=end_time,
            reason=reason
        )

    @staticmethod
    @transaction.atomic
    def create_working_hours(
            *,
            staff_member_id,
            weekday,
            opening_time,
            closing_time
    ):
        try:
            staff = StaffMember.objects.get(pk=staff_member_id)

        except StaffMember.DoesNotExist:
            raise ValidationError({
                "staff_member": "Staff member does not exist."
            })
        Business.objects.select_for_update().get(
            pk=staff.business_id
        )

        if closing_time <= opening_time:
            raise ValidationError({
                "closing_time": "Closing time must be after opening time."
            })

        AvailabilityService.validate_working_hours_change(
            staff_member=staff,
            weekday=weekday,
            opening_time=opening_time,
            closing_time=closing_time
        )

        if StaffWorkingHours.objects.filter(
            staff_member=staff,
            weekday=weekday
        ).exists():
            raise ValidationError({
                "weekday": (
                    "Working hours already exist for this weekday. "
                    "Update the existing record instead."
                )
            })
        return StaffWorkingHours.objects.create(
            staff_member=staff,
            weekday=weekday,
            opening_time=opening_time,
            closing_time=closing_time
        )

    @staticmethod
    @transaction.atomic
    def update_working_hours(
        *,
        working_hours_id,
        weekday,
        opening_time,
        closing_time,
    ):
        try:
            schedule = StaffWorkingHours.objects.select_related(
                "staff_member"
            ).get(pk=working_hours_id)
        except StaffWorkingHours.DoesNotExist:
            raise ValidationError({
                "working_hours": "Working-hours record does not exist."
            })

        # Coordinate this change with booking creation and other
        # availability changes for the same business.
        Business.objects.select_for_update().get(
            pk=schedule.staff_member.business_id
        )

        schedule = StaffWorkingHours.objects.select_for_update().get(
            pk=working_hours_id
        )

        if closing_time <= opening_time:
            raise ValidationError({
                "closing_time": "Closing time must be after opening time."
            })

        duplicate = StaffWorkingHours.objects.filter(
            staff_member=schedule.staff_member,
            weekday=weekday,
        ).exclude(pk=schedule.pk).exists()

        if duplicate:
            raise ValidationError({
                "weekday": "Working hours already exist for this weekday."
            })

        AvailabilityService.validate_working_hours_change(
            staff_member=schedule.staff_member,
            weekday=weekday,
            opening_time=opening_time,
            closing_time=closing_time,
        )

        schedule.weekday = weekday
        schedule.opening_time = opening_time
        schedule.closing_time = closing_time
        schedule.save(
            update_fields=["weekday", "opening_time", "closing_time"]
        )

        return schedule

    @staticmethod
    @transaction.atomic
    def delete_working_hours(*, working_hours_id):
        try:
            schedule = StaffWorkingHours.objects.select_related(
                "staff_member"
            ).get(pk=working_hours_id)
        except StaffWorkingHours.DoesNotExist:
            raise ValidationError({
                "working_hours": "Working-hours record does not exist."
            })

        Business.objects.select_for_update().get(
            pk=schedule.staff_member.business_id
        )

        schedule = StaffWorkingHours.objects.select_for_update().get(
            pk=working_hours_id
        )

        future_reservations = (
            AvailabilityService._get_blocking_reservations(
                staff_member=schedule.staff_member,
            )
            .filter(end_time__gt=timezone.now())
        )

        for reservation in future_reservations:
            local_start = timezone.localtime(reservation.start_time)

            if local_start.weekday() == schedule.weekday:
                raise ValidationError({
                    "working_hours": (
                        "These working hours cannot be deleted because "
                        "the staff member has future reservations on this day."
                    )
                })

        schedule.delete()

    @staticmethod
    @transaction.atomic
    def update_time_off(
        *,
        time_off_id,
        start_time,
        end_time,
        reason="",
    ):
        try:
            time_off = StaffTimeOff.objects.select_related(
                "staff_member"
            ).get(pk=time_off_id)
        except StaffTimeOff.DoesNotExist:
            raise ValidationError({
                "time_off": "Time-off record does not exist."
            })

        Business.objects.select_for_update().get(
            pk=time_off.staff_member.business_id
        )

        time_off = StaffTimeOff.objects.select_for_update().get(
            pk=time_off_id
        )

        if end_time <= start_time:
            raise ValidationError({
                "end_time": "End time must be after start time."
            })

        AvailabilityService.validate_time_off_against_bookings(
            staff_member=time_off.staff_member,
            start_time=start_time,
            end_time=end_time,
        )

        time_off.start_time = start_time
        time_off.end_time = end_time
        time_off.reason = reason
        time_off.save(
            update_fields=["start_time", "end_time", "reason"]
        )

        return time_off

    @staticmethod
    @transaction.atomic
    def delete_time_off(*, time_off_id):
        try:
            time_off = StaffTimeOff.objects.select_related(
                "staff_member"
            ).get(pk=time_off_id)
        except StaffTimeOff.DoesNotExist:
            raise ValidationError({
                "time_off": "Time-off record does not exist."
            })

        Business.objects.select_for_update().get(
            pk=time_off.staff_member.business_id
        )

        time_off = StaffTimeOff.objects.select_for_update().get(
            pk=time_off_id
        )
        time_off.delete()