from django.test import SimpleTestCase, override_settings
from apps.notifications.email.providers.factory import (
     EmailProviderFactory
)
from apps.notifications.email.providers.smtp import SMTPProvider

from config.settings import EMAIL_PROVIDER_CLASS


class EmailProviderFactoryTest(SimpleTestCase):
    @override_settings(
        EMAIL_PROVIDER_CLASS=(
            "apps.notifications.email.providers.smtp.SMTPProvider"
        )
    )

    def test_factory_creates_configured_smtp_provider(self):
        provider = EmailProviderFactory.create()
        self.assertIsInstance(provider, SMTPProvider)

    @override_settings(EMAIL_PROVIDER_CLASS="builtins.str")
    def test_factory_rejects_invalid_provider_class(self):

        with self.assertRaises(TypeError):
            EmailProviderFactory.create()

    @override_settings(EMAIL_PROVIDER_CLASS="builtins.dict")
    def test_factory_rejects_class_not_implementing_contract(self):

        with self.assertRaises(TypeError):
            EmailProviderFactory.create()