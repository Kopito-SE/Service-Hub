from unittest.mock import patch, Mock
from django.test import TestCase, override_settings
from apps.payments.providers.mpesa import MpesaClient, MpesaError
from config.settings import MPESA_BASE_URL, MPESA_CONSUMER_KEY

@override_settings(
    MPESA_ENVIRONMENT="sandbox",
    MPESA_BASE_URL="https://sandbox.safaricom.co.ke",
    MPESA_CONSUMER_KEY="test-consumer-key",
    MPESA_CONSUMER_SECRET="test-consumer-secret",
    MPESA_SHORTCODE="174379",
    MPESA_PASSKEY="test-passkey",
    MPESA_CALLBACK_URL="https://example.ngrok-free.app/api/payments/mpesa/callback/",
)

class MpesaClientTest(TestCase):
    def test_normalizes_kenyan_phone_numbers(self):
        self.assertEqual(
            MpesaClient.normalize_phone_number("0712345678"),
            "254712345678"
        )

        self.assertEqual(
            MpesaClient.normalize_phone_number("712345678"),
            "254712345678"
        )

        self.assertEqual(
            MpesaClient.normalize_phone_number("+254712345678"),
            "254712345678"
        )

    def test_rejects_invalid_phone_number(self):
        with self.assertRaises(MpesaError):
            MpesaClient.normalize_phone_number("12345")

    @patch("apps.payments.providers.mpesa.requests.post")
    @patch("apps.payments.providers.mpesa.requests.get")
    def test_initiates_stk_push(self, mock_get, mock_post):
        token_response = Mock()
        token_response.json.return_value = {
            "access_token": "fake-access-token"
        }
        token_response.raise_for_status.return_value = None
        mock_get.return_value = token_response

        stk_response = Mock()
        stk_response.json.return_value = {
            "ResponseCode": "0",
            "ResponseDescription": "Success. Request accepted for processing",
            "MerchantRequestID": "merchant-123",
            "CheckoutRequestID": "checkout-123",
        }
        stk_response.raise_for_status.return_value = None
        mock_post.return_value = stk_response  # ← was missing

        result = MpesaClient.initiate_stk_push(  # ← was missing
            phone_number="0712345678",
            amount=100,
            account_reference="SH123",
        )

        self.assertEqual(result["CheckoutRequestID"], "checkout-123")

        mock_get.assert_called_once()
        mock_post.assert_called_once()

        request_kwargs = mock_post.call_args.kwargs
        payload = request_kwargs["json"]

        self.assertEqual(payload["Amount"], 100)
        self.assertEqual(payload["PhoneNumber"], "254712345678")
        self.assertEqual(payload["PartyA"], "254712345678")
        self.assertEqual(
            payload["CallBackURL"],
            "https://example.ngrok-free.app/api/payments/mpesa/callback/",
        )
        self.assertEqual(
            request_kwargs["headers"]["Authorization"],
            "Bearer fake-access-token"
        )