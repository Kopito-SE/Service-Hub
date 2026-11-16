from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.availability.models import SlotReservation
from apps.businesses.models import Business, StaffMember

# noinspection PyTypeChecker
class ReservationService:
    @staticmethod
    def _get_blocking_reservations(
            *,
            business_id,
            staff_member_id,
            start_time,
            end_time,
            exclude_booking_reference=None
    ):
        """
        Find reservations that overlap the requested period.
        A staff-specific reservation conflicts with:
          - Reservations assigned to the same staff member.
          - Reservations without an assigned staff member.

        An unassigned reservation conflicts with all reservations
        belonging to the business.
        """
        now = timezone.now()

        conflicts = SlotReservation.objects.filter(
            business_id=business_id,
            start_time__lt=end_time,
            end_time__gt=start_time
        ).filter(
            Q(
                status__in=[
                    SlotReservation.Status.ACTIVE,
                    SlotReservation.Status.CONFIRMED
                ]
            )

            | Q(
                status=SlotReservation.Status.HELD,
                expires_at__gt=now
            )
        )
        if staff_member_id is not None:
            conflicts = conflicts.filter(
                Q(staff_member_id=staff_member_id)
                | Q(staff_member__isnull=True)
            )

        if exclude_booking_reference is not None:
            conflicts = conflicts.exclude(
                booking_reference=exclude_booking_reference
            )
        return conflicts

    @staticmethod
    @transaction.atomic
    def reserve_slot(
            *,
            business_id,
            staff_member_id,
            booking_reference,
            start_time,
            end_time,
            status=SlotReservation.Status.ACTIVE,
            expires_at=None
    ):
        """
        Create a reservation after checking for scheduling conflicts.
        ACTIVE is the default because an existing pending Booking
        is not necessarily a temporary payment hold.
        """
        if end_time <= start_time:
            raise ValidationError({
                "end_time": "End time must be after start time."
            })

        allowed_statuses = [
            SlotReservation.Status.HELD,
            SlotReservation.Status.ACTIVE,
            SlotReservation.Status.CONFIRMED,
        ]

        if status not in allowed_statuses:
            raise ValidationError({
                "status": "Invalid initial reservation status."
            })

        if status == SlotReservation.Status.HELD:
            if expires_at is None or expires_at <= timezone.now():
                raise ValidationError({
                    "expires_at": (
                        "A held reservation requires a future expiry time."
                    )
                })
        elif expires_at is not None:
            raise ValidationError({
                "expires_at": (
                    "Only held reservations can have an expiry time."
                )
            })

        # Use the same coordination lock as Booking and
        # AvailabilityManagementService.
        try:
            Business.objects.select_for_update().get(
                pk=business_id
            )
        except Business.DoesNotExist:
            raise ValidationError({
                "business": "Business does not exist."
            })

        if staff_member_id is not None:
            try:
                StaffMember.objects.get(
                    pk=staff_member_id,
                    business_id=business_id,
                )
            except StaffMember.DoesNotExist:
                raise ValidationError({
                    "staff_member": (
                        "Staff member does not belong to this business."
                    )
                })

        if SlotReservation.objects.filter(
                booking_reference=booking_reference
        ).exists():
            raise ValidationError({
                "booking_reference": (
                    "A reservation already exists for this booking."
                )
            })

        conflicts = ReservationService._get_blocking_reservations(
            business_id=business_id,
            staff_member_id=staff_member_id,
            start_time=start_time,
            end_time=end_time,
        )

        if conflicts.exists():
            raise ValidationError({
                "start_time": (
                    "This time slot conflicts with an existing reservation."
                )
            })

        return SlotReservation.objects.create(
            business_id=business_id,
            staff_member_id=staff_member_id,
            booking_reference=booking_reference,
            start_time=start_time,
            end_time=end_time,
            status=status,
            expires_at=expires_at,
        )

    @staticmethod
    @transaction.atomic
    def confirm_reservation(*, booking_reference):
        """
        Confirm an existing reservation.

        An expired HELD reservation cannot be confirmed.
        """

        try:
            reservation = SlotReservation.objects.get(
                booking_reference=booking_reference
            )
        except SlotReservation.DoesNotExist:
            raise ValidationError({
                "reservation": "Reservation does not exist."
            })

        Business.objects.select_for_update().get(
            pk=reservation.business_id
        )

        reservation = SlotReservation.objects.select_for_update().get(
            booking_reference=booking_reference
        )

        if reservation.status == SlotReservation.Status.CONFIRMED:
            return reservation

        if reservation.status == SlotReservation.Status.RELEASED:
            raise ValidationError({
                "reservation": "A released reservation cannot be confirmed."
            })

        if (
                reservation.status == SlotReservation.Status.HELD
                and reservation.expires_at <= timezone.now()
        ):
            raise ValidationError({
                "reservation": "This reservation hold has expired."
            })

        reservation.status = SlotReservation.Status.CONFIRMED
        reservation.expires_at = None

        reservation.save(
            update_fields=["status", "expires_at", "updated_at"]
        )

        return reservation

    @staticmethod
    @transaction.atomic
    def release_reservation(*, booking_reference):
        """
        Release a reservation so that its time slot becomes available.
        """

        try:
            reservation = SlotReservation.objects.get(
                booking_reference=booking_reference
            )
        except SlotReservation.DoesNotExist:
            raise ValidationError({
                "reservation": "Reservation does not exist."
            })

        Business.objects.select_for_update().get(
            pk=reservation.business_id
        )

        reservation = SlotReservation.objects.select_for_update().get(
            booking_reference=booking_reference
        )

        if reservation.status == SlotReservation.Status.RELEASED:
            return reservation

        reservation.status = SlotReservation.Status.RELEASED
        reservation.expires_at = None

        reservation.save(
            update_fields=["status", "expires_at", "updated_at"]
        )

        return reservation


