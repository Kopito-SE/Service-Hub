from decimal import Decimal

from django.test import TestCase
from django.contrib.auth import get_user_model

from apps.businesses.models import Business
from apps.service_catalog.models import Service
from apps.service_catalog.interfaces import (
    ServiceInterface,
    ServiceInterfaceError,
)

User = get_user_model()

class ServiceInterfaceTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            username="serviceowner",
            password="testpassword123",
        )

        self.business = Business.objects.create(
            owner=self.owner,
            name="Test Business",
            category=Business.Category.OTHER,
        )

        self.service = Service.objects.create(
            business=self.business,
            name="Haircut",
            price=Decimal("500.00"),
            duration_minutes=30,
        )

    def test_get_active_service(self):
        result = ServiceInterface.get_active_service(
            service_id=self.service.pk,
            business_id=self.business.pk
        )

        self.assertEqual(result.id, self.service.pk)
        self.assertEqual(result.business_id, self.business.pk)
        self.assertEqual(result.price, Decimal("500.00"))
        self.assertEqual(result.duration_minutes, 30)

    def test_reject_service_from_another_business(self):
        with self.assertRaises(ServiceInterfaceError):
            ServiceInterface.get_active_service(
                service_id=self.service.pk,
                business_id=99999
            )

    def test_reject_inactive_service(self):
        self.service.is_active = False
        self.service.save(update_fields=["is_active"])

        with self.assertRaises(ServiceInterfaceError):
            ServiceInterface.get_active_service(
                service_id=self.service.pk,
                business_id=self.business.pk
            )