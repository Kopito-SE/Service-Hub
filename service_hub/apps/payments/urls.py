from rest_framework.routers import DefaultRouter
from .views import PaymentViewSet
router = DefaultRouter()

router.register("payment", PaymentViewSet, basename="payment")

urlpatterns = router.urls
