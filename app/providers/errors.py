class ProviderError(RuntimeError):
    """A safe, user-visible error without raw request URLs or credentials."""
