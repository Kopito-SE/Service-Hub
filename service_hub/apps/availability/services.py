from rest_framework.exceptions import ValidationError
from django.utils import timezone

from .models import StaffWorkingHours, StaffTimeOff
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


