from source.evidence import OccurrenceEvidence, ReadingOccurrence


def place_insertions(
    rows: tuple[ReadingOccurrence, ...], anchor: OccurrenceEvidence | None,
    inserted: tuple[ReadingOccurrence, ...],
) -> tuple[ReadingOccurrence, ...]:
    if not inserted:
        return rows
    if anchor is None:
        return inserted + rows
    for position, row in enumerate(rows, 1):
        if row.evidence == anchor:
            return rows[:position] + inserted + rows[position:]
    return rows + inserted
