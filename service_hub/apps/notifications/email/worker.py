import logging
from apps.notifications.email.processor import EmailDeliveryProcessor
from apps.notifications.email.providers.factory import EmailProviderFactory

logger = logging.getLogger(__name__)

def process_pending_emails(limit=100):
    if limit < 1:
        raise ValueError("Limit must be greater than Zero")
    provider = EmailProviderFactory.create()

    processor = EmailDeliveryProcessor(
        provider=provider
    )
    # Move exhausted deliveries to dead before claiming new work.
    processor.recover_exhausted_deliveries()

    processed_count = 0

    while processed_count < limit:
        claim = processor.claim_delivery()

        if claim is None:
            break

        delivery_id, claim_token = claim

        processor.process_delivery(
            delivery_id=delivery_id,
            claim_token=claim_token
        )

        processed_count += 1

    return processed_count