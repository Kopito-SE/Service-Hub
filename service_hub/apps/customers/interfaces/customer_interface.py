

from dataclasses import dataclass

from django.core.exceptions import ValidationError

from apps.customers.services import CustomerService

class CustomerInterfaceError(Exception):
    """Raised when a customer operation cannot be completed."""

    # noinspection PyCompatibility
    def __init__(self, messages: list[str]):
        self.messages = messages
        super().__init__("; ".join(messages))

@dataclass(frozen=True)
class CustomerDTO:
    """
    Public representation of a Customer.

    Other components receive this object instead of
    depending directly on the Customer Django model.
    """

    id: int
    full_name: str
    email: str
    phone_number: str


class CustomerInterface:
    """
    Public entry point for interacting with the Customers component.
    """

    @staticmethod
    def create_or_get_customer(
        *,
        full_name: str,
        email: str,
        phone_number: str,
    ) -> tuple[CustomerDTO, bool]:

        try:
            customer, created =  CustomerService.create_or_get_customer(
                    full_name=full_name,
                    email=email,
                    phone_number=phone_number,
                )


        except ValidationError as exc:
            raise CustomerInterfaceError(exc.messages) from exc


        customer_dto = CustomerDTO(
            id=customer.pk,
            full_name=customer.full_name,
            email=customer.email,
            phone_number=customer.phone_number,
        )

        return customer_dto, created



