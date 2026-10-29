from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework.reverse import reverse
from django.utils import timezone
from apps.notifications.models import Notification

class NotificationAPITests(APITestCase):

    def setUp(self):
        User = get_user_model()

        self.user = User.objects.create_user(
            username="customer_one",
            email="customer@example.com",
            password="TestPassword5362"
        )

        self.other_user = User.objects.create_user(
            username="customer_two",
            email="customer2@example.com",
            password="TestPassword123!",
        )
        self.notification = Notification.objects.create(
            recipient=self.user,
            channel=Notification.Channel.IN_APP,
            event_type=Notification.EventType.BOOKING_CREATED,
            subject="Booking received",
            message="Your booking has been received",
            status=Notification.Status.SENT,
            sent_at=timezone.now()
        )

        self.other_notification = Notification.objects.create(
            recipient=self.other_user,
            channel=Notification.Channel.IN_APP,
            event_type=Notification.EventType.BOOKING_CREATED,
            subject="Private booking",
            message="This belongs to another customer.",
            status=Notification.Status.SENT,
            sent_at=timezone.now()
        )

        self.list_url = reverse("notification-list")
        self.detail_url = reverse(
            "notification-detail",
            kwargs={"pk": self.notification.pk}
        )
        self.read_url = reverse(
            "notification-mark-as-read",
            kwargs={"pk": self.notification.pk}
        )

        self.client.force_authenticate(user=self.user)
    def test_user_can_list_own_notifications(self):
        response = self.client.get(self.list_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(
            response.data[0]["id"],
            self.notification.id
        )

    def test_user_cannot_view_another_users_notification(self):
        url = reverse(
            "notification-detail",
            kwargs={"pk": self.other_notification.pk}
        )
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_user_can_mark_own_notification_as_read(self):
        response = self.client.post(self.read_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["is_read"])
        self.assertIsNotNone(response.data["read_at"])

        self.notification.refresh_from_db()
        self.assertIsNotNone(self.notification.read_at)

    def test_user_cannot_mark_another_users_notification_as_read(self):
        url = reverse(
            "notification-mark-as-read",
            kwargs={"pk": self.other_notification.pk},
        )

        response = self.client.post(url)

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

        self.other_notification.refresh_from_db()
        self.assertIsNone(self.other_notification.read_at)

    def test_unauthenticated_user_cannot_list_notifications(self):
        self.client.force_authenticate(user=None)

        response = self.client.get(self.list_url)

        self.assertIn(
            response.status_code,
            (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN)
        )


