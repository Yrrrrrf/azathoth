class AzathothBaseError(Exception):
    """Base exception for all Azathoth errors."""

    pass


class LLMError(AzathothBaseError):
    """Raised when an LLM call fails."""

    pass


class I18nError(AzathothBaseError):
    """Base exception for i18n errors."""

    pass


class ConfigParseError(I18nError):
    """Raised when inlang config cannot be parsed."""

    pass


class TranslationError(I18nError):
    """Raised when translation logic fails."""

    pass


class RegistryError(I18nError):
    """Raised when registry ops fail."""

    pass
