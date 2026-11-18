from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from rest_framework.exceptions import ValidationError

from apps.businesses.models import Business

class BusinessService:
    @staticmethod
    def _validate_business(business):
        """
        Validate business fields using Django model validation.
        """
        try:
            business.full_clean()

        except DjangoValidationError as exc:
            raise ValidationError(
                getattr(exc, "message_dict", exc.messages)
            )

    @staticmethod
    @transaction.atomic
    def create_business(
            *,
            owner,
            name,
            category=Business.Category.OTHER,
            description="",
            phone_number="",
            email="",
            address=""
    ):
        """
        Create a business owned by the supplied user.
        """
        business = Business(
            owner=owner,
            name=name,
            category=category,
            description=description,
            phone_number=phone_number,
            email=email,
            address=address
        )

        BusinessService._validate_business(business)
        business.save()

        return business

    @staticmethod
    def get_business(*, business_id, owner):
        try:
            return Business.objects.get(
                pk=business_id,
                owner=owner,
            )
        except Business.DoesNotExist:
            raise ValidationError({
                "business": "Business does not exist."
            })

    @staticmethod
    def list_businesses(*, owner):
        """
        Retrieve all businesses belonging to an owner.
        """

        return Business.objects.filter(
            owner=owner
        ).order_by("-created_at")

    @staticmethod
    @transaction.atomic
    def update_business(
            *,
            business_id,
            owner,
            **updated_fields
    ):
        """
        Update permitted business information.
        """
        allowed_fields = {
            "name",
            "description",
            "category",
            "phone_number",
            "email",
            "address"
        }

        invalid_fields = set(updated_fields) - allowed_fields

        if invalid_fields:
            raise ValidationError({
                "fields": f"These fields cannot be updated: {','.join(sorted(invalid_fields))}"
            })

        try:
            business = Business.objects.select_for_update().get(
                pk=business_id,
                owner=owner
            )
        except Business.DoesNotExist:
            raise ValidationError({
                "business": "Business does not exist."
            })
        for field, value in updated_fields.items():
            setattr(business, field, value)

        BusinessService._validate_business(business)

        business.save()
        return business

    @staticmethod
    @transaction.atomic
    def deactivate_business(*, business_id, owner):
        """
        Deactivate a business without deleting its records.
        """
        try:
            business = Business.objects.select_for_update().get(
                pk=business_id,
                owner=owner
            )

        except Business.DoesNotExist:
            raise ValidationError({
                "business": "Business does not exist."
            })

        if not business.is_active:
            return business

        business.is_active = False
        business.save(update_fields=["is_active", "updated_at"])

        return business





