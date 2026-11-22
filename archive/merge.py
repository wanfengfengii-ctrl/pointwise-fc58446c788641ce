from archive.dependencies import AuthorLineage, edit_levels
from archive.occurrences import edit_placements, flatten, root_placements
from errors import ValidationError
from exchange.manifest import Manifest
from revision.ranges import checked_range
from source.evidence import ReadingOccurrence


def merge_view(
    root_revision_id: str, roots: tuple[ReadingOccurrence, ...], manifests: tuple[Manifest, ...],
) -> tuple[ReadingOccurrence, ...]:
    levels = edit_levels(root_revision_id, manifests)
    placements = list(root_placements(roots))
    deleted = []
    for manifest in manifests:
        placements.extend(edit_placements(levels[manifest.edit_id], manifest))
        deleted.extend(manifest.deleted)
    return flatten(tuple(placements), tuple(deleted))


def check_author_evidence(
    root_revision_id: str, roots: tuple[ReadingOccurrence, ...],
    lineage: AuthorLineage, manifest: Manifest,
) -> None:
    parent_view = merge_view(root_revision_id, roots, lineage.ancestors)
    amendment = manifest.amendment
    start, end = checked_range(len(parent_view), amendment.start, amendment.delete_count)
    deleted = tuple(row.evidence for row in parent_view[start:end])
    anchor = parent_view[start - 1].evidence if start else None
    if deleted != manifest.deleted or anchor != manifest.anchor:
        raise ValidationError('package evidence does not match the author parent revision')
