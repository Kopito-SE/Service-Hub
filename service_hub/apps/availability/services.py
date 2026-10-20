from rest_framework.exceptions import ValidationError
from django.utils import timezone

from .models import StaffWorkingHours

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
                    "for the selected day"
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
                    "The Appointment must fit within the staff member's "
                    "working hours."
                )
            })
