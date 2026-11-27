from dataclasses import dataclass
from decimal import Decimal
from apps.bookings.services.booking_service import BookingService
from django.db import connection
from apps.bookings.models import Booking
from rest_framework.exceptions import ValidationError


class BookingInterfaceError(Exception):
    """Raised when a booking cannot be retrieved through the public interface"""
from django.db.models import Q

@dataclass(frozen=True)
class BookingDTO:
    id: int
    customer_id: int | None
    guest_customer_id: int | None
    business_id: int
    business_owner_id: int
    status: str
    price_at_booking: Decimal

def _to_dto(booking):
    return BookingDTO(
        id=booking.pk,
        customer_id=booking.customer_id,
        guest_customer_id=booking.guest_customer_id,
        business_id=booking.business_id,
        business_owner_id=booking.business.owner_id,
        status=booking.status,
        price_at_booking=booking.price_at_booking
    )

def create_booking(
        *,
        customer=None,
        guest_customer_id=None,
        business_id,
        service_id,
        start_time,
        staff_member_id=None,
        notes=""
):
    """
    Create a booking through the public Interface.
    Support registered and guest customers
    """
    try:
        booking = BookingService.create_booking(
            customer=customer,
            guest_customer_id=guest_customer_id,
            business_id=business_id,
            service_id=service_id,
            start_time=start_time,
            staff_member_id=staff_member_id,
            notes=notes
        )
    except ValidationError as exc:
        raise BookingInterfaceError(str(exc)) from exc

    return _to_dto(booking)


def get_booking(*, booking_id):
    try:
        booking = Booking.objects.select_related("business").get(
            pk=booking_id
        )

    except Booking.DoesNotExist:
        raise BookingInterfaceError(
            f"Booking #{booking_id} does not exist."
        )

    return _to_dto(booking)

def get_booking_for_update(*, booking_id):
    if not connection.in_atomic_block:
        raise BookingInterfaceError(
            "get_booking_for_update must be called inside transaction.atomic()."
        )

    try:
        booking = (
            Booking.objects
            .select_for_update()
            .select_related("business")
            .get(pk=booking_id)
        )

    except Booking.DoesNotExist:
        raise BookingInterfaceError(
            f"Booking {booking_id} does not exist."
        )

    return _to_dto(booking)
def get_accessible_booking_ids(*, user_id):
    """
    Return IDs of bookings accessible to a user
    A user can access booking where they are either Business owner ot the customer
    """
    return tuple( Booking.objects.filter(
        Q(business__owner_id=user_id) | Q(customer_id=user_id)
      ).values_list("id", flat=True)
    )

def confirm_booking(*, booking_id):
    """Confirm a booking through the public interface."""
    try:
        booking = BookingService.confirm_booking(
            booking_id=booking_id
        )

    except ValidationError as exc:
        raise BookingInterfaceError(str(exc)) from exc

    return _to_dto(booking)

def expire_pending_booking(*, booking_id):
    """
    Expire a pending booking through the public interface
    """
    try:
        booking = BookingService.expire_pending_booking(
            booking_id=booking_id
        )
    except ValidationError as exc:
        raise BookingInterfaceError(str(exc)) from exc

    return _to_dto(booking)


