from django.conf import settings
from django.db import models
from django.db.models import F, Q

class Booking(models.Model):
    class Status(models.TextChoices):
        PENDING  = "pending", "Pending"
        CONFIRMED = "confirmed", "Confirmed"
        CANCELLED = "cancelled", "Cancelled"
        COMPLETED = "completed", "Completed"

    customer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="service_hub_bookings"
    )

    business = models.ForeignKey(
        "businesses.Business",
        on_delete = models.PROTECT,
        related_name="bookings"
    )

    service = models.ForeignKey(
        "service_catalog.Service",
        on_delete = models.PROTECT,
        related_name = "bookings"
    )

    staff_member = models.ForeignKey(
        "businesses.StaffMember",
        on_delete=models.PROTECT,
        related_name="bookings",
        null=True,
        blank=True
    )

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True
    )

    start_time = models.DateTimeField()
    end_time = models.DateTimeField()

    notes = models.TextField(blank=True)

    price_at_booking = models.DecimalField(
        max_digits=10,
        decimal_places=2
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["start_time"]
        constraints = [
            models.CheckConstraint(
                condition=Q(price_at_booking__gte=0),
                name="booking_price_nonnegative"
            ),

            models.CheckConstraint(
                condition=Q(end_time__gt=F("start_time")),
                name="booking_end_after_start"
            ),
        ]
        indexes = [
            models.Index(
                fields=["customer", "start_time"],
                name="booking_customer_time_idx",
            ),
            models.Index(
                fields=["business", "start_time", "status"],
                name="booking_business_time_idx",
            ),
        ]

    def __str__(self):
        return f"Booking #{self.pk} - {self.start_time}"



