import base64
from decimal import Decimal, ROUND_HALF_UP
import re
import requests
from django.conf import settings
from django.utils import timezone

class MpesaError(Exception):
    """Raised when a Daraja request fails or returns an invalid response"""

class MpesaClient:
    TOKEN_PATH = "/oauth/v1/generate"
    STK_PUSH_PATH = "/mpesa/stkpush/v1/processrequest"

    @staticmethod
    def _validate_configuration():
        required = {
            "MPESA_CONSUMER_KEY": settings.MPESA_CONSUMER_KEY,
            "MPESA_CONSUMER_SECRET": settings.MPESA_CONSUMER_SECRET,
            "MPESA_SHORTCODE": settings.MPESA_SHORTCODE,
            "MPESA_PASSKEY": settings.MPESA_PASSKEY,
            "MPESA_CALLBACK_URL": settings.MPESA_CALLBACK_URL
        }

        missing = [name for name, value in required.items() if not value]
        if missing:
            raise MpesaError(
                "Missing Daraja Configuration: " + ", ".join(missing)
            )

        if not settings.MPESA_CALLBACK_URL.startswith("https://"):
            raise MpesaError("The Daraja callback nust be HTTPS.")

        if settings.MPESA_ENVIRONMENT not in {"sandbox", "production"}:
            raise MpesaError("Invalid Daraja Environment")

    @staticmethod
    def normalize_phone_number(phone_number):
        digits = re.sub(r"[\s()+-]", "", str(phone_number))

        if digits.startswith("0") and len(digits) == 10:
            digits = "254" + digits[1:]

        elif digits.startswith("7") and len(digits) == 9:
            digits = "254" + digits

        elif digits.startswith("1") and len(digits) == 9:
            digits = "254" + digits

        if not re.fullmatch(r"254(?:7|1)\d{8}", digits):
            raise MpesaError(
                "Enter a valid Kenyan M-Pesa Number, e.g 2547xxxxxxxx."

            )
        return digits

    @classmethod
    def get_access_token(cls):
        cls._validate_configuration()

        url = f"{settings.MPESA_BASE_URL}{cls.TOKEN_PATH}"

        try:
            response = requests.get(
                url,
                params={"grant_type": "client_credential"},
                auth=(
                    settings.MPESA_CONSUMER_KEY,
                    settings.MPESA_CONSUMER_SECRET
                ),
                timeout=(5, 20),
            )
            response.raise_for_status()
            payload = response.json()

        except (requests.RequestException, ValueError) as exc:
            raise MpesaError(
                "Could not obtain a Daraja access token."
            ) from exc

        token = payload.get("access_token")
        if not token:
            raise MpesaError("Daraja did not return an access Token")

        return token
    @staticmethod
    def _timestamp():
        return timezone.localtime().strftime("%Y%m%d%H%M%S")

    @classmethod
    def initiate_stk_push(
            cls,
            *,
            phone_number,
            amount,
            account_reference,
            transaction_desc="Service Hub booking payment"
    ):
        cls._validate_configuration()

        phone = cls.normalize_phone_number(phone_number)
        amount_decimal = Decimal(str(amount))

        if not amount_decimal.is_finite() or amount_decimal <= 0:
            raise MpesaError("The payment amount must be positive.")

        rounded = amount_decimal.quantize(
            Decimal("1"),
            rounding=ROUND_HALF_UP
        )

        #STK Push uses whole KES amounts. Don't silently round the
        # amount and charge a different amount from the booking record

        if amount_decimal != rounded:
            raise MpesaError(
                "M-Pesa STK requires a whole number KES Amount."
            )
        amount_int = int(rounded)
        if amount_int < 1:
            raise MpesaError("The STK Push amount must be at least KES 1.")

        timestamp = cls._timestamp()
        shortcode = settings.MPESA_SHORTCODE
        password_raw = (
            f"{shortcode}{settings.MPESA_PASSKEY}{timestamp}"
        )
        password = base64.b64encode(
            password_raw.encode("utf-8")
        ).decode("utf-8")

        token = cls.get_access_token()

        payload = {
            "BusinessShortCode": shortcode,
            "Password": password,
            "Timestamp": timestamp,
            "TransactionType": "CustomerPayBillOnline",
            "Amount": amount_int,
            "PartyA": phone,
            "PartyB": shortcode,
            "PhoneNumber": phone,
            "CallBackURL": settings.MPESA_CALLBACK_URL,
            "AccountReference": str(account_reference)[:12],
            "TransactionDesc": str(transaction_desc)[:13]
        }

        url = (
            f"{settings.MPESA_BASE_URL}"
            f"{cls.STK_PUSH_PATH}"
        )

        try:
            response = requests.post(
                url,
                json=payload,
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json"
                },
                timeout=(5, 30),
            )
            response.raise_for_status()
            result = response.json()

        except (requests.RequestException, ValueError) as exc:

            # The request may have reached Safaricom even if our client
            # timed out. The caller must not blindly retry and create
            # another STK prompt.

            raise MpesaError(
                "The stk outcome is unknown Check its status "
                "before retrying"
            ) from exc

        if not result.get("CheckoutRequestID"):
            raise MpesaError(
                "Daraja did not return a checkout request Identifier"
            )
        return result














