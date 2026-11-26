from datetime import timedelta

from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.businesses.interfaces import (
    BusinessInterface,
    BusinessInterfaceError,
)
from apps.service_catalog.interfaces import ServiceInterface, ServiceInterfaceError

from apps.bookings.models import Booking
from apps.availability.interfaces import (
    AvailabilityInterface,
    AvailabilityInterfaceError,
)

from apps.events.interfaces import (
    EventsInterface,
    EventsInterfaceError,
    BookingCreated,
    BookingCancelled,
    BookingConfirmed
)

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
        # 1. Lock and retrieve the business through its public interface.
        try:
            business = BusinessInterface.get_business_for_update(
                business_id=business_id
            )
        except BusinessInterfaceError as exc:
            raise ValidationError({
                "business": str(exc)
            }) from exc

        if not business.is_active:
            raise ValidationError({
                "business": "This business is not accepting bookings."
            })

        # 2. Retrieve the service through the Service Catalog Interface.
        try:
            service = ServiceInterface.get_active_service(
                service_id=service_id,
                business_id=business_id,
            )

        except ServiceInterfaceError as exc:
            raise ValidationError({
                "service": str(exc)
            }) from exc

        # 3. Validate the staff member through the Businesses interface.
        if staff_member_id is not None:
            try:
                BusinessInterface.get_active_staff_member(
                    staff_member_id=staff_member_id,
                    business_id=business_id,
                )
            except BusinessInterfaceError as exc:
                raise ValidationError({
                    "staff_member": str(exc)
                }) from exc

        # 4. Validate the booking start time.
        if start_time <= timezone.now():
            raise ValidationError({
                "start_time": "The booking must be in the future."
            })

        end_time = start_time + timedelta(
            minutes=service.duration_minutes
        )

        # 5. Ask Availability to validate the working schedule.
        if staff_member_id is not None:
            try:
                AvailabilityInterface.validate_appointment(
                    business_id=business_id,
                    staff_member_id=staff_member_id,
                    start_time=start_time,
                    end_time=end_time,
                )
            except AvailabilityInterfaceError as exc:
                raise ValidationError(exc.detail) from exc

        # 6. Create the booking using foreign-key IDs.
        # We no longer have Business or StaffMember model instances.
        booking = Booking.objects.create(
            customer=customer,
            business_id=business_id,
            service_id=service_id,
            staff_member_id=staff_member_id,
            start_time=start_time,
            end_time=end_time,
            notes=notes,
            price_at_booking=service.price,
            status=Booking.Status.PENDING,
        )

        # 7. Ask Availability to reserve the slot.
        try:
            AvailabilityInterface.reserve_slot(
                business_id=business_id,
                staff_member_id=staff_member_id,
                booking_reference=booking.pk,
                start_time=start_time,
                end_time=end_time,
                status="active",
            )
        except AvailabilityInterfaceError as exc:
            raise ValidationError(exc.detail) from exc

        # 8. Record the booking-created event in the outbox.
        event = BookingCreated(
            booking_id=booking.pk,
            customer_id=booking.customer_id,
            service_name=str(booking.service),
        )
        try:
            EventsInterface.publish(event)

        except EventsInterfaceError as exc:
            raise ValidationError({
                "event": str(exc)
            }) from exc

        return booking

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
                "status": "A completed booking cannot be cancelled."
            })

        booking.status = Booking.Status.CANCELLED
        booking.save(update_fields=["status", "updated_at"])

        try:
            AvailabilityInterface.release_reservation(
                booking_reference=booking.pk
            )
        except AvailabilityInterfaceError as exc:
            raise ValidationError(exc.detail) from exc

        event = BookingCancelled(
            booking_id=booking.pk,
            customer_id=booking.customer_id,
            service_name=str(booking.service),
        )
        try:
            EventsInterface.publish(event)

        except EventsInterfaceError as exc:
            raise ValidationError({
                "event": str(exc)
            }) from exc

        return booking

    @staticmethod
    @transaction.atomic
    def confirm_booking(*, booking_id):
        """Confirm a pending booking after Checkout is fully settled."""

        try:
            booking = (
                Booking.objects
                .select_for_update()
                .select_related("services")
                .get(pk=booking_id)
            )

        except Booking.DoesNotExist:
            raise ValidationError({
                "booking": "Booking does not exist."
            })

        # Idempotency: repeated confirmation is safe:
        if booking.status == Booking.Status.CONFIRMED:
            return booking

        if booking.status != Booking.Status.PENDING:
            raise ValidationError({
                "status": "Only pending bookings can be confirmed."
            })

        booking.status = Booking.Status.CONFIRMED
        booking.save(update_fields=["status", "updated_at"])

        event = BookingConfirmed(
            booking_id=booking.pk,
            customer_id=booking.customer_id,
            service_name=str(booking.service)
        )
        try:
            EventsInterface.publish(event)
        except EventsInterfaceError as exc:
            raise ValidationError({
                "event": str(exc)
            }) from exc

        return booking

    @staticmethod
    @transaction.atomic
    def expire_pending_booking(*, booking_id):
        """
        Expire a pending booking and release its reservation
        """
        try:
            booking = (
                Booking.objects
                .select_for_update()
                .get(pk=booking_id)
            )

        except Booking.DoesNotExist:
            raise ValidationError({
                "booking": "Booking does not exist"
            })
        # A Booking already cancelled needs no further action.
        if booking.status == Booking.Status.CANCELLED:
            return booking

        if booking.status != Booking.Status.PENDING:
            raise ValidationError({
                "status": "Only pending bookings can expire."
            })

        # Reuse the existing cancellation workflow:
        # Status change, reservation release and event publishing
        return BookingService.cancel_booking(
            booking=booking
        )
