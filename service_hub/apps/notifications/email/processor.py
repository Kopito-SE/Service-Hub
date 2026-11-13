import uuid
from datetime import timedelta
from django.db import transaction
from django.db.models import F, Q
from django.utils import timezone

from apps.notifications.models import EmailDelivery, Notification
from apps.notifications.email.providers.base import EmailProvider
from apps.notifications.email.providers.exceptions import (
    TemporaryEmailProviderError,
    PermanentEmailProviderError
)

RECOVERY_TIMEOUT = timedelta(minutes=5)

BASE_RETRY_DELAY = 60
MAX_RETRY_DELAY = 3600

class EmailDeliveryProcessor:
    def __init__(self, provider: EmailProvider):
        self.provider = provider

    @staticmethod
    def _sync_notification(
            delivery,
            status,
            sent_at=None,
            failure_reason=""
    ):
        """
        Synchronize the linked Notification with its EmailDelivery.
        Authentication and system emails may not have a linked Notification, so
        notification_id can be None
        :param delivery:
        :param status:
        :param sent_at:
        :param failure_reason:
        :return:
        """
        if delivery.notification_id is None:
            return

        Notification.objects.filter(
            pk=delivery.notification_id
        ).update(
            status=status,
            sent_at=sent_at,
            failure_reason=failure_reason
        )

    def claim_delivery(self):
        now = timezone.now()
        recovery_threshold = now - RECOVERY_TIMEOUT

        with transaction.atomic():
            delivery = (
                EmailDelivery.objects
                .select_for_update(skip_locked=True)
                .filter(
                    Q(
                        status__in=[
                            EmailDelivery.Status.PENDING,
                            EmailDelivery.Status.FAILED
                        ],
                        next_attempt_at__lte=now,
                    )
                    |
                    Q(
                        status=EmailDelivery.Status.PROCESSING,
                        processing_started_at__lte=recovery_threshold
                    ),
                    attempts__lt=F("max_attempts"),
                )
                .order_by("next_attempt_at", "created_at")
                .first()
            )
            if delivery is None:
                return None

            claim_token = uuid.uuid4()

            delivery.status = EmailDelivery.Status.PROCESSING
            delivery.processing_started_at = now
            delivery.processing_token = claim_token
            delivery.attempts += 1

            delivery.save(
                update_fields=[
                    "status",
                    "processing_started_at",
                    "processing_token",
                    "attempts",
                    "updated_at"
                ]
            )

            return delivery.pk, claim_token

    #============================================================
    # implement Retry Calculation
    #===============================================================

    def calculate_retry_time(self, attempts):
        delay = min(
            BASE_RETRY_DELAY * (2** (attempts - 1)),
            MAX_RETRY_DELAY
        )
        return timezone.now() + timedelta(seconds=delay)


    #================================================================
    # Implement Successful delivery Handling
    #==================================================================
    def mark_as_sent(self, delivery_id, claim_token, result):
        now = timezone.now()

        with transaction.atomic():
            delivery = (
                EmailDelivery.objects
                .select_for_update()
                .filter(
                    pk=delivery_id,
                    status=EmailDelivery.Status.PROCESSING,
                    processing_token=claim_token
                )
                .first()
            )

            # The claim may have expired or been reclaimed.
            if delivery is None:
                return False

            delivery.status = EmailDelivery.Status.SENT
            delivery.provider_message_id = (
                result.provider_message_id or ""
            )
            delivery.sent_at = now
            delivery.processing_started_at = None
            delivery.processing_token = None
            delivery.last_error = ""

            delivery.save(
                update_fields=[
                    "status",
                    "provider_message_id",
                    "sent_at",
                    "processing_started_at",
                    "processing_token",
                    "last_error",
                    "updated_at"
                ]
            )

            self._sync_notification(
                delivery=delivery,
                status=Notification.Status.SENT,
                sent_at=now
            )

            return True

    #===================================================================
    # Implement Failure Handling
    #=====================================================================
    def mark_as_failed(
            self,
            delivery_id,
            claim_token,
            error,
            attempts,
            max_attempts,
            permanent=False
    ):
        now = timezone.now()

        exhausted = attempts >= max_attempts

        if permanent or exhausted:
            status = EmailDelivery.Status.DEAD
            next_attempt_at = now

            notification_status = Notification.Status.FAILED
            failure_reason = str(error)

        else:
            status = EmailDelivery.Status.FAILED
            next_attempt_at = self.calculate_retry_time(attempts)

            notification_status = Notification.Status.PENDING
            failure_reason = ""

        with transaction.atomic():
            delivery = (
                EmailDelivery.objects
                .select_for_update()
                .filter(
                    pk=delivery_id,
                    status=EmailDelivery.Status.PROCESSING,
                    processing_token=claim_token
                )
                .first()
            )
            if delivery is None:
                return False

            delivery.status = status
            delivery.next_attempt_at = next_attempt_at
            delivery.processing_started_at = None
            delivery.processing_token = None
            delivery.last_error=str(error)

            delivery.save(
                update_fields=[
                    "status",
                    "next_attempt_at",
                    "processing_started_at",
                    "processing_token",
                    "last_error",
                    "updated_at"
                ]
            )

            self._sync_notification(
                delivery=delivery,
                status=notification_status,
                sent_at=None,
                failure_reason=failure_reason
            )

            return True

    #===========================================================================
    # Implement process_delivery()
    #===========================================================================
    def process_delivery(self, delivery_id, claim_token):
        delivery = (
            EmailDelivery.objects
            .filter(
                pk=delivery_id,
                status=EmailDelivery.Status.PROCESSING,
                processing_token=claim_token
            )
            .values(
                "recipient_email",
                "subject",
                "body",
                "attempts",
                "max_attempts"
            )
            .first()
        )
        # The claim may have expired or been reclaimed.
        if delivery is None:
            return False

        try:
            result = self.provider.send(
                recipient=delivery["recipient_email"],
                subject=delivery["subject"],
                body=delivery["body"]
            )
        except PermanentEmailProviderError as exc:
            return self.mark_as_failed(
                delivery_id=delivery_id,
                claim_token=claim_token,
                error=exc,
                attempts=delivery["attempts"],
                max_attempts=delivery["max_attempts"],
                permanent=True
            )
        except TemporaryEmailProviderError as exc:
            return self.mark_as_failed(
                delivery_id=delivery_id,
                claim_token=claim_token,
                error=exc,
                attempts=delivery["attempts"],
                max_attempts=delivery["max_attempts"]
            )
        return self.mark_as_sent(
            delivery_id=delivery_id,
            claim_token=claim_token,
            result=result
        )
    #========================================================
    # Exhausted Delivery recovery
    #========================================================
    def recover_exhausted_deliveries(self):
        recovery_threshold = timezone.now() - RECOVERY_TIMEOUT
        now = timezone.now()

        with transaction.atomic():
            exhausted_deliveries = list(
                EmailDelivery.objects
                .select_for_update()
                .filter(
                    attempts__gte=F("max_attempts"),
                )
                .filter(
                    Q(status=EmailDelivery.Status.FAILED)
                    |
                    Q(
                        status=EmailDelivery.Status.PROCESSING,
                        processing_started_at__lte=recovery_threshold,
                    )
                )
            )
            for delivery in exhausted_deliveries:
                delivery.status = EmailDelivery.Status.DEAD
                delivery.processing_started_at = None
                delivery.processing_token = None
                delivery.last_error = (
                    "Maximum delivery attempts exhausted."
                )

                delivery.save(
                    update_fields=[
                        "status",
                        "processing_started_at",
                        "processing_token",
                        "last_error",
                        "updated_at"
                    ]
                )
                self._sync_notification(
                    delivery=delivery,
                    status=Notification.Status.FAILED,
                    sent_at=None,
                    failure_reason=delivery.last_error
                )
            return len(exhausted_deliveries)