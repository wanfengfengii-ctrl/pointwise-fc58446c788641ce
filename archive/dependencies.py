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


def edit_levels(root_revision_id: str, manifests: tuple[Manifest, ...]) -> dict[str, int]:
    by_child = {manifest.child_id: manifest for manifest in manifests}
    levels: dict[str, int] = {}
    for manifest in manifests:
        chain = []
        seen = set()
        current = manifest
        while current.edit_id not in levels:
            if current.edit_id in seen:
                raise ValidationError('cyclic author parent chain')
            seen.add(current.edit_id)
            chain.append(current)
            if current.parent_id == root_revision_id:
                levels[current.edit_id] = 0
            else:
                parent = by_child.get(current.parent_id)
                if parent is None:
                    raise MissingParentError(current.parent_id)
                current = parent
        level = levels[current.edit_id]
        for item in reversed(chain):
            level += 1
            levels[item.edit_id] = level
    return levels


def check_child_binding(
    root_revision_id: str, manifest: Manifest, by_child: Mapping[str, Manifest],
) -> None:
    expected = child_revision_number(work_number(manifest.recording_key, manifest.amendment))
    if manifest.child_id != expected or manifest.child_id == root_revision_id:
        raise ValidationError('frozen child does not bind the supplied amendment')
    if manifest.child_id in by_child:
        raise ConflictError(f'frozen child is already bound: {manifest.child_id}')
