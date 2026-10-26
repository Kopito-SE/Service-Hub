from .models import Payment, PaymentReversal

def get_business_payments(user):
    return (
        Payment.objects
        .filter(booking__business__owner=user)
        .select_related(
            "booking",
            "booking__business",
            "booking__customer",
            "recorded_by"
        )
        .order_by("-created_at")
    )

def get_business_payment(*, user, payment_id):
    return (
        get_business_payments(user)
        .filter(pk=payment_id)
        .first()
    )

def get_payment_reversals(*, payment):
    return(
        PaymentReversal.objects
        .filter(payment=payment)
        .select_related("recorded_by")
        .order_by("-created_at")
    )
