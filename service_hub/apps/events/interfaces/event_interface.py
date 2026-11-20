from apps.events.outbox import OutboxService

class EventInterfaceError(Exception):
    """Raised when publishing an event fails."""

class EventsInterface:
    @staticmethod
    def publish(event):
        try:
            return OutboxService.record_event(event)

        except (TypeError, ValueError) as exc:
            raise EventInterfaceError(str(exc)) from exc
