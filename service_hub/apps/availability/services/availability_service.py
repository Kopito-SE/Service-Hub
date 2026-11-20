
from rest_framework.exceptions import ValidationError
from django.utils import timezone
from django.db.models import Q

from apps.availability.models import (
    StaffWorkingHours,
    StaffTimeOff,
    SlotReservation,
)


class AvailabilityService:

    # Reservation Query Helper
    @staticmethod
    def _get_blocking_reservations(*, staff_member_id):
        """
        Return reservations that currently occupy a staff member's time.

        ACTIVE and CONFIRMED reservations always block.
        HELD reservations block while their expiry is in the future.
        RELEASED reservations never block.
        """
        now = timezone.now()

        return SlotReservation.objects.filter(
            staff_member_id=staff_member_id
        ).filter(
            Q(
                status__in=[
                    SlotReservation.Status.ACTIVE,
                    SlotReservation.Status.CONFIRMED,
                ]
            )
            |
            Q(
                status=SlotReservation.Status.HELD,
                expires_at__gt=now,
            )
        )

    @staticmethod
    def validate_staff_availability(
        *,
        staff_member_id,
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
            staff_member_id=staff_member_id,
            weekday=weekday,
        ).first()

        if working_hours is None:
            raise ValidationError({
                "start_time": (
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
        staff_member_id,
        start_time,
        end_time,
    ):
        has_conflict = StaffTimeOff.objects.filter(
            staff_member_id=staff_member_id,
            start_time__lt=end_time,
            end_time__gt=start_time,
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
        staff_member_id,
        start_time,
        end_time,
    ):
        conflicts = (
            AvailabilityService._get_blocking_reservations(
                staff_member_id=staff_member_id
            )
            .filter(
                start_time__lt=end_time,
                end_time__gt=start_time,
            )
        )

        if conflicts.exists():
            raise ValidationError({
                "start_time": (
                    "Time off cannot overlap a pending or confirmed booking."
                )
            })

    @staticmethod
    def validate_working_hours_change(
        *,
        staff_member_id,
        weekday,
        opening_time,
        closing_time,
    ):
        future_reservations = (
            AvailabilityService._get_blocking_reservations(
                staff_member_id=staff_member_id
            )
            .filter(end_time__gt=timezone.now())
        )

        for reservation in future_reservations:
            local_start = timezone.localtime(reservation.start_time)
            local_end = timezone.localtime(reservation.end_time)

            if local_start.weekday() != weekday:
                continue

            reservation_start = local_start.time().replace(tzinfo=None)
            reservation_end = local_end.time().replace(tzinfo=None)

            if reservation_start < opening_time:
                raise ValidationError({
                    "opening_time": (
                        "Opening time is too late for an existing reservation "
                        "on this day."
                    )
                })

            if reservation_end > closing_time:
                raise ValidationError({
                    "closing_time": (
                        "Closing time is too early for an existing reservation "
                        "on this day."
                    )
                })
