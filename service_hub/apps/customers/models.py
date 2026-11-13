from django.db import models

class Customer(models.Model):
    """
    Customers can make booking without creating Service Hub accounts
    """
    full_name = models.CharField(max_length=150)

    email = models.EmailField(
        max_length=254,
        db_index=True
    )

    phone_number = models.CharField(
        max_length=16,
        db_index=True
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.full_name} ({self.phone_number})"
