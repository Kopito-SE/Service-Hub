import re
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db import transaction

from .models import Customer

class CustomerService:
    """
    Handle customer creation, contact normalization,
    and existing customer identification.
    """
    @staticmethod
    def normalize_email(email):
        if not email or not email.strip():
            raise ValidationError({
                "email": "Email address required."
            })
        normalized_email = email.strip().lower()
        validate_email(normalized_email)

        return normalized_email

    @staticmethod
    def normalize_phone_number(phone_number):

        if not phone_number:
            raise ValidationError({
                "phone_number": "Phone number is required."
            })
        # Remove spaces, hyphens and common formatting characters.
        number = re.sub(r"[\s\-()]", "", phone_number)

        if number.startswith("+"):
            number = number[1:]

        if number.startswith("0") and len(number) == 10:
            number = "254" + number[1:]

        if (
            number.startswith("254")
            and len(number) == 12
            and number[3] in ("7", "1")
            and number.isdigit()
        ):
            return "+" + number
        raise ValidationError({
            "phone_number": "Enter a valid Kenyan mobile number."
        })

    @staticmethod
    @transaction.atomic
    def create_or_get_customer(*, full_name, email, phone_number):
        if not full_name or not full_name.strip():
            raise ValidationError({
                "full_name": "Full name is required."
            })
        full_name = full_name.strip()
        email = CustomerService.normalize_email(email)

        phone_number = CustomerService.normalize_phone_number(phone_number)
        email_matches = list(
            Customer.objects.filter(email=email)[:2]
        )

        phone_matches = list(
            Customer.objects.filter(phone_number=phone_number)[:2]
        )
        # Multiple records sharing an identifier are ambiguous .
        if len(email_matches) > 1 or len(phone_matches) > 1:
            raise ValidationError(
                "Customer identity is ambiguous. Manual review is required."
            )
        email_customer = email_matches[0] if email_matches else None
        phone_customer = phone_matches[0] if phone_matches else None

        # Both identifiers must point to the same customer.

        if email_customer and phone_customer:
            if email_customer.pk != phone_customer.pk:
                raise ValidationError(
                    "The Provided email and phone belong to different Customer records."
                )
            return email_customer, False

        # Only one identifier matched. Do not silently merge or
        # Overwrite the existing customer's contact information

        if email_customer or phone_customer:
            raise ValidationError(
                "One contact detail matches an existing customer,"
                "but the other does not. Customer verification is required."
            )
        customer = Customer.objects.create(
            full_name=full_name,
            email=email,
            phone_number=phone_number
        )

        return customer, True