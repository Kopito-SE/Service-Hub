from rest_framework.routers import DefaultRouter
from .views import PaymentViewSet, MpesaCallbackView
from django.urls import path, include

router = DefaultRouter()
router.register("payment", PaymentViewSet, basename="payment")

urlpatterns = [
    path(
        "payments/payment/callback/",
        MpesaCallbackView.as_view(),
        name="payment-callback"
    ),
    path("", include(router.urls)),
]
