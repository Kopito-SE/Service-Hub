from datetime import timedelta
from decimal import Decimal

from unittest.mock import patch
from django.contrib.auth import get_user_model

from django.test import TestCase, override_settings
from django.utils import timezone

from rest_framework.test import APIClient
from apps.businesses.models import Business

from apps.service_catalog.models import Service
from apps.bookings.models import Booking

from apps.payments.models import Payment
from apps.payments.services.mpesa_service import MpesaPaymentService

from config.settings import ALLOWED_HOSTS


@override_settings(ALLOWED_HOSTS=['testserver', 'test.ngrok-free.dev'])
class MpesaCallbackServiceTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.owner = User.objects.create_user(
            username="mpesa-owner",
            password="test-password",
        )

        self.business = Business.objects.create(
            owner=self.owner,
            name="Test service Hub Business",
        )

        self.service = Service.objects.create(
            business=self.business,
            name="Consultation",
            price=Decimal("500.00"),
            duration_minutes=60
        )

        start = timezone.now() + timedelta(days=1)

        self.booking = Booking.objects.create(
            customer=self.owner,
            business=self.business,
            service=self.service,
            start_time=start,
            end_time=start + timedelta(minutes=60),
            price_at_booking=Decimal("500.00")
        )

        self.payment = Payment.objects.create(
            booking=self.booking,
            amount=Decimal("100.00"),
            currency="KES",
            method=Payment.Method.MPESA,
            status=Payment.Status.PENDING,
            recorded_by=self.owner,
            phone_number="254712345678",
            checkout_request_id="ws_CO_test_123",
            merchant_request_id="merchant_test_123"

        )

    def successful_callback(self):
        return {
            "Body": {
                "stkCallback": {
                    "MerchantRequestID": "merchant_test_123",
                    "CheckoutRequestID": "ws_CO_test_123",
                    "ResultCode": 0,
                    "ResultDesc": "The service request is processed successfully.",
                    "CallbackMetadata": {
                        "Item": [
                            {"Name": "Amount", "Value": 100},
                            {
                                "Name": "MpesaReceiptNumber",
                                "Value": "QAB123XYZ"
                            },
                            {
                                "Name": "PhoneNumber",
                                "Value": 254712345678,
                            },
                        ],
                    },
                },
            },
        }

    # 1.
    def test_successful_callback_marks_payment_succeeded(self):
        """Catches: TypeError, Integer Phone bug, missing transaction_reference."""

        result = MpesaPaymentService.process_callback(self.successful_callback())
        self.assertTrue(result)
        self.payment.refresh_from_db()
        self.assertEqual(self.payment.status, Payment.Status.SUCCEEDED)
        self.assertEqual(self.payment.mpesa_receipt_number, "QAB123XYZ")
        self.assertEqual(self.payment.transaction_reference, "QAB123XYZ")
        self.assertIsNotNone(self.payment.callback_received_at)

    # 2.
    def test_failed_callback_does_not_mark_payment_successful(self):
        callback = {
            "Body": {
                "stkCallback": {
                    "MerchantRequestID": "merchant_test_123",
                    "CheckoutRequestID": "ws_CO_test_123",
                    "ResultCode": 1032,
                    "ResultDesc": "Request cancelled by user."
                },
            },
        }

        result = MpesaPaymentService.process_callback(callback)

        self.assertTrue(result)

        self.payment.refresh_from_db()
        self.assertEqual(
            self.payment.status,
            Payment.Status.FAILED
        )
        self.assertEqual(
            self.payment.provider_result_code,
            "1032",
        )
        self.assertEqual(self.payment.mpesa_receipt_number, "")

    # 3.
    def test_callback_view_bypasses_allowed_hosts(self):
        """Catches: The ngrok 400 Bad Request issue."""

        client = APIClient()
        #Simulate Daraja sending the request through ngrok

        response = client.post(
            "/api/payments/payment/callback/",
            self.successful_callback(),
            format="json",
            HTTP_HOST="test.ngrok-free.dev"
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["ResultCode"], 0)

    # 4.
    def test_amount_mismatch_does_not_mark_payment_successful(self):
        callback = self.successful_callback()
        callback["Body"]["stkCallback"]["CallbackMetadata"]["Item"][0][
            "Value"
        ] = 999

        result = MpesaPaymentService.process_callback(callback)
        self.assertFalse(result)

        self.payment.refresh_from_db()
        self.assertEqual(
            self.payment.status,
            Payment.Status.PENDING
        )
    # 5.
    def test_unknown_checkout_id_is_not_processed(self):
        callback = self.successful_callback()
        callback["Body"]["stkCallback"]["CheckoutRequestID"] = (
            "unknown_checkout_id"
        )

        result = MpesaPaymentService.process_callback(callback)

        self.assertFalse(result)

        self.payment.refresh_from_db()
        self.assertEqual(
            self.payment.status,
            Payment.Status.PENDING
        )

    # 6.
    @patch("apps.payments.services.payment_service.OutboxService.record_event")
    def test_duplicate_successful_callback_is_idempotent(self, mock_record_event):
        callback_data = self.successful_callback()

        # First callback processes the payment.
        self.assertTrue(MpesaPaymentService.process_callback(callback_data))
        self.payment.refresh_from_db()

        first_receipt = self.payment.transaction_reference
        first_callback_time = self.payment.callback_received_at

        # Safaricom sends the same callback again
        self.assertTrue(MpesaPaymentService.process_callback(callback_data))
        self.payment.refresh_from_db()

        # Payment remains unchanged
        self.assertEqual(self.payment.status, Payment.Status.SUCCEEDED)
        self.assertEqual(self.payment.transaction_reference, first_receipt)
        self.assertEqual(self.payment.callback_received_at, first_callback_time)

        # The success event must only be published once
        mock_record_event.assert_called_once()

    # 7.
    def test_wrong_merchant_request_id_does_not_succeed(self):
        callback_data = self.successful_callback()

        callback_data["Body"]["stkCallback"]["MerchantRequestID"] = (
            "wrong_merchant_request_id"
        )
        result = MpesaPaymentService.process_callback(callback_data)
        self.assertFalse(result)

        self.payment.refresh_from_db()

        self.assertEqual(self.payment.status, Payment.Status.PENDING)
        self.assertEqual(self.payment.transaction_reference, "")
        self.assertIsNone(self.payment.callback_received_at)

    # 8.
    def test_wrong_phone_number_does_not_succeed(self):
        callback_data = self.successful_callback()

        metadata = callback_data["Body"]["stkCallback"]["CallbackMetadata"]["Item"]

        for item in metadata:
            if item["Name"] == "PhoneNumber":
                item["Value"] = 254700000000

        callback_phone = next(
            item["Value"]
            for item in metadata
            if item["Name"] == "PhoneNumber"
        )
        self.assertEqual(callback_phone, 254700000000)

        result = MpesaPaymentService.process_callback(callback_data)

        self.assertFalse(result)
        self.payment.refresh_from_db()

        self.assertEqual(self.payment.status, Payment.Status.PENDING)
        self.assertEqual(self.payment.transaction_reference, "")

    # 9.
    def test_duplicate_mpesa_receipt_is_rejected(self):
        callback_data = self.successful_callback()

        # Another successful payment already owns this receipt
        Payment.objects.create(
            booking=self.booking,
            amount=self.payment.amount,
            method=Payment.Method.MPESA,
            status=Payment.Status.SUCCEEDED,
            phone_number="254700000000",
            mpesa_receipt_number="QAB123XYZ",
            transaction_reference="QAB123XYZ",
            recorded_by=self.payment.recorded_by
        )

        result = MpesaPaymentService.process_callback(callback_data)
        self.assertFalse(result)
        self.payment.refresh_from_db()

        self.assertEqual(self.payment.status, Payment.Status.PENDING)
        self.assertEqual(self.payment.transaction_reference, "")
