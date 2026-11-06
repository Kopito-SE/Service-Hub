import uuid

from django.db import models
from django.utils import timezone

class EmailDelivery(models.Model):

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        PROCESSING = "processing", "Processing"
        SENT = "sent", "Sent"
        FAILED = "failed", "Failed"
        DEAD = "dead", "Dead"

    class Purpose(models.TextChoices):
        AUTHENTICATION = "authentication", "Authentication"
        NOTIFICATION = "notification", "Notification"
        SYSTEM = "system", "System"

    notification = models.ForeignKey(
        "notifications.Notification",
        on_delete=models.PROTECT,
        related_name="email_deliveries",
        null=True,
        blank=True
    )
    recipient_email = models.EmailField()
    subject = models.CharField(max_length=255)
    body = models.TextField()

    purpose = models.CharField(
        max_length=30,
        choices=Purpose.choices
    )

    idempotency_key = models.CharField(
        max_length=255,
        unique=True,
        null=True,
        blank=True
    )

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING
    )

    attempts = models.PositiveIntegerField(default=0)
    max_attempts = models.PositiveIntegerField(default=5)

    next_attempt_at = models.DateTimeField(
        default=timezone.now
    )

    processing_started_at = models.DateTimeField(
        null=True,
        blank=True
    )

    processing_token = models.UUIDField(
        null=True,
        blank=True
    )

    last_error = models.TextField(blank=True)
    provider_message_id = models.CharField(
        max_length=250,
        blank=True
    )

    sent_at = models.DateTimeField(
        null=True,
        blank=True
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(
                fields=["status", "next_attempt_at"],
                name="email_delivery_retry_idx",
            ),
        ]

    def __str__(self):
        return (
            f"Email to {self.recipient_email}"
            f"{self.status}"
        )
