from rest_framework import status
from rest_framework.test import APITestCase
from django.urls import reverse

class PaymentAPITests(APITestCase):
    def setup(self):
        self.owner = User.objects.create_user(
            username="api_business_owner",
            password="test-password-123"
        )

        self.other_owner = User.objects.create_user(
            username="api_other_owner",
            password="test-password-123"
        )

        self.customer = User.objects.create_user(
            username="api_customer",
            password="test-password-145"
        )

        self.business = Business.objects.create(
            owner=self.owner,
            name=" Test API Business"
        )

        self.service = Service.objects.create(
            business=self.business,
            name="Consultation",
            price=Decimal("2000"),
            duration_minutes=60
        )

        start_time = timezone.now() + timedelta(days=7)
        self.booking = Booking.objects.create(
            customer=self.customer,
            business=self.business,
            service=self.service,
            start_time=start_time,
            end_time=start_time + timedelta(hours=1),
            price_at_booking=Decimal("2000"),
            status=Booking.Status.PENDING
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

def test_owner_can_create_pending_payment(self):
    response = self.create_payment()

    self.assertEqual(
        response.status_code,
        status.HTTP_201_CREATED
    )
    self.assertEqual(response.data["status"], Payment.Status.PENDING)

def test_owner_can_list_own_payment(self):
    self.create_payment()
    response = self.client.get(reverse("payment-list"))

    self.assertEqual(response.status_code, status.HTTP_200_OK)
    self.assertEqual(len(response.data), 1)

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

    self.assertEqual(
        status_response.status_code,
        status.HTTP_400_BAD_REQUEST
    )

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