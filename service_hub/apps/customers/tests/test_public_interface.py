from apps.customers.interfaces.customer_interface import (
    CustomerDTO,
    CustomerInterface,
    CustomerInterfaceError
)

from django.test import TestCase


class CustomerInterfaceTests(TestCase):
    def test_interface_returns_customer_dto(self):
        customer, created = (
            CustomerInterface.create_or_get_customer(
                full_name="John Mark",
                email="john@example.com",
                phone_number="0712345678"
            )
        )
        self.assertIsInstance(customer, CustomerDTO)
        self.assertTrue(created)
        self.assertEqual(customer.full_name, "John Mark")
        self.assertEqual(customer.email, "john@example.com")
        self.assertEqual(customer.phone_number, "+254712345678")

    def test_interface_reuses_existing_customer(self):
        first, _ = CustomerInterface.create_or_get_customer (
            full_name="John Mark",
            email="john@example.com",
            phone_number="+254712345678"
        )

        second, created = (
            CustomerInterface.create_or_get_customer(
                full_name="John Mark",
                email="John@Example.com",
                phone_number="0712345678"
            )
        )
        self.assertFalse(created)
        self.assertEqual(first.id, second.id)

    def test_interface_translates_validation_errors(self):
        with self.assertRaises(CustomerInterfaceError):
            CustomerInterface.create_or_get_customer(
                full_name="John Mark",
                email="invalid-email",
                phone_number="0712345678"
            )