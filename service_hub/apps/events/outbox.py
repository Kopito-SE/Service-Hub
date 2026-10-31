import json

from dataclasses import asdict, is_dataclass

from django.core.serializers.json import DjangoJSONEncoder
from django.db import transaction

from apps.events.dispatcher import get_handlers, handler_key
from apps.events.models import EventOutbox, EventDelivery

class OutboxService:
    @staticmethod
    @transaction.atomic
    def record_event(event):
        if not is_dataclass(event):
            raise TypeError("Events must be dataclass instance.")

        handlers = get_handlers(type(event))

        if not handlers:
            raise ValueError(
                f"No handlers registered for {type(event).__name__}."
            )
        # Convert the dataclass into JSON-compatible data.
        payload = json.loads(
            json.dumps(asdict(event), cls=DjangoJSONEncoder)
        )

        event_record = EventOutbox.objects.create(
            event_type=(
                f"{type(event).__module__}.{type(event).__qualname__}"
            ),
            payload=payload,
        )

        deliveries = [
            EventDelivery(
                event=event_record,
                handler_key=handler_key(handler)
            )
            for handler in handlers
        ]
        EventDelivery.objects.bulk_create(deliveries)

        return event_record
