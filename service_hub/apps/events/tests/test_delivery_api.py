from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APITestCase

from apps.events.models import EventDelivery, EventOutbox

from apps.events.dispatcher import handler_key

User = get_user_model()

class EventDeliveryAPITests(APITestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            username="delivery_admin",
            password="test-password",
            is_staff=True,
            is_active=True
        )

        self.customer = User.objects.create_user(
            username="delivery_customer",
            password="test_password",
            is_staff=False,
            is_active=True
        )

        self.event = EventOutbox.objects.create(
            event_type="apps.events.events.BookingCreated",
            payload={
                "booking_id": 10,
                "customer_id": 5,
                "service_name": "Haircut"
            },
        )

        self.delivery = EventDelivery.objects.create(
            event=self.event,
            handler_key="apps.notifications.handlers.handle_booking_created",
            status=EventDelivery.Status.FAILED,
            attempts=2,
            max_attempts=5,
            last_error="Notification service unavailable."
        )

        self.list_url = "/api/events/deliveries/"
        self.detail_url = f"/api/events/deliveries/{self.delivery.pk}/"

    def test_unauthenticated_user_cannot_list_deliveries(self):
        response = self.client.get(self.list_url)
        self.assertIn(
            response.status_code,
            (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN)
        )

    def test_regular_user_cannot_list_deliveries(self):
        self.client.force_authenticate(user=self.customer)

        response = self.client.get(self.list_url)

        self.assertIn(
            response.status_code,
            (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN)
        )
    def test_admin_can_list_deliveries(self):
        self.client.force_authenticate(user=self.admin)

        response = self.client.get(self.detail_url)

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK
        )

    def test_admin_can_retrieve_delivery_details(self):
        self.client.force_authenticate(user=self.admin)

        response = self.client.get(self.detail_url)

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK
        )
        self.assertEqual(
            response.data["status"],
            EventDelivery.Status.FAILED,
        )
        self.assertEqual(
            response.data["attempts"],
            2,
        )
        self.assertEqual(
            response.data["event_type"],
            "apps.events.events.BookingCreated"
        )
    def test_admin_can_filter_failed_deliveries(self):
        self.client.force_authenticate(user=self.admin)

        response = self.client.get(
            self.list_url,
            {"status": "failed"},
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK
        )