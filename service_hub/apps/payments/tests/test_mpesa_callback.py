
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from apps.businesses.models import Business
from apps.service_catalog.models import Service
from apps.bookings.models import Booking
from apps.payments.models import Payment
from apps.payments.services import MpesaPaymentService


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
                            {"name": "Amount", "Value": 100},
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