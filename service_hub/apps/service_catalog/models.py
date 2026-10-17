from django.db import models
from django.db.models import Q

class Service(models.Model):

    business = models.ForeignKey(
        "businesses.Business",
        on_delete=models.PROTECT,
        related_name="services"
    )

    name = models.CharField(max_length=30)
    description = models.TextField(blank=True)

    price = models.DecimalField(
        max_digits=10,
        decimal_places=2
    )

    duration_minutes = models.PositiveIntegerField()
    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=Q(price__gte=0),
                name="service_price_nonnegative"
            ),
            models.CheckConstraint(
                condition=Q(duration_minutes__gt=0),
                name="service_duration_positive"
            )
        ]
        indexes = [
            models.Index(
                fields=["business", "is_active"],
                name="service_business_active_idx"
            )
        ]
    def __str__(self):
        return f"{self.name} - {self.business.name}"