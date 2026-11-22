from decimal import Decimal
from datetime import timedelta
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from apps.businesses.models import Business
from apps.service_catalog.models import Service
from apps.bookings.models import Booking
from apps.payments.models import Payment

User = get_user_model()

class PaymentAPITests(APITestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            username="api_owner",
            password="pw"
        )

        self.other_owner = User.objects.create_user(
            username="api_other",
            password="pw"
        )

        self.customer = User.objects.create_user(
            username="api_customer",
            password="pw"
        )

        self.business = Business.objects.create(
            owner=self.owner,
            name="API Business"
        )

        self.service = Service.objects.create(
            business=self.business,
            name="Consultation",
            price=Decimal("2000.00"),
            duration_minutes=60
        )

        start_time = timezone.now() + timedelta(days=7)
        self.booking = Booking.objects.create(
            customer=self.customer,
            business=self.business,
            service=self.service,
            start_time=start_time,
            end_time=start_time + timedelta(hours=1),
            price_at_booking=Decimal("2000.00"),
            status=Booking.Status.PENDING
        )

        # Helper to create a payment for testing
        self.payment = Payment.objects.create(
            booking=self.booking,
            amount=Decimal("500.00"),
            method=Payment.Method.CASH,
            status=Payment.Status.SUCCEEDED, # Let's make it successful to test summaries
            recorded_by=self.owner,
        )

        self.client.force_authenticate(user=self.owner)

    def create_payment(self, method="cash", amount="500.00"):
        return self.client.post(
            reverse("payment-list"),
            {
                "booking": self.booking.pk,
                "amount": amount,
                "currency": "KES",
                "method": method
            },
            format="json"
        )

    # 1.
    def test_owner_can_create_pending_payment(self):
        response = self.create_payment()

        self.assertEqual(
            response.status_code,
            status.HTTP_201_CREATED
        )
        self.assertEqual(response.data["status"], Payment.Status.PENDING)

    # 2.
    def test_owner_can_list_own_payment(self):
        self.create_payment()
        response = self.client.get(reverse("payment-list"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 2)

    # 3.
    def test_owner_cannot_create_payment_for_another_business(self):
        other_business = Business.objects.create(
            owner=self.other_owner,
            name="Another Business"
        )

        other_service = Service.objects.create(
            business=other_business,
            name="Other Service",
            price=Decimal("500.00"),
            duration_minutes=30
        )

        start_time = timezone.now() + timedelta(days=8)
        other_booking = Booking.objects.create(
            customer=self.customer,
            business=other_business,
            service=other_service,
            start_time=start_time,
            end_time=start_time + timedelta(minutes=30),
            price_at_booking=Decimal("500.00"),
            status=Booking.Status.PENDING
        )

        response = self.client.post(
            reverse("payment-list"),
            {
                "booking": other_booking.pk,
                "amount": "100.00",
                "method": "cash",
                "currency": "KES"
            },
            format="json"
        )
        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST
        )
    # 4.
    def test_owner_cannot_manually_mark_mpesa_payment_succeeded(self):
        response = self.create_payment(method="mpesa")

        self.assertEqual(
            response.status_code,
            status.HTTP_201_CREATED,
        )

        status_response = self.client.post(
            reverse(
                "payment-set-status",
                args=[response.data["id"]],
            ),
            {"status": "succeeded"},
            format="json"
        )

        self.assertIn(
            status_response.status_code,
            (status.HTTP_400_BAD_REQUEST, status.HTTP_403_FORBIDDEN)
        )
    # 5.
    def test_other_owner_cannot_retrieve_payment(self):
        response = self.create_payment()
        payment_id = response.data["id"]

        self.client.force_authenticate(user=self.other_owner)

        detail_response = self.client.get(
            reverse("payment-detail", args=[payment_id])
        )

        self.assertEqual(
            detail_response.status_code,
            status.HTTP_404_NOT_FOUND
        )
    # 6.
    def test_customer_can_view_own_booking_summary(self):
        """Catches: The bug where only business owners could view summaries."""

        self.client.force_authenticate(user=self.customer)
        response = self.client.get(
            reverse("payment-booking-summary"),
            {"booking_id": self.booking.pk}
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(float(response.data["net_paid"]), 500.00)
        self.assertEqual(float(response.data["outstanding_balance"]), 1500.00)
    # 7.
    def test_customer_can_list_own_payments(self):
        self.client.force_authenticate(user=self.customer)
        response = self.client.get(reverse("payment-list"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)

