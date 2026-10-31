import logging
from collections import defaultdict

logger = logging.getLogger(__name__)
_handlers = defaultdict(list)

def handler_key(handler):
    """
    Generate a stable identifier for a registered handler.
    """
    return f"{handler.__module__}.{handler.__qualname__}"


def subscribe(event_type, handler):
    """
    Register a handler for a specific event class

    """
    if handler not in _handlers[event_type]:
        _handlers[event_type].append(handler)

def get_handlers(event_type):
    """
    Return all handlers registered for a given event type.
    """
    return tuple(_handlers.get(event_type, ()))

def get_handler(event_type, key):
    """
    Retrieve a registered handler using its stable identifier.
    """
    for handler in get_handlers(event_type):
        if handler_key(handler) == key:
            return handler

    return None

def dispatch(event):
    """
    Immediately dispatch an event to its registered handlers.
    Retained for any existing code that still needs direct dispatch.
    """
    for handler in get_handlers(type(event)):
        try:
            handler(event)
        except Exception:
            logger.exception(
                "Handler %s failed for event %s",
                handler.__qualname__,
                type(event).__name__,
            )

