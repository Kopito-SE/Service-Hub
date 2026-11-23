from dataclasses import dataclass
from decimal import Decimal

from django.db import connection
from apps.bookings.models import Booking

class BookingInterfaceError(Exception):
    """Raised when a booking cannot be retrieved through the public interface"""

@dataclass(frozen=True)
class BookingDTO:
    id: int
    customer_id: int
    business_id: int
    business_owner_id: int
    status: str
    price_at_booking: Decimal

def _to_dto(booking):
    return BookingDTO(
        id=booking.pk,
        customer_id=booking.customer_id,
        business_id=booking.business_id,
        business_owner_id=booking.business.owner_id,
        status=booking.status,
        price_at_booking=booking.price_at_booking
    )

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