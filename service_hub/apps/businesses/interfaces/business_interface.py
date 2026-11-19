from dataclasses import dataclass
from apps.businesses.models import Business, StaffMember
from django.db import transaction

class BusinessInterfaceError(Exception):
    """
    Raised when another component makes an invalid
    request to the Business component
    """
    pass

@dataclass(frozen=True)
class BusinessDTO:
    id: int
    owner_id: int
    name: str
    category:str
    is_active: bool

@dataclass(frozen=True)
class StaffMemberDTO:
    id: int
    business_id: int
    user_id: int | None
    display_name: str
    is_active: bool

class BusinessInterface:

    @staticmethod
    def get_business(*, business_id):
        """
        Retrieve a business without exposing its Django model.
        """
        try:
            business = Business.objects.get(pk=business_id)

        except Business.DoesNotExist:
            raise BusinessInterfaceError(
                "Business does not exist"
            )
        return BusinessDTO(
            id=business.id,
            owner_id=business.owner_id,
            name=business.name,
            category=business.category,
            is_active=business.is_active
        )
    @staticmethod
    def get_active_business(*, business_id):
        """
        Retrieve a business only if it is active.
        """
        try:
            business = Business.objects.get(
                pk=business_id,
                is_active=True
            )
        except Business.DoesNotExist:
            raise BusinessInterfaceError(
                "Business does not exist or is inactive."
            )
        return BusinessDTO(
            id=business.id,
            owner_id=business.owner_id,
            name=business.name,
            category=business.category,
            is_active=business.is_active
        )

    @staticmethod
    def get_business_for_update(*, business_id):
        """
        Lock a business row within the current transaction
        and return its DTO.
        The caller must already be inside transaction.atomic().
        """
        if not transaction.get_connection().in_atomic_block:
            raise BusinessInterfaceError(
                "This operation requires an active database transaction."
            )
        try:
            business = Business.objects.select_for_update().get(
                pk=business_id
            )
        except Business.DoesNotExist:
            raise BusinessInterfaceError(
                "Business does not exist."
            )
        return BusinessDTO(
            id=business.id,
            owner_id=business.owner_id,
            name=business.name,
            category=business.category,
            is_active=business.is_active
        )

    @staticmethod
    def get_staff_member(
            *,
            staff_member_id,
            business_id
    ):
        """
        Retrieve a staff member belonging to a particular business.
        Does not require the staff member or business to be active.
        """
        try:
            staff_member = StaffMember.objects.get(
                pk=staff_member_id,
                business_id=business_id
            )
        except StaffMember.DoesNotExist:
            raise BusinessInterfaceError(
                "Staff member does not belong to this business."
            )
        return StaffMemberDTO(
            id=staff_member.id,
            business_id=staff_member.business_id,
            user_id=staff_member.user_id,
            display_name=staff_member.display_name,
            is_active=staff_member.is_active
        )

    @staticmethod
    def get_active_staff_member(
            *,
            staff_member_id,
            business_id
    ):
        """
        Retrieve an active staff member belonging to
        an active business.
        """
        try:
            staff_member = StaffMember.objects.select_related(
                "business"
            ).get(
                pk=staff_member_id,
                business_id=business_id,
                business__is_active=True,
                is_active=True
            )

        except StaffMember.DoesNotExist:
            raise BusinessInterfaceError(
                "Staff Member does not exist, is inactive, or does not belong to this business."
            )
        return StaffMemberDTO(
            id=staff_member.id,
            business_id=staff_member.business_id,
            user_id=staff_member.user_id,
            display_name=staff_member.display_name,
            is_active=staff_member.is_active
        )

