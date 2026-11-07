class EmailProviderError(Exception):
    """Base exception for email provider failures."""

class TemporaryEmailProviderError(EmailProviderError):
    """A temporary failure that may succeed on retry."""

class PermanentEmailProviderError(EmailProviderError):
    """A failure that should not be retried"""