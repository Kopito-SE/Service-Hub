from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy import True_


@dataclass(frozen=True)
class BookingCreated:
    booking_id: int
    customer_id: int
    service_name: str

@dataclass(frozen=True)
class BookingCancelled:
    booking_id: int
    customer_id: int
    service_name: str

@dataclass(frozen=True)
class PaymentSucceeded:
    payment_id: int
    booking_id: int
    customer_id: int
    amount: Decimal

@dataclass(frozen=True)
class PaymentFailed:
    payment_id: int
    booking_id: int
    customer_id: int
    amount: Decimal