from dataclasses import dataclass

from source.evidence import OccurrenceEvidence, ReadingOccurrence


@dataclass(frozen=True, slots=True)
class Placement:
    occurrence: ReadingOccurrence
    anchor: OccurrenceEvidence | None
    level: int
    edit_id: str | None
    ordinal: int


def root_placements(roots: tuple[ReadingOccurrence, ...]) -> tuple[Placement, ...]:
    return tuple(
        Placement(row, roots[position - 1].evidence if position else None, 0, None, position)
        for position, row in enumerate(roots)
    )


def edit_placements(level: int, manifest) -> tuple[Placement, ...]:
    return tuple(
        Placement(row, manifest.anchor, level, manifest.edit_id, position)
        for position, row in enumerate(manifest.inserted)
    )


def flatten(
    placements: tuple[Placement, ...], deleted: tuple[OccurrenceEvidence, ...],
) -> tuple[ReadingOccurrence, ...]:
    children: dict[OccurrenceEvidence | None, list[Placement]] = {}
    for placement in placements:
        children.setdefault(placement.anchor, []).append(placement)
    for group in children.values():
        group.sort(key=lambda item: (-item.level, item.edit_id or '', item.ordinal))
    hidden = set(deleted)
    sequence = []
    stack = list(reversed(children.get(None, ())))
    while stack:
        placement = stack.pop()
        if placement.occurrence.evidence not in hidden:
            sequence.append(placement.occurrence)
        stack.extend(reversed(children.get(placement.occurrence.evidence, ())))
    return tuple(sequence)
