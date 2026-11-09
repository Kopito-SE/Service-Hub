from unittest.mock import MagicMock, patch
from django.test import SimpleTestCase
from apps.notifications.email.worker import process_pending_emails

class EmailWorkerTests(SimpleTestCase):
    @patch("apps.notifications.email.worker.EmailProviderFactory.create")
    @patch("apps.notifications.email.worker.EmailDeliveryProcessor")
    def test_worker_processes_available_deliveries(self, processor_class, factory_create):

        provider = MagicMock()
        factory_create.return_value = provider

        processor = processor_class.return_value
        processor.claim_delivery.side_effect = [
            (1, "token-1"),
            (2, "token-2"),
            None
        ]
        result = process_pending_emails()

        self.assertEqual(result, 2)
        factory_create.assert_called_once_with()

        processor_class.assert_called_once_with(
            provider=provider
        )

        processor.recover_exhausted_deliveries.assert_called_once_with()

        self.assertEqual(
            processor.process_delivery.call_count,
            2
        )
    @patch("apps.notifications.email.worker.EmailProviderFactory.create")
    @patch("apps.notifications.email.worker.EmailDeliveryProcessor")
    def test_worker_respects_batch_limit(
            self,
            processor_class,
            factory_create
    ):
        processor = processor_class.return_value

        processor.claim_delivery.side_effect = [
            (1, "token-1"),
            (2, "token-2"),
            (3, "token-3")
        ]
        result = process_pending_emails(limit=2)
        self.assertEqual(result, 2)

        self.assertEqual(processor.process_delivery.call_count, 2)
        self.assertEqual(processor.claim_delivery.call_count, 2)

    @patch("apps.notifications.email.worker.EmailProviderFactory.create")
    @patch("apps.notifications.email.worker.EmailDeliveryProcessor")
    def test_worker_returns_zero_when_no_delivery_is_available(self, processor_class, factory_create):

        processor = processor_class.return_value
        processor.claim_delivery.return_value = None

        result = process_pending_emails()
        self.assertEqual(result, 0)

        processor.recover_exhausted_deliveries.assert_called_once_with()
        processor.process_delivery.assert_not_called()

    def test_worker_rejects_invalid_batch_limit(self):
        with self.assertRaises(ValueError):
            process_pending_emails(limit=0)
