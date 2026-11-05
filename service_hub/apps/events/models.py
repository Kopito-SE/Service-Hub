from django.db import models
from django.utils import timezone
import uuid
from django.conf import settings

class EventOutbox(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        PROCESSING = "processing", "Processing"
        COMPLETED = "completed", "Completed"
        DEAD = "dead", "Dead"

    event_type = models.CharField(max_length=100)

    # Stores the event's data in JSON format.
    payload = models.JSONField()
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING
    )

    created_at = models.DateTimeField(auto_now_add=True)
    Updated_at = models.DateTimeField(auto_now=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["created_at"]
        indexes = [
            models.Index(
                fields=["status", "created_at"],
                name="outbox_status_created_idx",

            ),
        ]

    def __str__(self):
        return f"{self.event_type}-{self.status}"

class EventDelivery(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        PROCESSING = "processing", "Processing"
        SUCCEEDED = "succeeded", "Succeeded"
        FAILED = "failed", "Failed"
        DEAD = "dead", "Dead"

    event = models.ForeignKey(
        EventOutbox,
        on_delete=models.CASCADE,
        related_name="deliveries"
    )

    # Stable identifier for the registered handler.
    handler_key = models.CharField(max_length=150)

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING
    )

    attempts = models.PositiveIntegerField(default=0)
    max_attempts = models.PositiveIntegerField(default=5)

    next_attempt_at = models.DateTimeField(
        default=timezone.now,
    )
    alerted_at = models.DateTimeField(
        null=True,
        blank=True
    )

    last_error = models.TextField(blank=True)
    processing_started_at = models.DateTimeField(
        null=True,
        blank=True
    )
    processing_token = models.UUIDField(
        null=True,
        blank=True,
        editable=False
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    processed_at = models.DateTimeField(null=True, blank=True)

    manual_retry_count = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["event", "handler_key"],
                name="unique_event_handler_delivery"
            ),
        ]
        indexes = [
            models.Index(
                fields=["status", "next_attempt_at"],
                name="delivery_status_retry_idx",
            ),
        ]
    def __str__(self):
        return f"{self.handler_key} - {self.status}"

class EventDeliveryRetry(models.Model):

    delivery = models.ForeignKey(
        EventDelivery,
        on_delete=models.CASCADE,
        related_name="retry_history"
    )

    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="requested_event_retries"
    )

    retry_number = models.PositiveIntegerField()
    previous_attempts = models.PositiveIntegerField()
    previous_error = models.TextField(blank=True)
    reason = models.TextField()

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Delivery {self.delivery_id} - Manual retry {self.retry_number}"