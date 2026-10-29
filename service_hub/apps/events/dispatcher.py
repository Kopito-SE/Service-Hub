import logging
from collections import defaultdict

logger = logging.getLogger(__name__)
_handlers = defaultdict(list)

def subscribe(event_type, handler):
    """
    Register a handler for a specific event class

    """
    if handler not in _handlers[event_type]:
        _handlers[event_type].append(handler)

def dispatch(event):
    """
    Deliver an event to all handlers registered for its class.
    One handler failing should not prevent other handlers
    from receiving the same event

    """
    for handler in _handlers[type(event)]:
        try:
            handler(event)
        except Exception:
            logger.exception(
                "Handler %s failed for event %s",
                handler.__qualname__,
                type(event).__name__,
            )
