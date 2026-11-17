from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APITestCase

from apps.businesses.models import Business, StaffMember

User = get_user_model()


class AvailabilityAPITestBase(APITestCase):

    def setUp(self):
        self.owner = User.objects.create_user(
            username="owner",
            password="TestPassword254",
        )

        self.other_owner = User.objects.create_user(
            username="owner1",
            password="TestPassword452",
        )

        self.business = Business.objects.create(
            owner=self.owner,
            name="Owner One Salon",
        )

        self.other_business = Business.objects.create(
            owner=self.other_owner,
            name="Owner Two Salon",
        )

        self.staff = StaffMember.objects.create(
            business=self.business,
            display_name="Alex",
        )

        self.other_staff = StaffMember.objects.create(
            business=self.other_business,
            display_name="Jabez",
        )

        self.client.force_authenticate(user=self.owner)

        self.working_hours_url = reverse("working-hours-list")
        self.time_off_url = reverse("staff-time-off-list")