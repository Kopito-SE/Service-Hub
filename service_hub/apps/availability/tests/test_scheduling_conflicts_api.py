
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone

from apps.businesses.models import Business, StaffMember
from apps.service_catalog.models import Service
from apps.bookings.models import Booking
from apps.availability.models import StaffWorkingHours, StaffTimeOff, SlotReservation

from apps.availability.tests.base import AvailabilityAPITestBase
from rest_framework import status

User = get_user_model()

class SchedulingConflictAPITests(AvailabilityAPITestBase):
    # Regression Tests for scheduling conflict
    def create_future_booking(self):
        local_start = timezone.localtime(
            timezone.now() + timedelta(days=14)
        ).replace(
            hour=10,
            minute=0,
            second=0,
            microsecond=0,
        )

        # Keep the test appointment safely in the future.
        if local_start <= timezone.localtime(timezone.now()):
            local_start += timedelta(days=1)

        booking = Booking.objects.create(
            customer=self.owner,
            business=self.business,
            service=Service.objects.create(
                business=self.business,
                name="Test consultation",
                price="800.00",
                duration_minutes=60,
            ),
            staff_member=self.staff,
            start_time=local_start,
            end_time=local_start + timedelta(hours=1),
            status=Booking.Status.CONFIRMED,
            price_at_booking="800.00",
        )

        # Availability owns the reservation, not the Booking model.
        SlotReservation.objects.create(
            business=self.business,
            staff_member=self.staff,
            booking_reference=booking.pk,
            start_time=booking.start_time,
            end_time=booking.end_time,
            status=SlotReservation.Status.CONFIRMED,
            expires_at=None,
        )

        return booking

    def test_time_off_conflicting_with_booking_is_rejected(self):
        booking = self.create_future_booking()

        response = self.client.post(
            self.time_off_url,
            {
                "staff_member": self.staff.pk,
                "start_time": booking.start_time.isoformat(),
                "end_time": booking.end_time.isoformat(),
                "reason": "Leave",
            },
            format="json",
        )
        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST
        )

    def test_working_hours_cannot_exclude_existing_booking(self):
        booking = self.create_future_booking()
        weekday = timezone.localtime(
            booking.start_time
        ).weekday()

        response = self.client.post(
            self.working_hours_url,
            {
                "staff_member": self.staff.pk,
                "weekday": weekday,
                "opening_time": "09:00:00",
                "closing_time": "10:30:00",
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

    def test_time_off_without_conflict_is_allowed(self):
        booking = self.create_future_booking()

        start = booking.end_time + timedelta(hours=2)
        end = start + timedelta(hours=1)

        response = self.client.post(
            self.time_off_url,
            {
                "staff_member": self.staff.pk,
                "start_time": start.isoformat(),
                "end_time": end.isoformat(),
                "reason": "Personal appointment",
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_201_CREATED
        )

    def test_updating_working_hours_cannot_exclude_existing_booking(self):
        booking = self.create_future_booking()
        weekday = timezone.localtime(booking.start_time).weekday()

        create_response = self.client.post(
            self.working_hours_url,
            {
                "staff_member": self.staff.id,
                "weekday": weekday,
                "opening_time": "09:00:00",
                "closing_time": "17:00:00"
            },
            format="json",
        )
        self.assertEqual(
            create_response.status_code,
            status.HTTP_201_CREATED
        )
        url = reverse(
            "working-hours-detail",
            args=[create_response.data["id"]]
        )
        response = self.client.patch(
            url,
            {"closing_time": "10:30:00"},
            format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_deleting_working_hours_with_future_booking_is_rejected(self):
        booking = self.create_future_booking()
        weekday = timezone.localtime(booking.start_time).weekday()

        create_response = self.client.post(
            self.working_hours_url,
            {
                "staff_member": self.staff.id,
                "weekday": weekday,
                "opening_time": "09:00:00",
                "closing_time": "17:00:00"
            },
            format="json"
        )
        self.assertEqual(
            create_response.status_code,
            status.HTTP_201_CREATED
        )
        url = reverse(
            "working-hours-detail",
            args=[create_response.data["id"]]
        )
        response = self.client.delete(url)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_updating_time_off_to_overlap_booking_is_rejected(self):
        booking = self.create_future_booking()

        initial_start = booking.start_time + timedelta(hours=2)
        initial_end = booking.start_time + timedelta(hours=3)

        create_response = self.client.post(
            self.time_off_url,
            {
                "staff_member": self.staff.id,
                "start_time": initial_start.isoformat(),
                "end_time": initial_end.isoformat(),
                "reason": "Personal appointment"
            },
            format="json",
        )
        self.assertEqual(create_response.status_code, status.HTTP_201_CREATED)

        url = reverse(
            "staff-time-off-detail",
            args=[create_response.data["id"]]
        )

        response = self.client.patch(
            url,
            {
                "start_time": booking.start_time.isoformat(),
                "end_time": booking.end_time.isoformat(),
                "reason": "Updated time off",
            },
            format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_deleting_time_off_succeeds(self):
        start_time = timezone.now() + timedelta(days=20)
        end_time = start_time + timedelta(hours=1)

        create_response = self.client.post(
            self.time_off_url,
            {
                "staff_member": self.staff.id,
                "start_time": start_time.isoformat(),
                "end_time": end_time.isoformat(),
                "reason": "Personal appointment"
            },
            format="json"
        )

        self.assertEqual(create_response.status_code, status.HTTP_201_CREATED)
        time_off_id = create_response.data["id"]

        url = reverse("staff-time-off-detail", args=[time_off_id])

        response = self.client.delete(url)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
