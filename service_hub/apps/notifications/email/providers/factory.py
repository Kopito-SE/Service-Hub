from django.conf import settings
from django.utils.module_loading import import_string
from apps.notifications.email.providers.base import EmailProvider

class EmailProviderFactory:
    @staticmethod
    def create() -> EmailProvider:
        provider_path = settings.EMAIL_PROVIDER_CLASS

        provider_class = import_string(provider_path)

        if not isinstance(provider_class, type):
            raise TypeError(
                "Configured email provider must be a class."
            )

        if not issubclass(provider_class, EmailProvider):
            raise TypeError(
                "Configured email provider must implement "
                "EmailProvider."
            )

        return provider_class()
