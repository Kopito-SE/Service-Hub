from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from apps.events.models import (EventDelivery, EventDeliveryRetry, EventOutbox)

User = get_user_model()

class ManualRetryAPITests(APITestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            username="retry_admin",
            password="test_123",
            is_staff=True,
            is_active=True
        )

        self.customer = User.objects.create_user(
            username="retry_customer",
            password="test-password",
            is_staff=False,
            is_active=True
        )

        self.event = EventOutbox.objects.create(
            event_type="apps.events.events.BookingCreated",
            payload={
                "booking_id": 10,
                "customer_id": 5,
                "service_name": "Haircut",
            },
            status=EventOutbox.Status.DEAD
        )

        self.delivery = EventDelivery.objects.create(
            event=self.event,
            handler_key="apps.notifications.handlers.handle_booking_created",
            status=EventDelivery.Status.DEAD,
            attempts=5,
            max_attempts=5,
            last_error="Notification service unavailable.",
            alerted_at=timezone.now()
        )

        self.url = (
            f"/api/events/deliveries/{self.delivery.pk}/retry/"
        )
    def test_admin_can_retry_dead_delivery(self):
        self.client.force_authenticate(user=self.admin)

        response = self.client.post(
            self.url,
            {"reason": "Notification provider has been restored."},
            format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)
        self.delivery.refresh_from_db()
        self.assertEqual(self.delivery.status, EventDelivery.Status.PENDING)
        self.assertEqual(self.delivery.attempts, 0)
        self.assertEqual(self.delivery.manual_retry_count, 1)
        self.assertEqual(EventDeliveryRetry.objects.count(), 1)

    def test_unauthenticated_user_cannot_retry(self):
        response = self.client.post(
            self.url,
            {"reason": "Testing Unauthenticated User."},
            format="json"
        )
        self.assertIn(
            response.status_code,
            (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN)
        )

    def test_non_admin_cannot_retry(self):
        self.client.force_authenticate(user=self.customer)

        response = self.client.post(
            self.url,
            {"reason": "Trying as a customer."},
            format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_succeeded_delivery_returns_conflict(self):
        self.client.force_authenticate(user=self.admin)
        self.delivery.status = EventDelivery.Status.SUCCEEDED
        self.delivery.save(update_fields=["status"])

        response = self.client.post(
            self.url,
            {"reason": "Retrying a successful delivery"},
            format="json"
        )

        self.assertEqual(response.status_code,status.HTTP_409_CONFLICT)
        self.assertEqual(EventDeliveryRetry.objects.count(), 0)

    def test_blank_reason_is_rejected(self):
        self.client.force_authenticate(user=self.admin)

        response = self.client.post(
            self.url,
            {"reason": "  "},
            format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(EventDeliveryRetry.objects.count(), 0)

class RetryHistoryAPITests(APITestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            username="history_admin",
            password="test_123",
            is_staff=True,
            is_active=True
        )

        self.customer = User.objects.create_user(
            username="History_customer",
            password="test_password",
            is_staff=False,
            is_active=True
        )

        self.event = EventOutbox.objects.create(
            event_type="apps.events.events.BookingCreated",
            payload={
                "booking_id": 20,
                "customer_id": 1,
                "service_name": "Haircut"
            },
            status=EventOutbox.Status.PROCESSING,
        )

        self.delivery = EventDelivery.objects.create(
            event=self.event,
            handler_key=(
                "apps.notifications.handlers.handle_booking_created"
            ),
            status=EventDelivery.Status.PENDING,
            attempts=0,
            max_attempts=5
        )
        self.url = (
            f"/api/events/deliveries/{self.delivery.pk}/retries/"
        )
    def test_admin_can_view_retry_history(self):
        self.client.force_authenticate(user=self.admin)

        retry = EventDeliveryRetry.objects.create(
            delivery=self.delivery,
            requested_by=self.admin,
            retry_number=1,
            previous_attempts=5,
            previous_error="Notification service unavailable.",
            reason="Notification provider has been restored."
        )

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)

        self.assertEqual(response.data[0]["id"], retry.pk)
        self.assertEqual(
            response.data[0]["requested_by"],
            self.admin.pk
        )
        self.assertEqual(response.data[0]["retry_number"], 1)
        self.assertEqual(response.data[0]["previous_attempts"], 5)

    def test_empty_retry_history_returns_empty_list(self):
        self.client.force_authenticate(user=self.admin)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data, [])

    def test_nonexistent_delivery_returns_404(self):
        self.client.force_authenticate(user=self.admin)

        response = self.client.get(
            "/api/events/deliveries/6746246/retries/"
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_404_NOT_FOUND
        )

    def test_unauthenticated_user_cannot_view_history(self):
        response = self.client.get(self.url)

        self.assertIn(
            response.status_code,
            (
                status.HTTP_401_UNAUTHORIZED,
                status.HTTP_403_FORBIDDEN
            ),
        )
    def test_non_admin_cannot_view_history(self):
        self.client.force_authenticate(user=self.customer)

        response = self.client.get(self.url)

        self.assertEqual(
            response.status_code,
            status.HTTP_403_FORBIDDEN
        )