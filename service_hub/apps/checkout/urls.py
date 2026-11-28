from django.urls import path
from .views import (
    GuestCheckoutCreateAPIView,
    AuthenticatedCheckoutCreateAPIView
)

urlpatterns = [
    path(
        "guest/",
        GuestCheckoutCreateAPIView.as_view(),
        name="guest-checkout-create",
    ),
    path(
        "",
        AuthenticatedCheckoutCreateAPIView.as_view(),
        name="authenticated-checkout-create",

    )
]
