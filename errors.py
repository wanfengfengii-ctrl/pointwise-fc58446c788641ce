class ArchiveError(Exception):
    """A rejected recording, amendment, exchange, or archive operation."""


class ValidationError(ArchiveError, ValueError):
    """The supplied input or evidence fails the business contract."""


class ConflictError(ArchiveError):
    """An existing identifier is bound to different content."""


class NotFoundError(ArchiveError):
    """The requested persistent record does not exist."""


class MissingParentError(ArchiveError):
    def __init__(self, revision_id: str):
        self.revision_id = revision_id
        super().__init__(f'author parent has not been admitted: {revision_id}')
