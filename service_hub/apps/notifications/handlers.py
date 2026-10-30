from django.contrib.auth import get_user_model
from apps.notifications.services import NotificationService
from apps.notifications.models import Notification

User = get_user_model()

def handle_booking_created(event):
    customer = User.objects.get(pk=event.customer_id)

    NotificationService.create_notification(
        recipient=customer,
        event_type=Notification.EventType.BOOKING_CREATED,
        subject="Booking received",
        message=(
            f"Your booking for {event.service_name} "
            "has been received successfully"
        ),
    )

def handle_booking_cancelled(event):
    customer = User.objects.get(pk=event.customer_id)

    NotificationService.create_notification(
        recipient=customer,
        event_type=Notification.EventType.BOOKING_CANCELLED,
        subject="Booking cancelled",
        message=(
            f"Your booking for {event.service_name} "
            "has been cancelled."
        ),
    )

def handle_payment_succeeded(event):
    customer = User.objects.get(pk=event.customer_id)

    NotificationService.create_notification(
        recipient=customer,
        event_type=Notification.EventType.PAYMENT_SUCCEEDED,
        subject="Payment successful",
        message=(
            f"Your payment of {event.amount} for booking "
            f"{event.booking_id} was successful."
        ),
    )

def handle_payment_failed(event):
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
    )