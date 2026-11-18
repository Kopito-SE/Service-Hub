from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.exceptions import ValidationError

from apps.businesses.models import Business, StaffMember
from apps.businesses.services import BusinessService, StaffMemberService

User = get_user_model()

class StaffMemberServiceTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            username="owner",
            email="owner@example.com",
            password="testpassword123",
        )

        self.other_owner = User.objects.create_user(
            username="other_owner",
            email="other@example.com",
            password="testpassword123",
        )

        self.staff_user = User.objects.create_user(
            username="john",
            email="john@example.com",
            password="testpassword123",
        )

        self.business = BusinessService.create_business(
            owner=self.owner,
            name="Seth's Salon",
            category=Business.Category.SALON,
        )

        self.other_business = BusinessService.create_business(
            owner=self.other_owner,
            name="Other Salon",
            category=Business.Category.SALON,
        )

        self.staff_member = StaffMemberService.add_staff_member(
            business_id=self.business.pk,
            owner=self.owner,
            display_name="Jane Doe",
        )

    # 1. Add staff without a registered account
    def test_add_staff_member_without_user_account(self):
        staff = StaffMemberService.add_staff_member(
            business_id=self.business.pk,
            owner=self.owner,
            display_name="John Mapesa"
        )

        self.assertEqual(staff.display_name, "John Mapesa")
        self.assertIsNone(staff.user)
        self.assertEqual(staff.business, self.business)
        self.assertTrue(staff.is_active)

    # 2. Add staff with an existing user account
    def test_add_staff_member_with_user_account(self):
        staff = StaffMemberService.add_staff_member(
            business_id=self.business.pk,
            owner=self.owner,
            display_name="Jon Stark",
            user=self.staff_user
        )

        self.assertEqual(staff.user, self.staff_user)
        self.assertEqual(staff.display_name, "Jon Stark")

    # 3. Reject adding staff to a business owned by another user
    def test_add_staff_member_rejects_wrong_owner(self):
        with self.assertRaises(ValidationError):
            StaffMemberService.add_staff_member(
                business_id=self.business.pk,
                owner=self.other_owner,
                display_name="Unauthorized Staff",
            )

    # 4. Reject adding staff to an inactive business
    def test_add_staff_member_rejects_inactive_business(self):
        self.business.is_active = False
        self.business.save(update_fields=["is_active"])

        with self.assertRaises(ValidationError):
            StaffMemberService.add_staff_member(
                business_id=self.business.pk,
                owner=self.owner,
                display_name="New Staff",
            )

    # 5. Reject duplicate user assignment in the same business
    def test_add_staff_member_rejects_duplicate_user(self):
        StaffMemberService.add_staff_member(
            business_id=self.business.pk,
            owner=self.owner,
            display_name="Seth Dola",
            user=self.staff_user
        )

        with self.assertRaises(ValidationError):
            StaffMemberService.add_staff_member(
                business_id=self.business.pk,
                owner=self.owner,
                display_name="Odhis Major",
                user=self.staff_user
            )

    # 6. Allow the same user in a different business
    def test_same_user_can_belong_to_different_businesses(self):
        staff = StaffMemberService.add_staff_member(
            business_id=self.other_business.pk,
            owner=self.other_owner,
            display_name="Seth Dola",
            user=self.staff_user
        )
        self.assertEqual(staff.user, self.staff_user)
        self.assertEqual(staff.business, self.other_business)

    # 7. Retrieve staff Member
    def test_get_staff_member(self):
        staff = StaffMemberService.get_staff_member(
            staff_member_id=self.staff_member.pk,
            business_id=self.business.pk,
            owner=self.owner,
        )

        self.assertEqual(staff, self.staff_member)

    # 8. Reject retrieval by another owner
    def test_get_staff_member_rejects_wrong_owner(self):
        with self.assertRaises(ValidationError):
            StaffMemberService.get_staff_member(
                staff_member_id=self.staff_member.pk,
                business_id=self.business.pk,
                owner=self.other_owner,
            )

    # 9. List staff members belonging to a business
    def test_list_staff_members(self):
        StaffMemberService.add_staff_member(
            business_id=self.business.pk,
            owner=self.owner,
            display_name="Seth Dola",
        )

        StaffMemberService.add_staff_member(
            business_id=self.other_business.pk,
            owner=self.other_owner,
            display_name="Odhis Major",
        )

        staff_members = StaffMemberService.list_staff_members(
            business_id=self.business.pk,
            owner=self.owner,
        )

        self.assertEqual(staff_members.count(), 2)

        for staff in staff_members:
            self.assertEqual(staff.business, self.business)

    # 10. Update staff display name
    def test_update_staff_member_display_name(self):
        updated_staff = StaffMemberService.update_staff_member(
            staff_member_id=self.staff_member.pk,
            business_id=self.business.pk,
            owner=self.owner,
            display_name="Seth Dola",
        )

        self.assertEqual(
            updated_staff.display_name,
            "Seth Dola",
        )

    # 11. Link an existing user to an existing staff record
    def test_update_staff_member_link_user(self):
        updated_staff = StaffMemberService.update_staff_member(
            staff_member_id=self.staff_member.pk,
            business_id=self.business.pk,
            owner=self.owner,
            user=self.staff_user,
        )

        self.assertEqual(updated_staff.user, self.staff_user)

    # 12. Reject duplicate user assignment during update
    def test_update_staff_member_rejects_duplicate_user(self):
        another_staff = StaffMemberService.add_staff_member(
            business_id=self.business.pk,
            owner=self.owner,
            display_name="Odhis Major",
            user=self.staff_user,
        )

        with self.assertRaises(ValidationError):
            StaffMemberService.update_staff_member(
                staff_member_id=self.staff_member.pk,
                business_id=self.business.pk,
                owner=self.owner,
                user=self.staff_user,
            )

    # 13. Reject unauthorized field updates
    def test_update_staff_member_rejects_invalid_fields(self):
        with self.assertRaises(ValidationError):
            StaffMemberService.update_staff_member(
                staff_member_id=self.staff_member.pk,
                business_id=self.business.pk,
                owner=self.owner,
                business=self.other_business,
            )

    # 14. Reject updating staff belonging to another owner
    def test_update_staff_member_rejects_wrong_owner(self):
        with self.assertRaises(ValidationError):
            StaffMemberService.update_staff_member(
                staff_member_id=self.staff_member.pk,
                business_id=self.business.pk,
                owner=self.other_owner,
                display_name="Unauthorized Update",
            )

    # 15. Deactivate staff member
    def test_deactivate_staff_member(self):
        staff = StaffMemberService.deactivate_staff_member(
            staff_member_id=self.staff_member.pk,
            business_id=self.business.pk,
            owner=self.owner,
        )

        self.assertFalse(staff.is_active)

    # 16. Deactivation is idempotent
    def test_deactivate_staff_member_is_idempotent(self):
        first_result = StaffMemberService.deactivate_staff_member(
            staff_member_id=self.staff_member.pk,
            business_id=self.business.pk,
            owner=self.owner,
        )

        second_result = StaffMemberService.deactivate_staff_member(
            staff_member_id=self.staff_member.pk,
            business_id=self.business.pk,
            owner=self.owner,
        )

        self.assertFalse(first_result.is_active)
        self.assertFalse(second_result.is_active)

    # 17. Reject deactivation by another owner
    def test_deactivate_staff_member_rejects_wrong_owner(self):
        with self.assertRaises(ValidationError):
            StaffMemberService.deactivate_staff_member(
                staff_member_id=self.staff_member.pk,
                business_id=self.business.pk,
                owner=self.other_owner,
            )