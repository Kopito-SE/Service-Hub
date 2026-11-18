
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.exceptions import ValidationError

from apps.businesses.models import Business
from apps.businesses.services import BusinessService


User = get_user_model()


class BusinessServiceTests(TestCase):

    def setUp(self):
        self.owner = User.objects.create_user(
            username="owner",
            email="owner@example.com",
            password="testpassword123"
        )

        self.other_owner = User.objects.create_user(
            username="other_owner",
            email="other@example.com",
            password="testpassword123"
        )

        self.business = BusinessService.create_business(
            owner=self.owner,
            name="Seth's Salon",
            category=Business.Category.SALON,
            description="A professional salon.",
            phone_number="0712345678",
            email="salon@example.com",
            address="Kutus"
        )

    # 1. Test business creation
    def test_create_business(self):
        business = BusinessService.create_business(
            owner=self.owner,
            name="Auto Garage",
            category=Business.Category.GARAGE
        )

        self.assertEqual(business.name, "Auto Garage")
        self.assertEqual(business.owner, self.owner)
        self.assertEqual(
            business.category,
            Business.Category.GARAGE
        )
        self.assertTrue(business.is_active)

    # 2. Test retrieving a business
    def test_get_business(self):
        business = BusinessService.get_business(
            business_id=self.business.pk,
            owner=self.owner
        )

        self.assertEqual(business, self.business)

    # 3. Test preventing another owner from accessing a business
    def test_get_business_rejects_wrong_owner(self):
        with self.assertRaises(ValidationError):
            BusinessService.get_business(
                business_id=self.business.pk,
                owner=self.other_owner
            )

    # 4. Test listing businesses by owner
    def test_list_businesses(self):
        BusinessService.create_business(
            owner=self.owner,
            name="Photography Studio",
            category=Business.Category.PHOTOGRAPHY
        )

        BusinessService.create_business(
            owner=self.other_owner,
            name="Cleaning Services",
            category=Business.Category.CLEANING
        )

        businesses = BusinessService.list_businesses(
            owner=self.owner
        )

        self.assertEqual(businesses.count(), 2)

        for business in businesses:
            self.assertEqual(business.owner, self.owner)

    # 5. Test updating business details
    def test_update_business(self):
        updated_business = BusinessService.update_business(
            business_id=self.business.pk,
            owner=self.owner,
            name="Updated Salon",
            address="Kerugoya",
            phone_number="0798765432"
        )

        self.assertEqual(updated_business.name, "Updated Salon")
        self.assertEqual(updated_business.address, "Kerugoya")
        self.assertEqual(
            updated_business.phone_number,
            "0798765432"
        )

    # 6. Test rejecting unauthorized fields
    def test_update_business_rejects_invalid_fields(self):
        with self.assertRaises(ValidationError):
            BusinessService.update_business(
                business_id=self.business.pk,
                owner=self.owner,
                owner1=self.other_owner
            )

    # 7. Test updating a business owned by another user
    def test_update_business_rejects_wrong_owner(self):
        with self.assertRaises(ValidationError):
            BusinessService.update_business(
                business_id=self.business.pk,
                owner=self.other_owner,
                name="Unauthorized Update"
            )

    # 8. Test business validation
    def test_create_business_rejects_invalid_email(self):
        with self.assertRaises(ValidationError):
            BusinessService.create_business(
                owner=self.owner,
                name="Invalid Business",
                email="not-an-email"
            )

    # 9. Test business deactivation
    def test_deactivate_business(self):
        business = BusinessService.deactivate_business(
            business_id=self.business.pk,
            owner=self.owner
        )

        self.assertFalse(business.is_active)

    # 10. Test deactivation is idempotent
    def test_deactivate_business_is_idempotent(self):
        first_result = BusinessService.deactivate_business(
            business_id=self.business.pk,
            owner=self.owner
        )

        second_result = BusinessService.deactivate_business(
            business_id=self.business.pk,
            owner=self.owner
        )

        self.assertFalse(first_result.is_active)
        self.assertFalse(second_result.is_active)

    # 11. Test rejecting deactivation by another owner
    def test_deactivate_business_rejects_wrong_owner(self):
        with self.assertRaises(ValidationError):
            BusinessService.deactivate_business(
                business_id=self.business.pk,
                owner=self.other_owner
            )
