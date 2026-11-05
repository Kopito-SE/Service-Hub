from django.contrib.auth import get_user_model
from apps.notifications.services import NotificationService
from apps.notifications.models import Notification

User = get_user_model()

def _delivery_key(delivery_id):
    if delivery_id is None:
        return None
    return f"event-delivery-{delivery_id}"

def handle_booking_created(event, *, delivery_id=None):
    customer = User.objects.get(pk=event.customer_id)
    '''
    # TEMPORARY TEST: simulate notification delivery failure.
    if event.service_name.startswith("Haircut"):
        raise RuntimeError(
            "TEST FAILURE: Notification provider outage."
        )
    '''
    NotificationService.create_notification(
        recipient=customer,
        event_type=Notification.EventType.BOOKING_CREATED,
        subject="Booking received",
        message=(
            f"Your booking for {event.service_name} "
            "has been received successfully."
        ),
        idempotency_key=_delivery_key(delivery_id),
    )

def handle_booking_cancelled(event, *, delivery_id=None):
    customer = User.objects.get(pk=event.customer_id)

    NotificationService.create_notification(
        recipient=customer,
        event_type=Notification.EventType.BOOKING_CANCELLED,
        subject="Booking cancelled",
        message=(
            f"Your booking for {event.service_name} "
            "has been cancelled."
        ),
        idempotency_key=_delivery_key(delivery_id)
    )

def handle_payment_succeeded(event, *, delivery_id=None):
    customer = User.objects.get(pk=event.customer_id)

    NotificationService.create_notification(
        recipient=customer,
        event_type=Notification.EventType.PAYMENT_SUCCEEDED,
        subject="Payment successful",
        message=(
            f"Your payment of {event.amount} for booking "
            f"{event.booking_id} was successful."
        ),
        idempotency_key=_delivery_key(delivery_id)
    )

def handle_payment_failed(event, *, delivery_id=None):
    customer = User.objects.get(pk=event.customer_id)

    NotificationService.create_notification(
        recipient=customer,
        event_type=Notification.EventType.PAYMENT_FAILED,
        subject="Payment Unsuccessful",
        message=(
            f"Your payment of {event.amount} for booking "
            f"#{event.booking_id} was unsuccessful. "
            "Please check the payment status before trying again."
        ),
        idempotency_key=_delivery_key(delivery_id)
    )