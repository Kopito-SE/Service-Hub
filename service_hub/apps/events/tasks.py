from celery import shared_task
from apps.events.processor import process_pending_deliveries

@shared_task(
    name="apps.events.process_outbox",
    bind=True,
    max_retries=3,
    default_retry_delay=30,
    ignore_result=False
)
def process_outbox_task(self):
    try:
        return process_pending_deliveries(limit=100)
    except Exception as exc:
        raise self.retry(exc=exc)


