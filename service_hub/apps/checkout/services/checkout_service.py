import hashlib
import secrets
import hmac
from dataclasses import dataclass
from datetime import timedelta

from django.db import IntegrityError, transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError
from apps.checkout.models import Checkout

from apps.bookings.interfaces import get_booking, BookingInterfaceError

@dataclass(frozen=True)
class CheckoutCreationDTO:
    checkout: Checkout
    guest_access_token: str | None

class CheckoutService:
    EXPIRY_MINUTES = 15

    @staticmethod
    def create_checkout(*, booking_id):
        """
        Create one checkout for an existing pending Booking.
        Supports registered and guest customers.
        Guest checkout receives a one-time access token.
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

        if (booking.customer_id is None) == (booking.guest_customer_id is None):
            raise ValidationError(
                "The booking must have exactly one customer identity."
            )
        guest_access_token = None
        guest_access_token_hash = None

        if booking.guest_customer_id is not None:
            guest_access_token = secrets.token_urlsafe(32)

            guest_access_token_hash = hashlib.sha256(
                guest_access_token.encode("utf-8")
            ).hexdigest()

        expires_at = timezone.now() + timedelta(
            minutes=CheckoutService.EXPIRY_MINUTES
        )

        try:
            with transaction.atomic():
                # Inner atomic creates a savepoint.
                # This allows the IntegrityError to be handled safely
                with transaction.atomic():
                    checkout = Checkout.objects.create(
                        booking_id=booking.id,
                        customer_id=booking.customer_id,
                        guest_customer_id=booking.guest_customer_id,
                        guest_access_token_hash=guest_access_token_hash,
                        amount_due=amount_due,
                        currency="KES",
                        status=Checkout.Status.PENDING,
                        expires_at=expires_at
                    )

        except IntegrityError as exc:
            raise ValidationError(
                "A checkout session already exists for this booking."
            ) from exc
        
        return CheckoutCreationDTO(
            checkout=checkout,
            guest_access_token=guest_access_token
        )

    @staticmethod
    def verify_guest_access(*, checkout_id, access_token):
        """
        Verify a guest's access token and return the Checkout.
        The raw token is hashed before comparison
        """
        if not isinstance(access_token, str) or not access_token:
            raise ValidationError("Invalid checkout credentials.")

        try:
            checkout = Checkout.objects.get(
                pk=checkout_id,
                guest_customer_id__isnull=False,
            )

        except (Checkout.DoesNotExist, ValueError, TypeError):
            raise ValidationError(
                "Invalid checkout credentials"
            )

        stored_hash = checkout.guest_access_token_hash

        if not stored_hash:
            raise ValidationError("Invalid checkout credentials.")

        provided_hash = hashlib.sha256(
            access_token.encode("utf-8")
        ).hexdigest()

        if not hmac.compare_digest(stored_hash, provided_hash):
            raise ValidationError("Invalid checkout credentials.")

        return checkout
