from dataclasses import dataclass
from decimal import Decimal

@dataclass(frozen=True)
class BookingCreated:
    booking_id: int
    customer_id: int | None
    guest_customer_id: int | None
    service_name: str

@dataclass(frozen=True)
class BookingCancelled:
    booking_id: int
    customer_id: int | None
    guest_customer_id: int | None
    service_name: str

@dataclass(frozen=True)
class BookingConfirmed:
    booking_id: int
    customer_id: int | None
    guest_customer_id: int | None
    service_name: str

@dataclass(frozen=True)
class PaymentSucceeded:
    payment_id: int
    booking_id: int
    customer_id: int | None
    guest_customer_id: int | None
    amount: Decimal

@dataclass(frozen=True)
class PaymentFailed:
    payment_id: int
    booking_id: int
    customer_id: int | None
    guest_customer_id: int | None
    amount: Decimal