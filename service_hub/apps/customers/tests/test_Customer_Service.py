
from django.core.exceptions import ValidationError
from django.test import TestCase

from apps.customers.models import Customer
from apps.customers.services import CustomerService



class CustomerServiceTest(TestCase):
    def setUp(self):
        self.customer_data = {
            "full_name": "Steve Mark",
            "email": "Steve@example.com",
            "phone_number": "0112345678"
        }

    #==============================================
    # Email Normalization
    #==============================================

    def test_normalize_email(self):
        result = CustomerService.normalize_email(
            "STEVE@example.COM"
        )

        self.assertEqual(result, "steve@example.com")

    def test_invalid_email_is_rejected(self):
        with self.assertRaises(ValidationError):
            CustomerService.normalize_email("invalid-email")

    #================================================
    # Phone Normalization
    #==================================================

    def test_normalize_local_kenyan_phone(self):
        result = CustomerService.normalize_phone_number(
            "0712345678"
        )
        self.assertEqual(result, "+254712345678")

    def test_normalize_international_kenyan_phone(self):
        result = CustomerService.normalize_phone_number(
            "+254712345678"
        )
        self.assertEqual(result, "+254712345678")

    def test_normalize_phone_without_plus(self):
        result = CustomerService.normalize_phone_number(
            "254712345678"
        )
        self.assertEqual(result, "+254712345678")

    def test_invalid_phone_is_rejected(self):
        with self.assertRaises(ValidationError):
            CustomerService.normalize_phone_number(
                "123456789"
            )

    #=====================================
    # Customer Creation
    #===================================
    def test_create_new_customer(self):
        customer, created = (
            CustomerService.create_or_get_customer(
                **self.customer_data
            )
        )
        self.assertTrue(created)
        self.assertEqual(Customer.objects.count(), 1)

        self.assertEqual(customer.full_name, "Steve Mark")
        self.assertEqual(customer.email, "steve@example.com")
        self.assertEqual(
            customer.phone_number,
            "+254112345678"
        )

    #===========================================================
    # Existing Customer identification
    #===========================================================
    def test_reuse_existing_customer(self):
        existing_customer = Customer.objects.create(
            full_name="Steve Mark",
            email="steve@example.com",
            phone_number="+254112345678"
        )
        customer, created = (
            CustomerService.create_or_get_customer(
                full_name="Steve Mark",
                email="STEVE@EXAMPLE.COM",
                phone_number="0112345678"
            )
        )

        self.assertFalse(created)
        self.assertEqual(customer.pk, existing_customer.pk)
        self.assertEqual(Customer.objects.count(), 1)

    #============================================================
    # Identity conflicts
    #============================================================
    def test_reject_email_and_phone_belonging_to_different_customers(self):

        Customer.objects.create(
            full_name="Steve Mark",
            email="steve@example.com",
            phone_number="+25412345678"
        )
        Customer.objects.create(
            full_name="Maddy Marry",
            email="maddy@example.com",
            phone_number="254113456789"
        )
        with self.assertRaises(ValidationError):
            CustomerService.create_or_get_customer(
                full_name="Another Customer",
                email="steve@example.com",
                phone_number="0113456789"
            )

    def test_reject_when_only_email_matches(self):
        Customer.objects.create(
            full_name="Steve Mark",
            email="steve@example.com",
            phone_number="0712345678"
        )

        with self.assertRaises(ValidationError):
            CustomerService.create_or_get_customer(
                full_name="Steve Mark",
                email="steve@example.com",
                phone_number="0112345678"
            )

    def test_reject_when_only_phone_matches(self):
        Customer.objects.create(
            full_name="Steve Mark",
            email="steve@example.com",
            phone_number="+254712345678"
        )
        with self.assertRaises(ValidationError):
            CustomerService.create_or_get_customer(
                full_name="Steve Morris",
                email="mark@example.com",
                phone_number="0712345678"
            )

    def test_reject_ambiguous_email(self):
        Customer.objects.create(
            full_name="Steve Mark",
            email="mark@example.com",
            phone_number="0712345678"
        )
        Customer.objects.create(
            full_name="Steve Morris",
            email="mark@example.com",
            phone_number="0112345678"
        )
        with self.assertRaises(ValidationError):
            CustomerService.create_or_get_customer(
                full_name="Steve Mark",
                email="mark@example.com",
                phone_number="0712345678"
            )
