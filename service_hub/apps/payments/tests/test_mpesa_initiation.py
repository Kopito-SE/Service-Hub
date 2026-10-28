from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from apps.bookings.models import Booking
from apps.businesses.models import Business
from apps.payments.models import Payment
from apps.service_catalog.models import Service


User = get_user_model()


class MpesaInitiationAPITests(APITestCase):
    def setUp(self):
        self.owner = User.objects.create_user(username="mpesa_business_owner")
        self.customer = User.objects.create_user(username="mpesa_customer")
        self.other_customer = User.objects.create_user(
            username="mpesa_other_customer"
        )

        self.business = Business.objects.create(
            owner=self.owner,
            name="M-Pesa Test Business",
        )

        self.service = Service.objects.create(
            business=self.business,
            name="Consultation",
            price=Decimal("500.00"),
            duration_minutes=60,
        )

        start_time = timezone.now() + timedelta(days=1)
        self.booking = Booking.objects.create(
            customer=self.customer,
            business=self.business,
            service=self.service,
            start_time=start_time,
            end_time=start_time + timedelta(hours=1),
            price_at_booking=Decimal("500.00"),
        )

    @patch("apps.payments.services.MpesaClient.initiate_stk_push")
    def test_customer_can_initiate_mpesa_for_own_booking(self, initiate_stk):
        initiate_stk.return_value = {
            "CheckoutRequestID": "ws_CO_test_123",
            "MerchantRequestID": "merchant_test_123",
            "ResponseCode": "0",
            "ResponseDescription": "Success",
        }
        self.client.force_authenticate(user=self.customer)

        response = self.client.post(
            reverse("payment-initiate-mpesa"),
            {
                "booking": self.booking.pk,
                "amount": "500.00",
                "phone_number": "0712345678",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        payment = Payment.objects.get(pk=response.data["id"])
        self.assertEqual(payment.booking, self.booking)
        self.assertEqual(payment.recorded_by, self.customer)
        initiate_stk.assert_called_once()

    @patch("apps.payments.services.MpesaClient.initiate_stk_push")
    def test_other_customer_cannot_initiate_mpesa_for_booking(
        self, initiate_stk
    ):
        self.client.force_authenticate(user=self.other_customer)

        response = self.client.post(
            reverse("payment-initiate-mpesa"),
            {
                "booking": self.booking.pk,
                "amount": "500.00",
                "phone_number": "0712345678",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(Payment.objects.count(), 0)
        initiate_stk.assert_not_called()
