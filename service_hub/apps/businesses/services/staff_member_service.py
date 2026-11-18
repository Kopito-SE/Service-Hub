from cloudinary.api import update
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from rest_framework.exceptions import ValidationError

from apps.businesses.models import Business, StaffMember

class StaffMemberService:
    @staticmethod
    def _validate_staff_member(staff_member):
        """
        Validate staff member fields and model constraints.
        """
        try:
            staff_member.full_clean()
        except DjangoValidationError as exc:
            raise ValidationError(
                getattr(exc, "message_dict", exc.messages)
            )

    @staticmethod
    @transaction.atomic
    def add_staff_member(
            *,
            business_id,
            owner,
            display_name,
            user=None
    ):
        try:
            business = Business.objects.select_for_update().get(
                pk=business_id,
                owner=owner,
                is_active=True
            )
        except Business.DoesNotExist:
            raise ValidationError({
                "business": "Business does not exist, is_active, or you do not have permission to manage it"
            })

        staff_member = StaffMember(
            business=business,
            user=user,
            display_name=display_name
        )

        StaffMemberService._validate_staff_member(staff_member)

        staff_member.save()
        return staff_member

    @staticmethod
    def get_staff_member(
            *,
            staff_member_id,
            business_id,
            owner,
    ):
        """
        Retrieve a staff member belonging to the owner's business.
        """

        try:
            return StaffMember.objects.get(
                pk=staff_member_id,
                business_id=business_id,
                business__owner=owner,
            )
        except StaffMember.DoesNotExist:
            raise ValidationError({
                "staff_member": "Staff member does not exist."
            })

    @staticmethod
    def list_staff_members(
            *,
            business_id,
            owner
    ):
        """
        List staff members belonging to a particular business.
        """
        return StaffMember.objects.filter(
            business_id=business_id,
            business__owner=owner
        ).order_by("created_at")

    @staticmethod
    @transaction.atomic
    def update_staff_member(
            *,
            staff_member_id,
            business_id,
            owner,
            **updated_fields,
    ):
        """
        Update permitted staff member information.
        """

        allowed_fields = {
            "display_name",
            "user",
        }

        invalid_fields = set(updated_fields) - allowed_fields

        if invalid_fields:
            raise ValidationError({
                "fields": (
                    f"These fields cannot be updated: "
                    f"{', '.join(sorted(invalid_fields))}"
                )
            })

        try:
            staff_member = StaffMember.objects.select_for_update().get(
                pk=staff_member_id,
                business_id=business_id,
                business__owner=owner,
            )
        except StaffMember.DoesNotExist:
            raise ValidationError({
                "staff_member": "Staff member does not exist."
            })

        for field, value in updated_fields.items():
            setattr(staff_member, field, value)

        StaffMemberService._validate_staff_member(staff_member)

        staff_member.save()

        return staff_member

    @staticmethod
    @transaction.atomic
    def deactivate_staff_member(
            *,
            staff_member_id,
            business_id,
            owner
    ):
        """
        Deactivate a staff member without deleting their records.
        """
        try:
            staff_member = StaffMember.objects.select_for_update().get(
                pk=staff_member_id,
                business_id=business_id,
                business__owner=owner
            )
        except StaffMember.DoesNotExist:
            raise ValidationError({
                "staff_member": "Staff member does not exist."
            })
        if not staff_member.is_active:
            return staff_member

        staff_member.is_active = False
        staff_member.save(update_fields=["is_active"])

        return staff_member
