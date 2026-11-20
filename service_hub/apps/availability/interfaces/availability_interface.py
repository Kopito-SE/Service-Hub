from dataclasses import dataclass
from datetime import datetime

from rest_framework.exceptions import ValidationError

from apps.availability.services.availability_service import AvailabilityService
from apps.availability.services.reservation_service import ReservationService
from apps.businesses.interfaces import (
    BusinessInterface,
    BusinessInterfaceError,
)


class AvailabilityInterfaceError(Exception):
    """Raised when an Availability component operation fails."""

    def __init__(self, detail):
        self.detail = detail
        super().__init__(str(detail))


@dataclass(frozen=True)
class ReservationDTO:
    booking_reference: int
    business_id: int
    staff_member_id: int | None
    start_time: datetime
    end_time: datetime
    status: str
    expires_at: datetime | None


class AvailabilityInterface:

    @staticmethod
    def _execute(operation):
        """Translate internal DRF validation errors into interface errors."""
        try:
            return operation()
        except ValidationError as exc:
            raise AvailabilityInterfaceError(exc.detail) from exc

    @staticmethod
    def _to_dto(reservation):
        return ReservationDTO(
            booking_reference=reservation.booking_reference,
            business_id=reservation.business_id,
            staff_member_id=reservation.staff_member_id,
            start_time=reservation.start_time,
            end_time=reservation.end_time,
            status=reservation.status,
            expires_at=reservation.expires_at,
        )

    @classmethod
    def validate_appointment(
        cls,
        *,
        business_id,
        staff_member_id,
        start_time,
        end_time,
    ):
        """Validate a staff member's working hours and time off."""

        def operation():
            try:
                BusinessInterface.get_active_staff_member(
                    staff_member_id=staff_member_id,
                    business_id=business_id
                )
            except BusinessInterfaceError as exc:
                raise ValidationError({
                    "staff_member": (
                        "Select an active staff member belonging "
                        "to this business."
                    )
                }) from exc

            AvailabilityService.validate_staff_availability(
                staff_member_id=staff_member_id,
                start_time=start_time,
                end_time=end_time
            )

            AvailabilityService.validate_no_time_off(
                staff_member_id=staff_member_id,
                start_time=start_time,
                end_time=end_time
            )

        return cls._execute(operation)

    @classmethod
    def reserve_slot(
        cls,
        *,
        business_id,
        staff_member_id,
        booking_reference,
        start_time,
        end_time,
        status="active",
        expires_at=None,
    ):
        reservation = cls._execute(
            lambda: ReservationService.reserve_slot(
                business_id=business_id,
                staff_member_id=staff_member_id,
                booking_reference=booking_reference,
                start_time=start_time,
                end_time=end_time,
                status=status,
                expires_at=expires_at,
            )
        )

        return cls._to_dto(reservation)

    @classmethod
    def confirm_reservation(cls, *, booking_reference):
        reservation = cls._execute(
            lambda: ReservationService.confirm_reservation(
                booking_reference=booking_reference
            )
        )

        return cls._to_dto(reservation)

    @classmethod
    def release_reservation(cls, *, booking_reference):
        reservation = cls._execute(
            lambda: ReservationService.release_reservation(
                booking_reference=booking_reference
            )
        )

        return cls._to_dto(reservation)
