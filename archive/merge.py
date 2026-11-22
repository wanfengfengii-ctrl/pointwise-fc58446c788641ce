from archive.dependencies import AuthorLineage
from archive.occurrences import place_insertions
from errors import ValidationError
from exchange.manifest import Manifest
from revision.ranges import checked_range
from source.evidence import ReadingOccurrence


def apply_current(
    roots: tuple[ReadingOccurrence, ...], current: tuple[ReadingOccurrence, ...],
    lineage: AuthorLineage, manifest: Manifest,
) -> tuple[ReadingOccurrence, ...]:
    amendment = manifest.amendment
    if not lineage.ancestors:
        start, end = checked_range(len(roots), amendment.start, amendment.delete_count)
        deleted = tuple(row.evidence for row in roots[start:end])
        anchor = roots[start - 1].evidence if start else None
        if deleted != manifest.deleted or anchor != manifest.anchor:
            raise ValidationError('package evidence does not match the root revision')
    start, end = checked_range(len(current), amendment.start, amendment.delete_count)
    remaining = current[:start] + current[end:]
    return place_insertions(remaining, manifest.anchor, manifest.inserted)
