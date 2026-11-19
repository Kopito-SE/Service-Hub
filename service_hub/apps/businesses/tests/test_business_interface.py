from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.businesses.models import Business, StaffMember
from apps.businesses.interfaces import (
    BusinessInterface,
    BusinessInterfaceError,
    BusinessDTO,
    StaffMemberDTO,
)

User = get_user_model()

class BusinessInterfaceTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            username="owner",
            email="owner@example.com",
            password="testpass123",
        )

        self.other_owner = User.objects.create_user(
            username="otherowner",
            email="other@example.com",
            password="testpass123",
        )

        self.business = Business.objects.create(
            owner=self.owner,
            name="Seth's Salon",
            category=Business.Category.SALON,
        )

        self.inactive_business = Business.objects.create(
            owner=self.owner,
            name="Inactive Salon",
            category=Business.Category.SALON,
            is_active=False,
        )

        self.staff_member = StaffMember.objects.create(
            business=self.business,
            display_name="Odhis Major",
        )

        self.inactive_staff = StaffMember.objects.create(
            business=self.business,
            display_name="Odhis Bondeka",
            is_active=False,
        )

            #BUSINESS TESTS

    # 1. Test retrieve business return DataTransferObject(DTO)
    def test_get_business_returns_business_dto(self):
        result = BusinessInterface.get_business(
            business_id=self.business.id
        )

        self.assertIsInstance(result, BusinessDTO)
        self.assertEqual(result.id, self.business.id)
        self.assertEqual(result.name, "Seth's Salon")
        self.assertEqual(result.category, Business.Category.SALON)

    # 2. Test retrieving business returns owner ID
    def test_get_business_return_owner_id(self):
        result = BusinessInterface.get_business(
            business_id=self.business.id
        )
        self.assertEqual(result.owner_id, self.owner.id)

    # 3. Test Interface retrieves inactive businesses
    def test_get_business_can_retrieve_inactive_business(self):
        result = BusinessInterface.get_business(
            business_id=self.inactive_business.id
        )
        self.assertFalse(result.is_active)

    # 4. Test interface rejects retrieving non-existent business
    def test_get_business_rejects_nonexistent_business(self):
        with self.assertRaises(BusinessInterfaceError):
            BusinessInterface.get_business(
                business_id=99999
            )

    # 5. Test retrieving an active business succeed
    def test_get_active_business_returns_active_business(self):
        result = BusinessInterface.get_active_business(
            business_id=self.business.id
        )
        self.assertIsInstance(result, BusinessDTO)
        self.assertTrue(result.is_active)

    # 6. Test Interface reject inactive business
    def test_get_active_business_rejects_inactive_business(self):
        with self.assertRaises(BusinessInterfaceError):
            BusinessInterface.get_active_business(
                business_id=self.inactive_business.id
            )

            # STAFF MEMBER TESTS

    # 7. Test retrieve Active Staff returns StaffMember DTO
    def test_get_active_staff_member_returns_staff_dto(self):
        result = BusinessInterface.get_active_staff_member(
            staff_member_id=self.staff_member.id,
            business_id=self.business.id
        )
        self.assertIsInstance(result, StaffMemberDTO)
        self.assertEqual(result.id, self.staff_member.id)
        self.assertEqual(result.business_id, self.business.id)
        self.assertEqual(result.display_name, "Odhis Major")
        self.assertTrue(result.is_active)

    # 8. Test Interface rejects retrieval of Inactive staff
    def test_get_active_staff_member_rejects_inactive_staff(self):
        with self.assertRaises(BusinessInterfaceError):
            BusinessInterface.get_active_staff_member(
                staff_member_id=self.inactive_staff.id,
                business_id=self.business.id
            )

    # 9. Test Interface rejects retrieving staff with wrong Business
    def test_get_active_staff_member_rejects_wrong_business(self):
        with self.assertRaises(BusinessInterfaceError):
            BusinessInterface.get_active_staff_member(
                staff_member_id=self.staff_member.id,
                business_id=self.inactive_business.id
            )

    # 10. Test Interface rejects retrieval of staff member from inactive business
    def test_get_active_staff_member_rejects_inactive_business(self):
        self.business.is_active = False
        self.business.save(update_fields=["is_active"])

        with self.assertRaises(BusinessInterfaceError):
            BusinessInterface.get_active_staff_member(
                staff_member_id=self.staff_member.id,
                business_id=self.business.id,
            )
