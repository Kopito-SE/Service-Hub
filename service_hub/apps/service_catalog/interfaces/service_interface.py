from dataclasses import dataclass
from decimal import Decimal
from apps.service_catalog.models import Service

class ServiceInterfaceError(Exception):
    """Raised when a service cannot be retrieved or validated."""

@dataclass(frozen=True)
class ServiceDTO:
    id: int
    business_id: int
    name: str
    price: Decimal
    duration_minutes: int
    is_active: bool

class ServiceInterface:

    @staticmethod
    def get_service(*, service_id):
        try:
            service = Service.objects.get(pk=service_id)

        except Service.DoesNotExist as exc:
            raise ServiceInterfaceError(
                "The selected service does not exist."
            ) from exc

        return ServiceDTO(
            id=service.pk,
            business_id=service.business_id,
            name=service.name,
            price=service.price,
            duration_minutes=service.duration_minutes,
            is_active=service.is_active
        )

    @staticmethod
    def get_active_service(*, service_id, business_id):
        try:
            service = Service.objects.get(
                pk=service_id,
                business_id=business_id,
                is_active=True
            )

        except Service.DoesNotExist as exc:
            raise ServiceInterfaceError(
                "Select an active service belonging to the selected business"
            ) from exc
        return ServiceDTO(
            id=service.pk,
            business_id=service.business_id,
            name=service.name,
            price=service.price,
            duration_minutes=service.duration_minutes,
            is_active=service.is_active
        )