from types import SimpleNamespace
from django.test import TestCase
from django.contrib.auth import get_user_model

from apps.notifications.models import Notification
from apps.notifications.handlers import handle_booking_created

User = get_user_model()

class NotificationIdempotencyTests(TestCase):
    def setUp(self):
        self.customer = User.objects.create_user(
            username="idempotency_customer",
            password="test_password"
        )
        self.event = SimpleNamespace(
            customer_id=self.customer.pk,
            service_name="Haircut"
        )

    def test_repeated_delivery_creates_only_one_notification(self):
        delivery_id = 100

        handle_booking_created(
            self.event,
            delivery_id=delivery_id
        )

        handle_booking_created(
            self.event,
            delivery_id=delivery_id
        )

        notification = Notification.objects.filter(
            recipient=self.customer,
            idempotency_key=f"event-delivery-{delivery_id}-in_app"
        )

        self.assertEqual(notification.count(), 1)

    def test_different_deliveries_create_separate_notifications(self):
        handle_booking_created(
            self.event,
            delivery_id=100
        )

        handle_booking_created(
            self.event,
            delivery_id=101
        )

        self.assertEqual(
            Notification.objects.filter(
                recipient=self.customer
            ).count(),
            2,
        )

    def test_notification_without_delivery_id_has_no_idempotency_key(self):
        handle_booking_created(
            self.event,
        )

        notification = Notification.objects.get(
            recipient=self.customer
        )

        self.assertIsNone(notification.idempotency_key)
