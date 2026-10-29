from apps.events.dispatcher import subscribe
from apps.events.events import BookingCreated, BookingCancelled

from apps.notifications.handlers import handle_booking_created, handle_booking_cancelled

def register_handlers():
    subscribe(BookingCreated, handle_booking_created)
    subscribe(BookingCancelled, handle_booking_cancelled)

register_handlers()
