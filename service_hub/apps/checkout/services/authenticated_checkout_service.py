from dataclasses import dataclass
from django.db import transaction
from rest_framework.exceptions import ValidationError

from apps.bookings.interfaces import (
    BookingDTO,
    create_booking,
    BookingInterfaceError
)

from apps.checkout.services.checkout_service import (
    CheckoutService,
    CheckoutCreationDTO
)

@dataclass(frozen=True)
class AuthenticatedCheckoutDTO:
    booking: BookingDTO
    checkout: CheckoutCreationDTO

class AuthenticatedCheckoutService:
    @staticmethod
    @transaction.atomic
    def create_checkout(
            *,
            customer,
            business_id,
            service_id,
            start_time,
            staff_member_id=None,
            notes="",
    ):
        if not customer or not customer.is_authenticated:
            raise ValidationError(
                "An authenticated customer is required."
            )
        try:
            booking = create_booking(
                customer=customer,
                guest_customer_id=None,
                business_id=business_id,
                service_id=service_id,
                start_time=start_time,
                staff_member_id=staff_member_id,
                notes=notes
            )
        except BookingInterfaceError as exc:
            raise ValidationError(str(exc)) from exc

        checkout_result = CheckoutService.create_checkout(
            booking_id=booking.id
        )

        return AuthenticatedCheckoutDTO(
            booking=booking,
            checkout=checkout_result
        )