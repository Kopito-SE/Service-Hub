from django.db import models
from django.conf import settings

class Business(models.Model):
    class Category(models.TextChoices):
        SALON = "salon", "Salon"
        GARAGE = "garage", "Garage"
        CLEANING = "cleaning", "Cleaning"
        PHOTOGRAPHY = "photography", "Photography"
        CONSULTING = "consulting", "Consulting"
        OTHER = "other", "Other"

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="owned_businesses"
    )

    name = models.CharField(max_length=50)
    category = models.CharField(
        max_length=20,
        choices=Category.choices,
        default=Category.OTHER
    )

    description = models.TextField(blank=True)
    phone_number = models.CharField(max_length=20, blank=True)
    email = models.EmailField(blank=True)
    address = models.CharField(max_length=255, blank=True)
    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name


    class StaffMember(models.Model):

        business = models.ForeignKey(
            "businesses.Business",
            on_delete=models.PROTECT,
            related_name="staff_members"
        )

        user = models.ForeignKey(
            settings.AUTH_USER_MODEL,
            on_delete=models.PROTECT,
            related_name="staff_memberships",
            null=True,
            blank=True
        )

        display_name = models.CharField(max_length=50)
        is_active = models.BooleanField(default=True)
        created_at = models.DateTimeField(auto_now_add=True)

        class Meta:
            constraints = [
                models.UniqueConstraint(
                    fields=["business", "user"],
                    condition=models.Q(user__isnull=False),
                    name="unique_business_staff_user"
                )
            ]
        def __str__(self):
            return f"{self.display_name} - {self.business.name}"

