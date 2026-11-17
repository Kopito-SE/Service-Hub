
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from apps.availability.interfaces import (
    AvailabilityInterface,
    AvailabilityInterfaceError,
    ReservationDTO,
)
from apps.availability.models import StaffWorkingHours, SlotReservation
from apps.businesses.models import Business, StaffMember


User = get_user_model()


class AvailabilityInterfaceTests(TestCase):

    def setUp(self):
        self.owner = User.objects.create_user(
            username="interface_owner",
            password="TestPassword254",
        )

        self.business = Business.objects.create(
            owner=self.owner,
            name="Interface Test Salon",
        )

        self.staff = StaffMember.objects.create(
            business=self.business,
            display_name="Alex",
        )

        self.start_time = timezone.now() + timedelta(days=5)
        self.end_time = self.start_time + timedelta(hours=1)

        weekday = self.start_time.weekday()

        StaffWorkingHours.objects.create(
            staff_member=self.staff,
            weekday=weekday,
            opening_time=self.start_time.time().replace(
                second=0,
                microsecond=0,
            ),
            closing_time=(
                self.start_time + timedelta(hours=2)
            ).time().replace(second=0, microsecond=0),
        )

    def test_validate_appointment_accepts_valid_appointment(self):
        result = AvailabilityInterface.validate_appointment(
            business_id=self.business.pk,
            staff_member_id=self.staff.pk,
            start_time=self.start_time,
            end_time=self.end_time,
        )

        self.assertIsNone(result)

    def test_validate_appointment_rejects_invalid_staff(self):
        with self.assertRaises(AvailabilityInterfaceError):
            AvailabilityInterface.validate_appointment(
                business_id=self.business.pk,
                staff_member_id=99999,
                start_time=self.start_time,
                end_time=self.end_time,
            )

    def test_validate_appointment_rejects_staff_from_another_business(self):
        other_owner = User.objects.create_user(
            username="other_interface_owner",
            password="TestPassword254",
        )

        other_business = Business.objects.create(
            owner=other_owner,
            name="Other Salon",
        )

        other_staff = StaffMember.objects.create(
            business=other_business,
            display_name="James",
        )

        with self.assertRaises(AvailabilityInterfaceError):
            AvailabilityInterface.validate_appointment(
                business_id=self.business.pk,
                staff_member_id=other_staff.pk,
                start_time=self.start_time,
                end_time=self.end_time,
            )

    def test_reserve_slot_returns_reservation_dto(self):
        reservation = AvailabilityInterface.reserve_slot(
            business_id=self.business.pk,
            staff_member_id=self.staff.pk,
            booking_reference=501,
            start_time=self.start_time,
            end_time=self.end_time,
            status=SlotReservation.Status.ACTIVE,
        )

        self.assertIsInstance(reservation, ReservationDTO)
        self.assertEqual(reservation.booking_reference, 501)
        self.assertEqual(
            reservation.status,
            SlotReservation.Status.ACTIVE,
        )
        self.assertEqual(reservation.business_id, self.business.pk)

    def test_reserve_slot_translates_validation_error(self):
        AvailabilityInterface.reserve_slot(
            business_id=self.business.pk,
            staff_member_id=self.staff.pk,
            booking_reference=501,
            start_time=self.start_time,
            end_time=self.end_time,
        )

        with self.assertRaises(AvailabilityInterfaceError):
            AvailabilityInterface.reserve_slot(
                business_id=self.business.pk,
                staff_member_id=self.staff.pk,
                booking_reference=502,
                start_time=self.start_time,
                end_time=self.end_time,
            )

    def test_confirm_reservation_returns_confirmed_dto(self):
        AvailabilityInterface.reserve_slot(
            business_id=self.business.pk,
            staff_member_id=self.staff.pk,
            booking_reference=501,
            start_time=self.start_time,
            end_time=self.end_time,
        )

        reservation = AvailabilityInterface.confirm_reservation(
            booking_reference=501,
        )

        self.assertIsInstance(reservation, ReservationDTO)
        self.assertEqual(
            reservation.status,
            SlotReservation.Status.CONFIRMED,
        )

    def test_release_reservation_returns_released_dto(self):
        AvailabilityInterface.reserve_slot(
            business_id=self.business.pk,
            staff_member_id=self.staff.pk,
            booking_reference=501,
            start_time=self.start_time,
            end_time=self.end_time,
        )

        reservation = AvailabilityInterface.release_reservation(
            booking_reference=501,
        )

        self.assertIsInstance(reservation, ReservationDTO)
        self.assertEqual(
            reservation.status,
            SlotReservation.Status.RELEASED,
        )

    def test_confirming_nonexistent_reservation_raises_interface_error(self):
        with self.assertRaises(AvailabilityInterfaceError):
            AvailabilityInterface.confirm_reservation(
                booking_reference=99999,
            )

    def test_releasing_nonexistent_reservation_raises_interface_error(self):
        with self.assertRaises(AvailabilityInterfaceError):
            AvailabilityInterface.release_reservation(
                booking_reference=99999,
            )
