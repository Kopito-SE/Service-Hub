from django.urls import path
from apps.events.views import(
    OutboxMonitoringView,
    EventDeliveryListView,
    EventDeliveryDetailView,
    EventDeliveryRetryView,
    EventDeliveryRetryHistoryView
)

urlpatterns = [
    path(
        "monitoring/",
        OutboxMonitoringView.as_view(),
        name="outbox-monitoring"
    ),
    path(
        "deliveries/",
        EventDeliveryListView.as_view(),
        name="event-delivery-list"
    ),
    path(
        "deliveries/<int:pk>/",
        EventDeliveryDetailView.as_view(),
        name="event-delivery-detail"
    ),
    path(
        "deliveries/<int:pk>/retry/",
        EventDeliveryRetryView.as_view(),
        name="event-delivery-retry"
    ),
    path(
        "deliveries/<int:pk>/retries/",
        EventDeliveryRetryHistoryView.as_view(),
        name="event-delivery-retry-history"
    )
]
