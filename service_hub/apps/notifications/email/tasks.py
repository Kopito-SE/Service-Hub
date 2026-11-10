from celery import shared_task

from apps.notifications.email.worker import process_pending_emails

@shared_task(name="notifications.process_pending_emails")
def process_pending_emails_task(limit=100):
    return process_pending_emails(limit=limit)