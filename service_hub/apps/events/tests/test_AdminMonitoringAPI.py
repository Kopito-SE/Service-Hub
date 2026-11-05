from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APITestCase
from apps.events.models import EventDelivery, EventOutbox

from apps.events.dispatcher import handler_key

User = get_user_model()

class OutboxMonitoringAPITests(APITestCase):
    def setUp(self):
        self.url = "/api/events/monitoring/"

        self.admin = User.objects.create_user(
            username="Platform_admin",
            password="test-password",
            is_staff=True,
            is_active=True,
        )

        self.customer = User.objects.create_user(
            username="customer",
            password="test-pass",
            is_staff=False,
            is_active=True
        )

        self.event = EventOutbox.objects.create(
            event_type="apps.events.events.BookingCreated",
            payload={
                "booking_id": 1,
                "customer_id": 1,
                "service_name": "Haircut"
            },
        )

        EventDelivery.objects.create(
            event=self.event,
            handler_key="test.handler",
            status=EventDelivery.Status.PENDING
        )

    def test_unauthenticated_user_cannot_access_monitoring(self):
        response = self.client.get(self.url)

        self.assertIn(
            response.status_code,
            (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN)
        )

    def test_regular_customer_cannot_access_monitoring(self):
        self.client.force_authenticate(user=self.customer)

        response = self.client.get(self.url)

        self.assertIn(
            response.status_code,
            (status.HTTP_403_FORBIDDEN, status.HTTP_401_UNAUTHORIZED)
        )
    def test_platform_admin_can_access_monitoring(self):
        self.client.force_authenticate(user=self.admin)

        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        self.assertIn("events", response.data)
        self.assertIn("deliveries", response.data)
        self.assertIn("stale_deliveries", response.data)
        self.assertIn("unalerted_dead_deliveries", response.data)



