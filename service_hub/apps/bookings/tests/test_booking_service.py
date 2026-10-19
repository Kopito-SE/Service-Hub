from datetime import timedelta

from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.businesses.models import Business, StaffMember
from apps.service_catalog.models import Service
from apps.bookings.models import Booking
from apps.bookings.services import BookingService
from decimal import Decimal

User = get_user_model()

class BookingServiceTests(TestCase):
    def setUp(self):
        #Create the customer who will make the booking
        self.customer  = User.objects.create_user(
            username="Customer1",
            password="test-password-123",
        )

        # Create a business and its Services
        self.business = Business.objects.create(

            owner=self.customer,
            name="Topi's Demo salon",
            is_active=True,

        )

        self.service = Service.objects.create(
            business=self.business,
            name="HairCut",
            price=Decimal("500.00"),
            duration_minutes=60,
            is_active=True,
        )

        self.staff_member = StaffMember.objects.create(
            business=self.business,
            display_name="Alex",
            is_active=True
        )

        #Use a Future, timezone-aware appointment time
        self.start_time = timezone.now() + timedelta(days=2)

    def test_customer_can_create_booking(self):
        booking = BookingService.create_booking(
            customer=self.customer,
            business_id=self.business.pk,
            service_id=self.service.pk,
            staff_member_id=self.staff_member.pk,
            start_time=self.start_time,
            notes="First appointment",
        )

        self.assertEqual(booking.customer, self.customer)
        self.assertEqual(booking.business, self.business)
        self.assertEqual(booking.service, self.service)
        self.assertEqual(booking.status, Booking.Status.PENDING)
        self.assertEqual(booking.price_at_booking, self.service.price)

        # A 60-minute service must end 60 minutes after it starts.
        self.assertEqual(
            booking.end_time,
            self.start_time + timedelta(minutes=60),
        )

    def test_booking_cannot_be_created_in_the_past(self):
        past_time = timezone.now() - timedelta(days=1)

        with self.assertRaises(ValidationError):
            BookingService.create_booking(
                customer=self.customer,
                business_id=self.business.pk,
                service_id=self.service.pk,
                staff_member_id=self.staff_member.pk,
                start_time=past_time,
            )
    def test_overlapping_booking_is_rejected(self):
        BookingService.create_booking(
            customer=self.customer,
            business_id=self.business.pk,
            service_id=self.service.pk,
            staff_member_id=self.staff_member.pk,
            start_time=self.start_time
        )

        # This Appointment starts 30 min into the First one.
        overlapping_time = self.start_time + timedelta(minutes=30)

        with self.assertRaises(ValidationError):
            BookingService.create_booking(

                customer=self.customer,
                business_id=self.business.pk,
                service_id=self.service.pk,
                staff_member_id=self.staff_member.pk,
                start_time=overlapping_time

            )


    def test_inactive_business_rejects_booking(self):
        self.business.is_active = False
        self.business.save(update_fields=["is_active"])

        with self.assertRaises(ValidationError):
            BookingService.create_booking(
                customer=self.customer,
                business_id=self.business.pk,
                service_id=self.service.pk,
                staff_member_id=self.staff_member.pk,
                start_time=self.start_time
            )
    def test_cancellation_changes_booking_status(self):
        booking = BookingService.create_booking(
            customer=self.customer,
            business_id=self.business.pk,
            service_id=self.service.pk,
            staff_member_id=self.staff_member.pk,
            start_time=self.start_time
        )

        cancelled_booking = BookingService.cancel_booking(
            booking=booking
        )

        self.assertEqual(
            cancelled_booking.status,
            Booking.Status.CANCELLED
        )


    def test_service_from_another_business_is_rejected(self):
        other_business = Business.objects.create(
            owner=self.customer,
            name="Another Salon",
        )

        other_service = Service.objects.create(
            business=other_business,
            name="Hair Coloring",
            price="1500.00",
            duration_minutes=90,
        )

        with self.assertRaises(ValidationError):
            BookingService.create_booking(
                customer=self.customer,
                business_id=self.business.pk,
                service_id=other_service.pk,
                start_time=self.start_time,
            )

    def test_staff_from_another_business_is_rejected(self):
        other_business = Business.objects.create(
            owner=self.customer,
            name="Another Salon",
        )

        other_staff = StaffMember.objects.create(
            business=other_business,
            display_name="Jordan",
        )

        with self.assertRaises(ValidationError):
            BookingService.create_booking(
                customer=self.customer,
                business_id=self.business.pk,
                service_id=self.service.pk,
                staff_member_id=other_staff.pk,
                start_time=self.start_time,
            )

    def test_inactive_service_is_rejected(self):
        self.service.is_active = False
        self.service.save(update_fields=["is_active"])

        with self.assertRaises(ValidationError):
            BookingService.create_booking(
                customer=self.customer,
                business_id=self.business.pk,
                service_id=self.service.pk,
                start_time=self.start_time,
            )

    def test_cancelled_booking_does_not_block_slot(self):
        first_booking = BookingService.create_booking(
            customer=self.customer,
            business_id=self.business.pk,
            service_id=self.service.pk,
            staff_member_id=self.staff_member.pk,
            start_time=self.start_time,
        )

        BookingService.cancel_booking(booking=first_booking)

        second_booking = BookingService.create_booking(
            customer=self.customer,
            business_id=self.business.pk,
            service_id=self.service.pk,
            staff_member_id=self.staff_member.pk,
            start_time=self.start_time,
        )

        self.assertEqual(
            second_booking.status,
            Booking.Status.PENDING,
        )
