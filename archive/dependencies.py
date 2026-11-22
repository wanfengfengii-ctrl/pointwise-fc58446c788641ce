from collections.abc import Mapping
from dataclasses import dataclass

from errors import ConflictError, MissingParentError, ValidationError
from exchange.manifest import Manifest
from revision.edits import work_number
from revision.freeze import child_revision_number


@dataclass(frozen=True, slots=True)
class AuthorLineage:
    ancestors: tuple[Manifest, ...]

    @property
    def level(self) -> int:
        return len(self.ancestors) + 1


def resolve_parent(
    root_revision_id: str, parent_id: str, by_child: Mapping[str, Manifest],
) -> AuthorLineage:
    ancestors = []
    seen = set()
    revision_id = parent_id
    while revision_id != root_revision_id:
        if revision_id in seen:
            raise ValidationError('cyclic author parent chain')
        seen.add(revision_id)
        parent = by_child.get(revision_id)
        if parent is None:
            raise MissingParentError(revision_id)
        ancestors.append(parent)
        revision_id = parent.parent_id
    return AuthorLineage(tuple(reversed(ancestors)))


def check_child_binding(
    root_revision_id: str, manifest: Manifest, by_child: Mapping[str, Manifest],
) -> None:
    expected = child_revision_number(work_number(manifest.recording_key, manifest.amendment))
    if manifest.child_id != expected or manifest.child_id == root_revision_id:
        raise ValidationError('frozen child does not bind the supplied amendment')
    if manifest.child_id in by_child:
        raise ConflictError(f'frozen child is already bound: {manifest.child_id}')
