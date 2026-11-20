from rest_framework.exceptions import ValidationError
from django.utils import timezone
from django.db import transaction

from apps.availability.models import StaffWorkingHours, StaffTimeOff
from apps.availability.services.availability_service import AvailabilityService
from apps.businesses.interfaces import (
    BusinessInterface,
    BusinessInterfaceError,
)


class AvailabilityManagementService:

    @staticmethod
    def _get_staff_member(staff_member_id):
        try:
            return BusinessInterface.get_staff_member_by_id(
                staff_member_id=staff_member_id
            )
        except BusinessInterfaceError as exc:
            raise ValidationError(str(exc))

    @staticmethod
    def _lock_business_for_staff_member(staff_member_id):
        staff_member = AvailabilityManagementService._get_staff_member(
            staff_member_id
        )

        try:
            BusinessInterface.get_business_for_update(
                business_id=staff_member.business_id
            )
        except BusinessInterfaceError as exc:
            raise ValidationError(str(exc))

        return staff_member

    @staticmethod
    @transaction.atomic
    def create_time_off(
        *,
        staff_member_id,
        start_time,
        end_time,
        reason=""
    ):
        staff = AvailabilityManagementService._lock_business_for_staff_member(
            staff_member_id
        )

        if end_time <= start_time:
            raise ValidationError({
                "end_time": "End time must be after start time."
            })

        AvailabilityService.validate_time_off_against_bookings(
            staff_member_id=staff.id,
            start_time=start_time,
            end_time=end_time
        )

        return StaffTimeOff.objects.create(
            staff_member_id=staff.id,
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
        staff = AvailabilityManagementService._lock_business_for_staff_member(
            staff_member_id
        )

        if closing_time <= opening_time:
            raise ValidationError({
                "closing_time": "Closing time must be after opening time."
            })

        AvailabilityService.validate_working_hours_change(
            staff_member_id=staff.id,
            weekday=weekday,
            opening_time=opening_time,
            closing_time=closing_time
        )

        if StaffWorkingHours.objects.filter(
            staff_member_id=staff.id,
            weekday=weekday
        ).exists():
            raise ValidationError({
                "weekday": (
                    "Working hours already exist for this weekday. "
                    "Update the existing record instead."
                )
            })

        return StaffWorkingHours.objects.create(
            staff_member_id=staff.id,
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
        closing_time
    ):
        try:
            schedule = StaffWorkingHours.objects.get(
                pk=working_hours_id
            )
        except StaffWorkingHours.DoesNotExist:
            raise ValidationError({
                "working_hours": "Working-hours record does not exist."
            })

        staff = AvailabilityManagementService._lock_business_for_staff_member(
            schedule.staff_member_id
        )

        schedule = StaffWorkingHours.objects.select_for_update().get(
            pk=working_hours_id
        )

        if closing_time <= opening_time:
            raise ValidationError({
                "closing_time": "Closing time must be after opening time."
            })

        duplicate = StaffWorkingHours.objects.filter(
            staff_member_id=staff.id,
            weekday=weekday
        ).exclude(pk=schedule.pk).exists()

        if duplicate:
            raise ValidationError({
                "weekday": "Working hours already exist for this weekday."
            })

        AvailabilityService.validate_working_hours_change(
            staff_member_id=staff.id,
            weekday=weekday,
            opening_time=opening_time,
            closing_time=closing_time
        )

        schedule.weekday = weekday
        schedule.opening_time = opening_time
        schedule.closing_time = closing_time

        schedule.save(
            update_fields=[
                "weekday",
                "opening_time",
                "closing_time"
            ]
        )

        return schedule

    @staticmethod
    @transaction.atomic
    def delete_working_hours(*, working_hours_id):
        try:
            schedule = StaffWorkingHours.objects.get(
                pk=working_hours_id
            )
        except StaffWorkingHours.DoesNotExist:
            raise ValidationError({
                "working_hours": "Working-hours record does not exist."
            })

        staff = AvailabilityManagementService._lock_business_for_staff_member(
            schedule.staff_member_id
        )

        schedule = StaffWorkingHours.objects.select_for_update().get(
            pk=working_hours_id
        )

        future_reservations = (
            AvailabilityService._get_blocking_reservations(
                staff_member_id=staff.id
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
        reason=""
    ):
        try:
            time_off = StaffTimeOff.objects.get(
                pk=time_off_id
            )
        except StaffTimeOff.DoesNotExist:
            raise ValidationError({
                "time_off": "Time-off record does not exist."
            })

        staff = AvailabilityManagementService._lock_business_for_staff_member(
            time_off.staff_member_id
        )

        time_off = StaffTimeOff.objects.select_for_update().get(
            pk=time_off_id
        )

        if end_time <= start_time:
            raise ValidationError({
                "end_time": "End time must be after start time."
            })

        AvailabilityService.validate_time_off_against_bookings(
            staff_member_id=staff.id,
            start_time=start_time,
            end_time=end_time
        )

        time_off.start_time = start_time
        time_off.end_time = end_time
        time_off.reason = reason

        time_off.save(
            update_fields=[
                "start_time",
                "end_time",
                "reason"
            ]
        )

        return time_off

    @staticmethod
    @transaction.atomic
    def delete_time_off(*, time_off_id):
        try:
            time_off = StaffTimeOff.objects.get(
                pk=time_off_id
            )
        except StaffTimeOff.DoesNotExist:
            raise ValidationError({
                "time_off": "Time-off record does not exist."
            })

        AvailabilityManagementService._lock_business_for_staff_member(
            time_off.staff_member_id
        )

        time_off = StaffTimeOff.objects.select_for_update().get(
            pk=time_off_id
        )

        time_off.delete()
