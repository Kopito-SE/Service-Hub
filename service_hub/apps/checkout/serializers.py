from rest_framework import serializers
from apps.checkout.services.guest_checkout_service import (
    GuestCheckoutService
)
from apps.checkout.services.authenticated_checkout_service import (
    AuthenticatedCheckoutService
)

class GuestCheckoutSerializer(serializers.Serializer):
    full_name = serializers.CharField(max_length=150)
    email = serializers.EmailField(max_length=254)
    phone_number = serializers.CharField(max_length=20)

    business_id = serializers.IntegerField(min_value=1)
    service_id = serializers.IntegerField(min_value=1)

    staff_member_id = serializers.IntegerField(
        min_value=1,
        required=False,
        allow_null=True
    )
    staff_time = serializers.DateTimeField()
    notes = serializers.CharField(
        required=False,
        allow_blank=True,
        default=""
    )

    def create(self, validated_data):
        return GuestCheckoutService.create_guest_checkout(
            **validated_data
        )

class AuthenticatedCheckoutSerializer(serializers.Serializer):
    business_id = serializers.IntegerField(min_value=1)
    service_id = serializers.IntegerField(min_value=1)

    staff_member_id = serializers.IntegerField(
        min_value=1,
        required=False,
        allow_null=True
    )

    start_time = serializers.DateTimeField()

    notes = serializers.CharField(
        required=False,
        allow_blank=True,
        default="",
    )

    def create(self, validated_data):
        request = self.context["request"]

        return AuthenticatedCheckoutService.create_checkout(
            customer=request.user,
            **validated_data
        )