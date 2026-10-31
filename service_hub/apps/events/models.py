from django.db import models
from django.utils import timezone

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

    last_error = models.TextField(blank=True)
    processing_started_at = models.DateTimeField(
        null=True,
        blank=True
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    processed_at = models.DateTimeField(null=True, blank=True)



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