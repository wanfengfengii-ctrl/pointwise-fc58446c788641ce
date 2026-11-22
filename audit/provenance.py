from dataclasses import dataclass

from source.evidence import OccurrenceEvidence, ReadingOccurrence


@dataclass(frozen=True, slots=True)
class ReportRow:
    position: int
    occurrence: ReadingOccurrence

    @property
    def name(self) -> str:
        return self.occurrence.reading.name

    @property
    def value(self) -> int | None:
        return self.occurrence.reading.value

    @property
    def evidence(self) -> OccurrenceEvidence:
        return self.occurrence.evidence

    @property
    def occurrence_id(self) -> str:
        return self.occurrence.occurrence_id

    @property
    def missing(self) -> bool:
        return self.value is None


def report_rows(rows: tuple[ReadingOccurrence, ...]) -> tuple[ReportRow, ...]:
    return tuple(ReportRow(position, row) for position, row in enumerate(rows))
