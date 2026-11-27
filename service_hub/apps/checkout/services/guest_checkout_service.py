from dataclasses import dataclass

from django.db import transaction
from rest_framework.exceptions import ValidationError

from apps.customers.interfaces import (
    CustomerInterface,
    CustomerInterfaceError
)

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
class GuestCheckoutDTO:
    booking: BookingDTO
    checkout: CheckoutCreationDTO

class GuestCheckoutService:
    @staticmethod
    @transaction.atomic
    def create_guest_checkout(
            *,
            full_name,
            email,
            phone_number,
            business_id,
            service_id,
            start_time,
            staff_member_id=None,
            notes="",
    ):
        """
        Coordinate guest customer, booking and checkout creation.
        """
        # 1. Create or Identify the Customer
        try:
            customer, created = (
                CustomerInterface.create_or_get_customer(
                    full_name=full_name,
                    email=email,
                    phone_number=phone_number
                )
            )
        except CustomerInterfaceError as exc:
            raise ValidationError(str(exc)) from exc

        # 2. Create the Pending guest booking through the Booking public interface.
        try:
            booking = create_booking(
                guest_customer_id=customer.id,
                business_id=business_id,
                service_id=service_id,
                start_time=start_time,
                staff_member_id=staff_member_id,
                notes=notes
            )
        except BookingInterfaceError as exc:
            raise ValidationError(str(exc)) from exc

        # 3. Create the Checkout session.
        try:
            checkout_result = CheckoutService.create_checkout(
                booking_id=booking.id
            )
        except ValidationError:
            # Preserve the original Validation error.
            raise

        # 4. Return the coordinated result
        return GuestCheckoutDTO(
            booking=booking,
            checkout=checkout_result
        )