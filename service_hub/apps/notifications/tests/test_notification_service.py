
from django.contrib.auth import get_user_model
from django.test import TestCase



from apps.notifications.models import Notification
from apps.notifications.services import NotificationService


User = get_user_model()


class NotificationServiceTests(TestCase):

    def setUp(self):
        self.user = User.objects.create_user(
            username="notification_test_user",
            email="test@example.com",
            password="TestPassword123!",
        )

    def test_create_in_app_notification(self):
        notification = NotificationService.create_notification(
            recipient=self.user,
            event_type=Notification.EventType.BOOKING_CREATED,
            subject="Booking received",
            message="Your booking has been received.",
        )

        self.assertEqual(notification.recipient, self.user)
        self.assertEqual(
            notification.channel,
            Notification.Channel.IN_APP,
        )
        self.assertEqual(
            notification.status,
            Notification.Status.SENT,
        )
        self.assertIsNotNone(notification.sent_at)
        self.assertIsNone(notification.read_at)

    def test_create_email_notification_starts_pending(self):
        notification = NotificationService.create_notification(
            recipient=self.user,
            event_type=Notification.EventType.PAYMENT_SUCCEEDED,
            subject="Payment received",
            message="Your payment was successful.",
            channel=Notification.Channel.EMAIL,
        )

        self.assertEqual(
            notification.status,
            Notification.Status.PENDING,
        )
        self.assertIsNone(notification.sent_at)

    def test_invalid_channel_raises_error(self):
        with self.assertRaises(ValueError):
            NotificationService.create_notification(
                recipient=self.user,
                event_type=Notification.EventType.BOOKING_CREATED,
                subject="Test",
                message="Test message",
                channel="sms",
            )

    def test_invalid_event_type_raises_error(self):
        with self.assertRaises(ValueError):
            NotificationService.create_notification(
                recipient=self.user,
                event_type="unknown_event",
                subject="Test",
                message="Test message",
            )
