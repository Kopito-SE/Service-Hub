from rest_framework.routers import DefaultRouter

from .views import(StaffTimeOffViewSet, StaffWorkingHoursViewSet)

router = DefaultRouter()

router.register(
    "working-hours",
    StaffWorkingHoursViewSet,
    basename="working-hours"
)

router.register(
    "time-off",
    StaffTimeOffViewSet,
    basename="staff-time-off"
)

urlpatterns = router.urls
