from rest_framework.routers import DefaultRouter
from .views import PaymentViewSet, MpesaCallbackView
from django.urls import path

router = DefaultRouter()
router.register("payment", PaymentViewSet, basename="payment")

urlpatterns = [
    path(
        "payments/mpesa/callback/",
        MpesaCallbackView.as_view(),
        name="mpesa-callback"
    ),
    *router.urls,
]
