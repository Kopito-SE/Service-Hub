from django.conf import settings
from django.db import models

class Notification(models.Model):
    class Channel(models.TextChoices):
        EMAIL = "email", "Email"
        IN_APP = "in_app", "In-app"

    class EventType(models.TextChoices):
        BOOKING_CREATED = "booking_created", "Booking Created"
        BOOKING_CONFIRMED = "booking_confirmed", "Booking Confirmed"
        BOOKING_CANCELLED = "booking_cancelled", "Booking Cancelled"
        PAYMENT_FAILED = "payment_failed", "Payment Failed"
        PAYMENT_SUCCEEDED = "payment_succeeded", "Payment Succeeded"

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        SENT = "sent", "Sent"
        FAILED = "failed", "Failed"

    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="notifications"
    )
    channel = models.CharField(
        max_length=20,
        choices=Channel.choices,
        default=Channel.IN_APP
    )
    event_type = models.CharField(
        max_length=40,
        choices=EventType.choices
    )
    subject = models.CharField(max_length=200)
    message = models.TextField()
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING
    )
    sent_at = models.DateTimeField(null=True, blank=True)
    read_at = models.DateTimeField(null=True, blank=True)

    failure_reason = models.CharField(max_length=255, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(
                fields=["recipient", "status"],
                name="notif_recipient_status_idx"
            ),
            models.Index(
                fields=["channel", "status"],
                name="notif_channel_status_idx"
            ),
        ]

    def __str__(self):
        return(
            f"{self.event_type} - "
            f"{self.recipient_id} - {self.status}"
        )

