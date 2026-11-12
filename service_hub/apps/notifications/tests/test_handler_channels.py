from types import SimpleNamespace
from django.test import TestCase
from decimal import Decimal
from django.contrib.auth import get_user_model
from apps.notifications.models import EmailDelivery, Notification
from apps.notifications.handlers import (
    handle_booking_created,
    handle_booking_cancelled,
    handle_payment_succeeded,
    handle_payment_failed
)
User = get_user_model()

class NotificationHandlerChannelTest(TestCase):
    def setUp(self):
        self.customer = User.objects.create_user(
            username="handler_customer",
            email="handler@example.com",
            password="test_password"
        )
        self.booking_event = SimpleNamespace(
            customer_id=self.customer.pk,
            service_name="Hair Dressing",
        )
        self.payment_event = SimpleNamespace(
            customer_id=self.customer.pk,
            booking_id=101,
            amount=Decimal("1500.00")
        )

    def assert_both_channels_created(self, event_type):
        notifications = Notification.objects.filter(
            recipient=self.customer,
            event_type=event_type
        )

        self.assertEqual(notifications.count(), 2)
        self.assertEqual(
            notifications.filter(
                channel=Notification.Channel.IN_APP
            ).count(),
            1
        )
        self.assertEqual(
            notifications.filter(
                channel=Notification.Channel.EMAIL
            ).count(),
            1
        )
        email_notification = notifications.get(
            channel=Notification.Channel.EMAIL
        )

        self.assertEqual(
            EmailDelivery.objects.filter(
                notification=email_notification
            ).count(),
            1
        )

    def test_booking_created_creates_both_channels(self):
        handle_booking_created(
            self.booking_event,
            delivery_id=101
        )
        self.assert_both_channels_created(
            Notification.EventType.BOOKING_CREATED
        )

    def test_booking_cancelled_creates_both_channels(self):
        handle_booking_cancelled(
            self.booking_event,
            delivery_id=102
        )
        self.assert_both_channels_created(
            Notification.EventType.BOOKING_CANCELLED
        )
    def payment_succeeded_creates_both_channels(self):
        handle_payment_succeeded(
            self.payment_event,
            delivery_id=103
        )

        self.assert_both_channels_created(
            Notification.EventType.PAYMENT_SUCCEEDED
        )

    def test_payment_failed_creates_both_channels(self):
        handle_payment_failed(
            self.payment_event,
            delivery_id=104
        )

        self.assert_both_channels_created(
            Notification.EventType.PAYMENT_FAILED
        )

    def test_customer_without_email_gets_only_in_app(self):
        self.customer.email = ""
        self.customer.save(update_fields=["email"])

        handle_booking_created(
            self.booking_event,
            delivery_id=105
        )
        notifications = Notification.objects.filter(
            recipient=self.customer
        )

        self.assertEqual(notifications.count(), 1)

        self.assertEqual(
            notifications.first().channel,
            Notification.Channel.IN_APP
        )
        self.assertEqual(EmailDelivery.objects.count(), 0)

    def test_repeated_event_does_not_create_duplicates(self):
        handle_booking_created(
            self.booking_event,
            delivery_id=106
        )

        handle_booking_created(
            self.booking_event,
            delivery_id=106
        )

        self.assertEqual(
            Notification.objects.filter(
                recipient=self.customer,
                event_type=Notification.EventType.BOOKING_CREATED
            ).count(),
            2
        )

        self.assertEqual(EmailDelivery.objects.count(), 1)