from calendar import weekday
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone

from rest_framework import status
from rest_framework.test import APITestCase

from apps.businesses.models import Business, StaffMember
from apps.service_catalog.models import Service
from apps.bookings.models import Booking
from apps.availability.models import StaffWorkingHours, StaffTimeOff

User = get_user_model()

class AvailabilityAPITests(APITestCase):
    def setUp(self):

        self.owner = User.objects.create_user(
            username="owner",
            password="TestPassword254"
        )

        self.other_owner = User.objects.create_user(
            username="owner1",
            password="TestPassword452"
        )

        self.business = Business.objects.create(
            owner=self.owner,
            name="Owner One Salon",
        )

        self.other_business = Business.objects.create(
            owner=self.other_owner,
            name="Owner Two Salon"
        )

        self.staff = StaffMember.objects.create(
            business=self.business,
            display_name = "Alex"

        )

        self.other_staff = StaffMember.objects.create(
            business=self.other_business,
            display_name = "Jabez"
        )

        self.client.force_authenticate(user=self.owner)

        self.working_hours_url = reverse("working-hours-list")
        self.time_off_url = reverse("staff-time-off-list")

    def test_owner_can_create_working_hours(self):
        response = self.client.post(
            self.working_hours_url,
            {
                "staff_member": self.staff.pk,
                "weekday":0,
                "opening_time": "09:00:00",
                "closing_time": "17:00:00"
            },
            format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(
            StaffWorkingHours.objects.filter(
                staff_member=self.staff,
                weekday=0,

            ).exists()
        )

    def test_owner_cannot_manage_another_business_staff(self):
        response = self.client.post(
            self.working_hours_url,
            {
                "staff_member": self.other_staff.pk,
                "weekday" : 0,
                "opening_time": "09:00:00",
                "closing_time": "17:00:00"
            },
            format = "json",

        )
        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST
        )

    def test_invalid_working_hours_are_rejected(self):
        response = self.client.post(
            self.working_hours_url,
            {
                "staff_member": self.staff.pk,
                "weekday": 0,
                "opening_time": "17:00:00",
                "closing_time": "09:00:00",
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

    def test_owner_only_sees_own_working_hours(self):
        StaffWorkingHours.objects.create(
            staff_member = self.staff,
            weekday=0,
            opening_time="09:00",
            closing_time="17:00"
        )

        StaffWorkingHours.objects.create(
            staff_member=self.other_staff,
            weekday=0,
            opening_time="10:00",
            closing_time="16:00"
        )

        response = self.client.get(self.working_hours_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        results = (
            response.data["results"]
            if isinstance(response.data, dict)
            and "results" in response.data
            else response.data
        )

        self.assertEqual(len(results), 1)
        self.assertEqual(
            results[0]["staff_member"],
            self.staff.pk,
        )

    def test_owner_can_create_time_off(self):
        start = timezone.now() + timedelta(days=10)
        end = start + timedelta(hours=2)

        response = self.client.post(
            self.time_off_url,
            {
                "staff_member": self.staff.pk,
                "start_time": start.isoformat(),
                "end_time": end.isoformat(),
                "reason": "Personal Leave",
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_201_CREATED,
        )

        self.assertTrue(
            StaffTimeOff.objects.filter(
                staff_member=self.staff,
            ).exists()
        )

    def test_invalid_time_off_period_is_rejected(self):
        start = timezone.now() + timedelta(days=10)
        end = start - timedelta(hours=1)

        response = self.client.post(
            self.time_off_url,
            {
                "staff_member": self.staff.pk,
                "start_time": start.isoformat(),
                "end_time": end.isoformat(),
                "reason": "Invalid period",
            },
            format="json",
        )
        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

    def test_owner_cannot_create_time_off_for_other_business(self):
        start = timezone.now() + timedelta(days=10)
        end = start + timedelta(hours=2)

        response = self.client.post(
            self.time_off_url,
            {
                "staff_member": self.other_staff.pk,
                "start_time": start.isoformat(),
                "end_time": end.isoformat(),
                "reason": "Unauthorized"
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

    def test_owner_cannot_retrieve_other_business_schedule(self):
        other_schedule = StaffWorkingHours.objects.create(
            staff_member=self.other_staff,
            weekday=0,
            opening_time="09:00",
            closing_time="17:00"
        )

        response = self.client.get(
            reverse(
                "working-hours-detail",
                args=[other_schedule.pk],
            )
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_404_NOT_FOUND,
        )





