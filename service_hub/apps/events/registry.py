from apps.events.dispatcher import subscribe
from apps.events.events import (
    BookingCreated,
    BookingCancelled,
    PaymentSucceeded,
    PaymentFailed
)

from apps.notifications.handlers import (
    handle_booking_created,
    handle_booking_cancelled,
    handle_payment_succeeded,
    handle_payment_failed
)

def register_handlers():
    # Booking Events
    subscribe(BookingCreated, handle_booking_created)
    subscribe(BookingCancelled, handle_booking_cancelled)

    # Payment Events
    subscribe(PaymentSucceeded, handle_payment_succeeded)
    subscribe(PaymentFailed, handle_payment_failed)

register_handlers()
