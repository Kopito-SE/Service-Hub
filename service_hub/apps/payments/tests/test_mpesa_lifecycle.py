from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch
from django.contrib.auth import get_user_model
from django.test import TestCase

from django.utils import timezone

from apps.businesses.models import Business
from apps.service_catalog.models import Service
from apps.bookings.models import Booking
from apps.payments.models import Payment
from apps.payments.services.mpesa_service import MpesaPaymentService
from apps.payments.providers.mpesa import MpesaError

class MpesaPaymentLifecycleTests(TestCase):
    def setUp(self):
        User = get_user_model()

        self.owner = User.objects.create_user(
            username="lifecycle-owner",
            password="test-password"
        )
        self.business = Business.objects.create(
            owner=self.owner,
            name="LifeCycle Test Business"
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
    # 1.Test Successful stk payment Lifecycle
    @patch("apps.payments.services.mpesa_service.MpesaClient.initiate_stk_push")
    def test_complete_stk_payment_lifecycle(self, mock_stk_push):

        # 1. Simulate a successful Daraja STK initiation response.
        mock_stk_push.return_value = {
            "ResponseCode": "0",
            "ResponseDescription": "Success. Request Accepted for processing",
            "MerchantRequestID": "merchant_lifecycle_123",
            "CheckoutRequestID": "checkout_lifecycle_123"
        }

        # 2. Initiate the payment
        payment = MpesaPaymentService.initiate_payment(
            booking_id=self.booking.pk,
            amount=Decimal("100.00"),
            phone_number="254712345678",
            recorded_by=self.owner
        )

        # 3. Verify the initial payment
        self.assertEqual(payment.status, Payment.Status.PENDING)
        self.assertEqual(payment.amount, Decimal("100.00"))
        self.assertEqual(payment.phone_number, "254712345678")

        # 4. Verify the provider identifiers were saved
        self.assertEqual(
            payment.checkout_request_id,
            "checkout_lifecycle_123"
        )

        self.assertEqual(
            payment.merchant_request_id,
            "merchant_lifecycle_123"
        )
        mock_stk_push.assert_called_once()

        # 5. Simulate the customer authorizing the STK request
        callback_data = {
            "Body": {
                "stkCallback": {
                    "MerchantRequestID": "merchant_lifecycle_123",
                    "CheckoutRequestID": "checkout_lifecycle_123",
                    "ResultCode": 0,
                    "ResultDesc": "The service request is processed successfully.",
                    "CallbackMetadata": {
                        "Item": [
                            {"Name": "Amount", "Value": 100},
                            {
                                "Name": "MpesaReceiptNumber",
                                "Value": "LIFECYCLE123",
                            },
                            {
                                "Name": "PhoneNumber",
                                "Value": 254712345678,
                            },
                        ]
                    },
                }
            }
        }

        # 6. Process the callback.
        with patch("apps.payments.services.payment_service.OutboxService.record_event") as mock_record_event:
            result = MpesaPaymentService.process_callback(callback_data)

            payment.refresh_from_db()

            print("\n--- CALLBACK DEBUG ---")
            print("Result:", result)
            print("Payment status:", payment.status)
            print("Checkout ID:", payment.checkout_request_id)
            print("Merchant ID:", payment.merchant_request_id)
            print("Payment phone:", payment.phone_number)
            print("Receipt:", payment.mpesa_receipt_number)
            print("Provider description:", payment.provider_result_description)
            print("----------------------\n")

            self.assertTrue(result)

            # PaymentSucceeded must be published exactly once.
            mock_record_event.assert_called_once()

            event = mock_record_event.call_args.args[0]
            self.assertEqual(event.payment_id, payment.pk)

        # 7. Verify the same Payment was updated.
        payment.refresh_from_db()

        self.assertEqual(payment.status, Payment.Status.SUCCEEDED)
        self.assertEqual(
            payment.mpesa_receipt_number,
            "LIFECYCLE123"
        )
        self.assertIsNotNone(payment.callback_received_at)

    # 2.
    @patch("apps.payments.services.mpesa_service.MpesaClient.initiate_stk_push")
    def test_cancelled_stk_payment_lifecycle(self, mock_stk_push):
        # 1. Simulate successful STK initiation.
        mock_stk_push.return_value = {
            "ResponseCode": "0",
            "ResponseDescription": "Success. Request accepted for processing",
            "MerchantRequestID": "merchant_cancel_123",
            "CheckoutRequestID": "checkout_cancel_123",
        }

        # 2. Initiate the payment.
        payment = MpesaPaymentService.initiate_payment(
            booking_id=self.booking.pk,
            amount=Decimal("100.00"),
            phone_number="254712345678",
            recorded_by=self.owner,
        )

        self.assertEqual(payment.status, Payment.Status.PENDING)

        # 3. Simulate the customer cancelling the STK prompt.
        callback_data = {
            "Body": {
                "stkCallback": {
                    "MerchantRequestID": "merchant_cancel_123",
                    "CheckoutRequestID": "checkout_cancel_123",
                    "ResultCode": 1032,
                    "ResultDesc": "Request cancelled by user.",
                }
            }
        }

        # 4. Process the failure callback.
        with patch(
            "apps.payments.services.payment_service.OutboxService.record_event"
        ) as mock_record_event:
            result = MpesaPaymentService.process_callback(callback_data)

            self.assertTrue(result)
            mock_record_event.assert_called_once()

            event = mock_record_event.call_args.args[0]

            self.assertEqual(event.payment_id, payment.pk)

        # 5. Verify the payment was marked failed.
        payment.refresh_from_db()

        self.assertEqual(payment.status, Payment.Status.FAILED)
        self.assertEqual(payment.mpesa_receipt_number, "")
        self.assertIsNotNone(payment.callback_received_at)
        self.assertEqual(payment.provider_result_code, "1032")

    # 3.
    @patch("apps.payments.services.mpesa_service.MpesaClient.initiate_stk_push")
    def test_stk_initiation_error_keeps_payment_pending(self, mock_stk_push):

        # Simulate an Ambiguous Daraja timeout
        mock_stk_push.side_effect = MpesaError(
            "The STK outcome is unknown. Check its status before retrying"
        )
        # Initiation should raise the provider error
        with self.assertRaises(MpesaError):
            MpesaPaymentService.initiate_payment(
                booking_id=self.booking.pk,
                amount=Decimal("100.00"),
                phone_number="254712345678",
                recorded_by=self.owner
            )

        # Retrieve the payment created before the provider request
        payment = Payment.objects.get(booking=self.booking)

        # The payment must remain pending for reconciliation
        self.assertEqual(payment.status, Payment.Status.PENDING)

        # The provider error should be saved
        self.assertIn(
            "outcome is unknown",
            payment.provider_result_description.lower()
        )
        # Only one STK request should have been attempted
        mock_stk_push.assert_called_once()

        # No provider checkout ID was received
        self.assertIn(payment.checkout_request_id,(None, "") )
