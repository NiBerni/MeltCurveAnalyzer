class PCRError(Exception):
    """Base class for use case errors."""

    pass


class TemplateNotFoundError(PCRError):
    """Error raised when a template is not found."""

    pass


class ControlValidationFailedError(PCRError):
    """Error raised when control validation fails."""

    pass


class DataParsingError(PCRError):
    """Error raised when data parsing fails."""

    pass
