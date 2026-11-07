from abc import ABC, abstractmethod
from dataclasses import dataclass

@dataclass(frozen=True)
class EmailSendResult:
    provider_message_id: str | None = None

class EmailProvider(ABC):

    @abstractmethod
    def send(
            self,
            recipient: str,
            subject: str,
            body: str
    ) -> EmailSendResult :
        """
        Send an email through the configured provider.

        Return:
             EmailSendResult containing provider delivery metadata.
        Raises:
             An exception if the provider cannot accept the email.
        """
        pass