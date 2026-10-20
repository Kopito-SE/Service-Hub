from datetime import timedelta

from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from apps.businesses.models import Business, StaffMember
from apps.service_catalog.models import Service
from apps.bookings.models import Booking
from decimal import Decimal

from apps.availability.models import StaffWorkingHours

User=get_user_model()

class BookingAPITests(APITestCase):
    def setUp(self):
        self.customer = User.objects.create_user(
            username="customer_api",
            password="TestPassword987",
        )

        self.other_customer = User.objects.create_user(
            username="other_customer",
            password="TestPassword567"
        )

        self.business = Business.objects.create(
            owner=self.customer,
            name="Salon Shop",
            is_active=True
        )

        self.service = Service.objects.create(
            business=self.business,
            name="Hair Drying and Straightening",
            price=Decimal("450.00"),
            duration_minutes=60,
            is_active=True
        )

        self.staff_member = StaffMember.objects.create(
            business=self.business,
            display_name="Marcus",
            is_active=True
        )

        for weekday in range(7):
            StaffWorkingHours.objects.create(
                staff_member=self.staff_member,
                weekday=weekday,
                opening_time="00:00",
                closing_time="23:59"
            )

        self.client.force_authenticate(user=self.customer)

    def create_booking(self):
        return Booking.objects.create(

            customer=self.customer,
            business=self.business,
            service=self.service,
            staff_member=self.staff_member,
            start_time=timezone.now() + timedelta(days=3),
            end_time=timezone.now() + timedelta(days=3, minutes=60),
            status=Booking.Status.PENDING,
            price_at_booking=self.service.price

        )

    def test_customer_can_list_bookings(self):
        self.create_booking()
        response = self.client.get(reverse("booking-list"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)

    def test_customer_can_create_booking(self):
        response = self.client.post(
            reverse("booking-list"),
            {
                "business": self.business.pk,
                "service": self.service.pk,
                "staff_member": self.staff_member.pk,
                "start_time": (
                    timezone.now() + timedelta(days=5)
                ).isoformat(),
                "notes": "API test booking",

            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(
            Booking.objects.filter(customer=self.customer).count(),
            1,
        )

    def test_customer_cannot_view_another_customers_booking(self):
        booking = self.create_booking()
        self.client.force_authenticate(user=self.other_customer)

        response = self.client.get(
            reverse("booking-detail", args=[booking.pk])
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_customer_can_cancel_own_booking(self):
        booking = self.create_booking()

        response = self.client.post(
            reverse("booking-cancel", args=[booking.pk])
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        booking.refresh_from_db()
        self.assertEqual(booking.status, Booking.Status.CANCELLED)

    def test_unauthenticated_customer_cannot_list_bookings(self):
        self.client.force_authenticate(user=None)
        response = self.client.get(reverse("booking-list"))

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)





