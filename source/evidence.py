from dataclasses import dataclass

from errors import ValidationError
from identity import expect_fields, expect_list, fingerprint, require_text
from source.readings import Reading, parse_reading


@dataclass(frozen=True, slots=True)
class OccurrenceEvidence:
    recording_key: str
    edit_id: str | None
    ordinal: int

    def __post_init__(self) -> None:
        require_text(self.recording_key, 'evidence recording key')
        if self.edit_id is not None:
            require_text(self.edit_id, 'evidence edit id')
        if type(self.ordinal) is not int or self.ordinal < 0:
            raise ValidationError('evidence ordinal must be a nonnegative integer')

    @property
    def kind(self) -> str:
        return 'root' if self.edit_id is None else 'edit'

    @property
    def occurrence_id(self) -> str:
        return fingerprint('occ', [self.recording_key, self.edit_id, self.ordinal])

    def as_data(self) -> dict:
        return {
            'recording_key': self.recording_key,
            'kind': self.kind,
            'edit_id': self.edit_id,
            'ordinal': self.ordinal,
        }

    @classmethod
    def from_data(cls, raw: object) -> 'OccurrenceEvidence':
        data = expect_fields(raw, {'recording_key', 'kind', 'edit_id', 'ordinal'}, 'evidence')
        evidence = cls(data['recording_key'], data['edit_id'], data['ordinal'])
        if data['kind'] != evidence.kind:
            raise ValidationError('evidence kind does not match its source')
        return evidence


@dataclass(frozen=True, slots=True)
class ReadingOccurrence:
    reading: Reading
    evidence: OccurrenceEvidence

    @property
    def occurrence_id(self) -> str:
        return self.evidence.occurrence_id

    def as_data(self) -> dict:
        return {'reading': self.reading.as_data(), 'evidence': self.evidence.as_data()}

    @classmethod
    def from_data(cls, raw: object) -> 'ReadingOccurrence':
        data = expect_fields(raw, {'reading', 'evidence'}, 'occurrence')
        return cls(parse_reading(data['reading']), OccurrenceEvidence.from_data(data['evidence']))


def root_occurrences(recording_key: str, rows: tuple[Reading, ...]) -> tuple[ReadingOccurrence, ...]:
    return tuple(
        ReadingOccurrence(reading, OccurrenceEvidence(recording_key, None, position))
        for position, reading in enumerate(rows)
    )


def parse_occurrences(raw: object) -> tuple[ReadingOccurrence, ...]:
    return tuple(ReadingOccurrence.from_data(row) for row in expect_list(raw, 'occurrences'))
