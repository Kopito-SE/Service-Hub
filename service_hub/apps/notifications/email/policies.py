from apps.notifications.models import Notification

EMAIL_ELIGIBLE_EVENT_TYPES = {
    Notification.EventType.BOOKING_CREATED,
    Notification.EventType.BOOKING_CONFIRMED,
    Notification.EventType.BOOKING_CANCELLED,
    Notification.EventType.PAYMENT_SUCCEEDED,
    Notification.EventType.PAYMENT_FAILED
}

def can_send_email(event_type, severity):
    if event_type in EMAIL_ELIGIBLE_EVENT_TYPES:
        return True
    if event_type == Notification.EventType.SYSTEM_ALERT:
        return severity in {
            Notification.Severity.WARNING,
            Notification.Severity.CRITICAL
        }
    return False
