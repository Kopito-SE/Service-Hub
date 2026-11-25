from datetime import timedelta
from django.db import IntegrityError, transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.checkout.models import Checkout

from apps.bookings.interfaces import get_booking, BookingInterfaceError


class CheckoutService:
    EXPIRY_MINUTES = 15
    @staticmethod
    @transaction.atomic
    def create_checkout(*, booking_id):
        """
        Create one checkout for an existing pending Booking
        """
        try:
            booking = get_booking(booking_id=booking_id)
        except BookingInterfaceError as exc:
            raise ValidationError(
                "The booking could not be found"
            ) from exc

        if booking.status != "pending":
            raise ValidationError(
                "Checkout can only be created for a pending booking"
            )

        amount_due = booking.price_at_booking
        if amount_due <= 0:
            raise ValidationError(
                "The booking amount must be greater than zero."
            )

        expires_at = timezone.now() + timedelta(
            minutes=CheckoutService.EXPIRY_MINUTES
        )

        try:
            with transaction.atomic():
                checkout = Checkout.objects.create(
                    booking_id=booking.id,
                    customer_id=booking.customer_id,
                    amount_due=amount_due,
                    currency="KES",
                    status=Checkout.Status.PENDING,
                    expires_at=expires_at
                )

        except IntegrityError as exc:
            raise ValidationError(
                "A checkout session already exists for this booking."
            ) from exc
        
        return checkout
