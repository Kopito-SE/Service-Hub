from rest_framework.exceptions import ValidationError
from django.utils import timezone
from .models import StaffWorkingHours, StaffTimeOff

from django.db import transaction
from apps.businesses.models import Business, StaffMember
from apps.bookings.models import Booking


class AvailabilityService:
    @staticmethod
    def validate_staff_availability(
            *,
            staff_member,
            start_time,
            end_time,
    ):
        # Convert aware datetime to Django's current local timezone
        local_start = timezone.localtime(start_time)
        local_end = timezone.localtime(end_time)

        # Our initial scheduling policy does not allow overnight services.
        if local_start.date() != local_end.date():
            raise ValidationError({
                "start_time": (
                    "Appointments must start and end on the same day."
                )
            })
        weekday = local_start.weekday()

        working_hours = StaffWorkingHours.objects.filter(
            staff_member=staff_member,
            weekday=weekday,

        ).first()

        if working_hours is None:
            raise ValidationError({
                "start_time":(
                    "This staff member has no working hours configured"
                    " for the selected day"
                )
            })

        appointment_start = local_start.time().replace(tzinfo=None)
        appointment_end = local_end.time().replace(tzinfo=None)

        if (
            appointment_start < working_hours.opening_time
            or appointment_end > working_hours.closing_time
        ):
            raise ValidationError({
                "start_time": (
                    "The Appointment must fit within the staff member's"
                    " working hours."
                )
            })

    @staticmethod
    def validate_no_time_off(
            *,
            staff_member,
            start_time,
            end_time
    ):
        has_conflict = StaffTimeOff.objects.filter(
            staff_member=staff_member,
            start_time__lt=end_time,
            end_time__gt=start_time
        ).exists()

        if has_conflict:
            raise ValidationError({
                "start_time": (
                    "The staff member is unavailable during this period."
                )
            })

    @staticmethod
    def validate_time_off_against_bookings(
            *,
            staff_member,
            start_time,
            end_time
    ):
        from apps.bookings.models import Booking

        conflicts = Booking.objects.filter(
            staff_member=staff_member,
            status__in=[
                Booking.Status.PENDING,
                Booking.Status.CONFIRMED,
            ],
            start_time__lt=end_time,
            end_time__gt=start_time
        )

        if conflicts.exists():
            raise ValidationError({
            "start_time":(
                "Time off cannot overlap a pending or confirmed booking."
            )
        })

    @staticmethod
    def validate_working_hours_change(
            *,
            staff_member,
            weekday,
            opening_time,
            closing_time
    ):
        from apps.bookings.models import Booking

        future_bookings = Booking.objects.filter(
            staff_member=staff_member,
            status__in=[
                Booking.Status.PENDING,
                Booking.Status.CONFIRMED
            ],
            end_time__gt=timezone.now(),
        )

        for booking in future_bookings:
            local_start = timezone.localtime(booking.start_time)
            local_end = timezone.localtime(booking.end_time)

            if local_start.weekday() != weekday:
                continue

            booking_start = local_start.time().replace(tzinfo=None)
            booking_end = local_end.time().replace(tzinfo=None)

            if booking_start < opening_time:
                raise ValidationError({
                    "opening_time": "Opening time is too late for an existing booking on this day."
                })

            if booking_end > closing_time:
                raise ValidationError({
                    "closing_time": "Closing time is too early for an existing booking on this day."
                })


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

        # Import locally to avoid making the components tightly coupled
        # at module-import time.
        from apps.bookings.models import Booking

        future_bookings = Booking.objects.filter(
            staff_member=schedule.staff_member,
            status__in=[
                Booking.Status.PENDING,
                Booking.Status.CONFIRMED,
            ],
            start_time__gt=timezone.now(),
        )

        for booking in future_bookings:
            local_start = timezone.localtime(booking.start_time)

            if local_start.weekday() == schedule.weekday:
                raise ValidationError({
                    "working_hours": (
                        "These working hours cannot be deleted because "
                        "the staff member has future bookings on this day."
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