from .models import Booking

def get_customer_bookings(customer):
    return (
        Booking.objects
        .filter(customer=customer)
        .select_related(
            "business",
            "service",
            "staff_member",
            "customer"

        )
        .order_by("-created_at")
    )

def get_customer_booking(*, customer, booking_id):
    return (
        Booking.objects
        .filter(customer=customer)
        .select_related(
            "business",
            "service",
            "staff_member"
        )
        .filter(pk=booking_id)
        .first()
    )