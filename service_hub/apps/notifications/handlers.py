from django.contrib.auth import get_user_model

from apps.notifications.services import NotificationService
from apps.notifications.models import Notification

from apps.customers.interfaces import (
    CustomerInterface,
    CustomerInterfaceError
)

User = get_user_model()


def _delivery_key(delivery_id, channel):
    if delivery_id is None:
        return None

    return f"event-delivery-{delivery_id}-{channel}"

def _resolve_customer(event):
    """
    Resolve the event recipient.

    Returns:
        (Registered_user, guest_customer)

    Exactly one recipient should be present
    """
    customer_id = getattr(event, "customer_id", None)
    guest_customer_id = getattr(event, "guest_customer_id", None)

    if customer_id is not None and guest_customer_id is not None:
        raise ValueError(
            "Event cannot contain both customer_id "
            "and guest_customer_id."
        )
    if customer_id is not None:
        return User.objects.get(pk=customer_id), None

    if guest_customer_id is not None:
        guest_customer = CustomerInterface.get_customer(
            customer_id=guest_customer_id
        )
        return None, guest_customer

    raise ValueError(
        "Event must contain customer_id or guest_customer_id."
    )

def _notify_customer(
    *,
    customer=None,
    guest_customer=None,
    event_type=None,
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

    if customer is not None:
        # Registered customer : in-app notification
        NotificationService.create_notification(
            recipient=customer,
            event_type=event_type,
            subject=subject,
            message=message,
            channel=Notification.Channel.IN_APP,
            severity=severity,
            idempotency_key=_delivery_key(
                delivery_id,
                Notification.Channel.IN_APP
            ),
        )
        email = customer.email
    elif guest_customer is not None:
        # Guest customer: email only.
        email = guest_customer.email

    else:
        raise ValueError(
            "A registered or guest customer is required."
        )

    if email:
        NotificationService.create_notification(
            recipient=customer,
            recipient_email=email,
            event_type=event_type,
            subject=subject,
            message=message,
            channel=Notification.Channel.EMAIL,
            severity=severity,
            idempotency_key=_delivery_key(
                delivery_id,
                Notification.Channel.EMAIL
            ),
        )

def handle_booking_created(event, *, delivery_id=None):
    customer, guest_customer = _resolve_customer(event)

    _notify_customer(
        customer=customer,
        guest_customer=guest_customer,
        event_type=Notification.EventType.BOOKING_CREATED,
        subject="Booking received",
        message=(
            f"Your booking for {event.service_name} "
            "has been received successfully."
        ),
        delivery_id=delivery_id,
    )


def handle_booking_cancelled(event, *, delivery_id=None):
    customer, guest_customer = _resolve_customer(event)

    _notify_customer(
        customer=customer,
        guest_customer=guest_customer,
        event_type=Notification.EventType.BOOKING_CANCELLED,
        subject="Booking cancelled",
        message=(
            f"Your booking for {event.service_name} "
            "has been cancelled."
        ),
        delivery_id=delivery_id,
    )

def handle_booking_confirmed(event, *, delivery_id=None):
    customer, guest_customer = _resolve_customer(event)

    _notify_customer(
        customer=customer,
        guest_customer=guest_customer,
        event_type=Notification.EventType.BOOKING_CONFIRMED,
        subject="Booking Confirmed",
        message=(
            f"Your booking for {event.service_name} "
            "has been confirmed"
        ),
        delivery_id=delivery_id
    )

def handle_payment_succeeded(event, *, delivery_id=None):
    customer, guest_customer = _resolve_customer(event)

    _notify_customer(
        customer=customer,
        guest_customer=guest_customer,
        event_type=Notification.EventType.PAYMENT_SUCCEEDED,
        subject="Payment successful",
        message=(
            f"Your payment of {event.amount} for booking "
            f"#{event.booking_id} was successful."
        ),
        delivery_id=delivery_id,
    )


def handle_payment_failed(event, *, delivery_id=None):
    customer, guest_customer = _resolve_customer(event)

    _notify_customer(
        customer=customer,
        guest_customer=guest_customer,
        event_type=Notification.EventType.PAYMENT_FAILED,
        subject="Payment unsuccessful",
        message=(
            f"Your payment of {event.amount} for booking "
            f"#{event.booking_id} was unsuccessful. "
            "Please check the payment status before trying again."
        ),
        delivery_id=delivery_id,
    )
