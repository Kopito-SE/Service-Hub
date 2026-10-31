from decimal import Decimal

from apps.events.events import (
    BookingCreated,
    BookingCancelled,
    PaymentSucceeded,
    PaymentFailed
)

EVENT_TYPES = {
    "apps.events.events.BookingCreated": BookingCreated,
    "apps.events.events.BookingCancelled": BookingCancelled,
    "apps.events.events.PaymentSucceeded": PaymentSucceeded,
    "apps.events.events.PaymentFailed": PaymentFailed,
}

def reconstruct_event(event_type, payload):
    """
    Reconstruct an event from its stored type and JSON payload.

    Only explicitly registered event classes can be reconstructed.
    """
    event_class = EVENT_TYPES.get(event_type)

    if event_class is None:
        raise ValueError(
            f"Unsupported event type: {event_type}"
        )
    event_data = payload.copy()

    if event_class in (PaymentSucceeded, PaymentFailed):
        event_data["amount"] = Decimal(event_data["amount"])

    return event_class(**event_data)