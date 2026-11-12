
from django.contrib.auth import get_user_model

from apps.notifications.services import NotificationService
from apps.notifications.models import Notification

User = get_user_model()


def _delivery_key(delivery_id, channel):
    if delivery_id is None:
        return None

    return f"event-delivery-{delivery_id}-{channel}"


def _notify_customer(
    customer,
    event_type,
    subject,
    message,
    delivery_id=None,
    severity=Notification.Severity.INFO,
):
    """
    Create the appropriate customer notification channels.

    In-app is always available.
    Email is requested only when the customer has an email address.
    :param customer: The User instance receiving the notification.
    :type customer: User
    :param event_type: The type of event triggering the notification.
    :type event_type: str
    :param subject: The notification subject line.
    :type subject: str
    :param message: The body of the notification.
    :type message:str
    """

    channels = [Notification.Channel.IN_APP]

    if customer.email:
        channels.append(Notification.Channel.EMAIL)

    for channel in channels:
        NotificationService.create_notification(
            recipient=customer,
            event_type=event_type,
            subject=subject,
            message=message,
            channel=channel,
            severity=severity,
            idempotency_key=_delivery_key(
                delivery_id,
                channel,
            ),
        )


def handle_booking_created(event, *, delivery_id=None):
    customer = User.objects.get(pk=event.customer_id)

    _notify_customer(
        customer=customer,
        event_type=Notification.EventType.BOOKING_CREATED,
        subject="Booking received",
        message=(
            f"Your booking for {event.service_name} "
            "has been received successfully."
        ),
        delivery_id=delivery_id,
    )


def handle_booking_cancelled(event, *, delivery_id=None):
    customer = User.objects.get(pk=event.customer_id)

    _notify_customer(
        customer=customer,
        event_type=Notification.EventType.BOOKING_CANCELLED,
        subject="Booking cancelled",
        message=(
            f"Your booking for {event.service_name} "
            "has been cancelled."
        ),
        delivery_id=delivery_id,
    )


def handle_payment_succeeded(event, *, delivery_id=None):
    customer = User.objects.get(pk=event.customer_id)

    _notify_customer(
        customer=customer,
        event_type=Notification.EventType.PAYMENT_SUCCEEDED,
        subject="Payment successful",
        message=(
            f"Your payment of {event.amount} for booking "
            f"#{event.booking_id} was successful."
        ),
        delivery_id=delivery_id,
    )


def handle_payment_failed(event, *, delivery_id=None):
    customer = User.objects.get(pk=event.customer_id)

    _notify_customer(
        customer=customer,
        event_type=Notification.EventType.PAYMENT_FAILED,
        subject="Payment unsuccessful",
        message=(
            f"Your payment of {event.amount} for booking "
            f"#{event.booking_id} was unsuccessful. "
            "Please check the payment status before trying again."
        ),
        delivery_id=delivery_id,
    )
