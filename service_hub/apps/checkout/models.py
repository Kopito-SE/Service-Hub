import uuid
from django.db import models

class Checkout(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        PARTIALLY_PAID = "partially_paid", "Partially Paid"
        COMPLETED = "completed", "Completed"
        FAILED = "failed", "Failed"
        EXPIRED = "expired", "Expired"
        CANCELLED = "cancelled", "Cancelled"

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False
    )

    # References to the Bookings component
    # Deliberately not a ForeignKey
    booking_id = models.PositiveBigIntegerField(unique=True)

    # Nullable to support future guest checkout
    # This is an external user/customer identifier
    customer_id = models.PositiveBigIntegerField(
        null=True,
        blank=True
    )

    # Snapshot of the amount that must be settled
    amount_due = models.DecimalField(
        max_digits=12,
        decimal_places=2
    )

    currency = models.CharField(
        max_length=3,
        default="KES"
    )

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING
    )

    expires_at = models.DateTimeField()
    completed_at = models.DateTimeField(
        null=True,
        blank=True
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(
                fields=["status", "expires_at"],
                name="checkout_status_exp_idx"
            ),
        ]

    def __str__(self):
        return f"Checkout {self.id} - {self.status}"

class CheckoutPayment(models.Model):
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False
    )

    checkout = models.ForeignKey(
        Checkout,
        on_delete=models.CASCADE,
        related_name="payment_links"
    )

    # Reference to the Payment component
    # No direct ForeignKey to its Payment Model

    payment_id = models.PositiveBigIntegerField(unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Checkout {self.checkout_id} - Payment {self.payment_id}"