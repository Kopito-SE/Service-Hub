from decimal import Decimal
from django.db.models import Sum

from apps.bookings.models import Booking
from ..models import Payment, PaymentReversal

def get_net_paid_amount(*, booking):
    """Successful payments minus reversal for this booking."""
    total_successful = (
        Payment.objects.filter(
            booking=booking,
            status=Payment.Status.SUCCEEDED
        ).aggregate(total=Sum("amount"))["total"]
        or Decimal("0.00")
    )
    total_reversed = (
        PaymentReversal.objects.filter(
            payment__booking=booking,
            payment__status=Payment.Status.SUCCEEDED
        ).aggregate(total=Sum("amount"))["total"]
        or Decimal("0.00")
    )
    return total_successful - total_reversed

def get_outstanding_amount(*, booking):
    return booking.price_at_booking - get_net_paid_amount(booking=booking)