from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.availability.models import SlotReservation
from apps.availability.services.reservation_service import ReservationService
from apps.businesses.models import Business, StaffMember


User = get_user_model()
DEFAULT_STAFF = object()

class ReservationServiceTests(TestCase):

    def setUp(self):
        self.owner = User.objects.create_user(
            username="reservation_owner",
            password="TestPassword254",
        )

        self.business = Business.objects.create(
            owner=self.owner,
            name="Reservation Test Salon",
        )

        self.staff = StaffMember.objects.create(
            business=self.business,
            display_name="Alex",
        )

        self.second_staff = StaffMember.objects.create(
            business=self.business,
            display_name="James",
        )

        self.start_time = timezone.now() + timedelta(days=5)
        self.end_time = self.start_time + timedelta(hours=1)

    def reserve_slot(
            self,
            *,
            booking_reference,
            staff_member_id=DEFAULT_STAFF,
            start_time=None,
            end_time=None,
            reservation_status=SlotReservation.Status.ACTIVE,
            expires_at=None
    ):
        if staff_member_id is DEFAULT_STAFF:
            staff_member_id = self.staff.pk

        return ReservationService.reserve_slot(
            business_id=self.business.pk,
            staff_member_id= staff_member_id,
            booking_reference=booking_reference,
            start_time=start_time or self.start_time,
            end_time=end_time or self.end_time,
            status=reservation_status,
            expires_at=expires_at,
        )

    def test_active_reservation_can_be_created(self):
        reservation = self.reserve_slot(booking_reference=101)

        self.assertEqual(
            reservation.status,
            SlotReservation.Status.ACTIVE
        )
        self.assertEqual(reservation.booking_reference, 101)

    def test_overlapping_reservation_for_same_staff_is_rejected(self):
        self.reserve_slot(booking_reference=101)

        with self.assertRaises(ValidationError):
            self.reserve_slot(booking_reference=102)

    def test_different_staff_can_have_overlapping_reservations(self):
        self.reserve_slot(booking_reference=101)

        reservation = self.reserve_slot(
            booking_reference=102,
            staff_member_id=self.second_staff.pk,
        )

        self.assertEqual(
            reservation.staff_member_id,
            self.second_staff.pk,
        )

    def test_unassigned_reservation_blocks_assigned_staff(self):
        self.reserve_slot(
            booking_reference=101,
            staff_member_id=None,
        )

        with self.assertRaises(ValidationError):
            self.reserve_slot(
                booking_reference=102,
                staff_member_id=self.second_staff.pk,
            )

    def test_assigned_reservation_blocks_unassigned_booking(self):
        self.reserve_slot(booking_reference=101)

        with self.assertRaises(ValidationError):
            self.reserve_slot(
                booking_reference=102,
                staff_member_id=None,
            )

    def test_expired_held_reservation_does_not_block_slot(self):
        SlotReservation.objects.create(
            business=self.business,
            staff_member=self.staff,
            booking_reference=101,
            start_time=self.start_time,
            end_time=self.end_time,
            status=SlotReservation.Status.HELD,
            expires_at=timezone.now() - timedelta(minutes=5),
        )

        reservation = self.reserve_slot(booking_reference=102)

        self.assertEqual(
            reservation.status,
            SlotReservation.Status.ACTIVE,
        )

    def test_reservation_can_be_confirmed(self):
        self.reserve_slot(booking_reference=101)

        reservation = ReservationService.confirm_reservation(
            booking_reference=101,
        )

        self.assertEqual(
            reservation.status,
            SlotReservation.Status.CONFIRMED,
        )

        self.assertIsNone(reservation.expires_at)

    def test_reservation_can_be_released(self):
        self.reserve_slot(booking_reference=101)

        reservation = ReservationService.release_reservation(
            booking_reference=101,
        )

        self.assertEqual(
            reservation.status,
            SlotReservation.Status.RELEASED,
        )

    def test_releasing_reservation_is_idempotent(self):
        self.reserve_slot(booking_reference=101)

        first_release = ReservationService.release_reservation(
            booking_reference=101,
        )

        second_release = ReservationService.release_reservation(
            booking_reference=101,
        )

        self.assertEqual(
            first_release.status,
            SlotReservation.Status.RELEASED,
        )

        self.assertEqual(
            second_release.status,
            SlotReservation.Status.RELEASED,
        )

    def test_expired_held_reservation_cannot_be_confirmed(self):
        SlotReservation.objects.create(
            business=self.business,
            staff_member=self.staff,
            booking_reference=101,
            start_time=self.start_time,
            end_time=self.end_time,
            status=SlotReservation.Status.HELD,
            expires_at=timezone.now() - timedelta(minutes=5),
        )

        with self.assertRaises(ValidationError):
            ReservationService.confirm_reservation(
                booking_reference=101,
            )

    def test_held_reservation_requires_expiry(self):
        with self.assertRaises(ValidationError):
            self.reserve_slot(
                booking_reference=101,
                reservation_status=SlotReservation.Status.HELD,
            )
