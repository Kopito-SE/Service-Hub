
from django.conf import settings
from django.db import models
from django.db.models import Q


class Payment(models.Model):
    class Method(models.TextChoices):
        CASH = "cash", "Cash"
        MPESA = "mpesa", "M-Pesa"
        BANK_TRANSFER = "bank_transfer", "Bank transfer"
        CARD = "card", "Card"
        OTHER = "other", "Other"

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        SUCCEEDED = "succeeded", "Succeeded"
        FAILED = "failed", "Failed"

    booking = models.ForeignKey(
        "bookings.Booking",
        on_delete=models.PROTECT,
        related_name="payments",
    )
    amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
    )
    currency = models.CharField(max_length=3, default="KES")
    method = models.CharField(
        max_length=20,
        choices=Method.choices,
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
    )
    transaction_reference = models.CharField(
        max_length=100,
        blank=True,
    )
    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="recorded_payments",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=Q(amount__gt=0),
                name="payment_amount_positive",
            ),
            models.UniqueConstraint(
                fields=["method", "transaction_reference"],
                condition=~Q(transaction_reference=""),
                name="unique_payment_method_reference",
            ),
        ]
        indexes = [
            models.Index(
                fields=["booking", "status"],
                name="payment_booking_status_idx",
            ),
        ]
        ordering = ["-created_at"]

    def __str__(self):
        return (
            f"Payment {self.pk} - "
            f"{self.amount} {self.currency} ({self.status})"
        )


class PaymentReversal(models.Model):
    payment = models.ForeignKey(
        Payment,
        on_delete=models.PROTECT,
        related_name="reversals",
    )
    amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
    )
    reason = models.CharField(max_length=255)
    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="recorded_payment_reversals",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=Q(amount__gt=0),
                name="payment_reversal_amount_positive",
            ),
        ]
        indexes = [
            models.Index(
                fields=["payment", "created_at"],
                name="reversal_payment_created_idx",
            ),
        ]
        ordering = ["-created_at"]

    def __str__(self):
        return f"Reversal {self.pk} - Payment {self.payment_id}"



