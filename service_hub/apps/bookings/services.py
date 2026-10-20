from datetime import timedelta

from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.businesses.models import Business, StaffMember
from apps.service_catalog.models import Service

from .models import Booking
from apps.availability.services import AvailabilityService

from apps.availability.services import AvailabilityService


class BookingService:

    @staticmethod
    @transaction.atomic
    def create_booking(
            *,
            customer,
            business_id,
            service_id,
            start_time,
            staff_member_id=None,
            notes="",
    ):
        try:
            business = (
                Business.objects
                .select_for_update()
                .get(pk=business_id)
            )
        except Business.DoesNotExist:
            raise ValidationError({
                "business": "This selected business does not exist."
            })

        if not business.is_active:
            raise ValidationError({
                "business": "This business is not accepting bookings."
            })

        try:
            service = Service.objects.get(
                pk=service_id,
                business=business,
                is_active=True
            )
        except Service.DoesNotExist:
            raise ValidationError({
                "service": (
                    "Select an active service belonging "
                    "to the selected business."
                )
            })

        staff_member = None
        if staff_member_id is not None:
            try:
                staff_member = StaffMember.objects.get(
                    pk=staff_member_id,
                    business=business,
                    is_active=True,
                )
            except StaffMember.DoesNotExist:
                raise ValidationError({
                    "staff_member": (
                        "Select an active Staff member "
                        "belonging to this business."
                    )
                })

        if start_time <= timezone.now():
            raise ValidationError({
                "start_time": "The booking must be in the Future."
            })

        end_time = start_time + timedelta(
            minutes=service.duration_minutes
        )

        # Asks the Availability component to validate the working schedule
        if staff_member is not None:
            AvailabilityService.validate_staff_availability(
                staff_member=staff_member,
                start_time=start_time,
                end_time=end_time
            )

        # Only active reservations block availability.
        conflicts = Booking.objects.filter(
            business=business,
            status__in=[
                Booking.Status.PENDING,
                Booking.Status.CONFIRMED,
            ],
            start_time__lt=end_time,
            end_time__gt=start_time,
        )

        if staff_member is not None:
            # A staff-specific appointment conflicts with bookings for that
            # staff member and unassigned bookings that reserve business-wide capacity.
            conflicts = conflicts.filter(
                Q(staff_member=staff_member) | Q(staff_member__isnull=True)
            )
        else:
            # Conservative initial Policy: an Unassigned
            # booking reserves business-wide capacity.
            pass

        if conflicts.exists():
            raise ValidationError({
                "start_time": (
                    "This Time conflicts with an existing booking"
                )
            })

        return Booking.objects.create(
            customer=customer,
            business=business,
            service=service,
            staff_member=staff_member,
            start_time=start_time,
            end_time=end_time,
            notes=notes,
            price_at_booking=service.price,
            status=Booking.Status.PENDING,
        )

    @staticmethod
    @transaction.atomic
    def cancel_booking(*, booking):
        booking = (
            Booking.objects
            .select_for_update()
            .get(pk=booking.pk)
        )

        if booking.status == Booking.Status.CANCELLED:
            return booking

        if booking.status == Booking.Status.COMPLETED:
            raise ValidationError({
                "status": "A completed Booking Cannot be cancelled."
            })

        booking.status = Booking.Status.CANCELLED
        booking.save(update_fields=["status", "updated_at"])

        return booking
