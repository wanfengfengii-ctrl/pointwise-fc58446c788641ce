from dataclasses import dataclass

from errors import ValidationError
from identity import expect_fields, expect_list, fingerprint, require_text
from revision.edits import Amendment, inserted_occurrences
from source.evidence import OccurrenceEvidence, ReadingOccurrence, parse_occurrences


@dataclass(frozen=True, slots=True)
class Manifest:
    recording_key: str
    child_id: str
    amendment: Amendment
    deleted: tuple[OccurrenceEvidence, ...]
    anchor: OccurrenceEvidence | None
    inserted: tuple[ReadingOccurrence, ...]
    receipt_id: str

    @property
    def parent_id(self) -> str:
        return self.amendment.parent_id

    @property
    def edit_id(self) -> str:
        return self.amendment.edit_id

    def as_data(self) -> dict:
        return {
            'recording_key': self.recording_key,
            'child_id': self.child_id,
            'amendment': self.amendment.as_data(),
            'deleted': [item.as_data() for item in self.deleted],
            'anchor': None if self.anchor is None else self.anchor.as_data(),
            'inserted': [item.as_data() for item in self.inserted],
            'receipt_id': self.receipt_id,
        }

    @classmethod
    def from_data(cls, raw: object) -> 'Manifest':
        data = expect_fields(
            raw, {'recording_key', 'child_id', 'amendment', 'deleted', 'anchor', 'inserted', 'receipt_id'},
            'manifest',
        )
        anchor = data['anchor']
        manifest = cls(
            data['recording_key'], data['child_id'], Amendment.from_data(data['amendment']),
            tuple(OccurrenceEvidence.from_data(item) for item in expect_list(data['deleted'], 'deleted evidence')),
            None if anchor is None else OccurrenceEvidence.from_data(anchor),
            parse_occurrences(data['inserted']), data['receipt_id'],
        )
        validate_manifest(manifest)
        return manifest


def issue_number(recording_key: str, edit_id: str) -> str:
    return fingerprint('issue', [recording_key, edit_id])


def build_manifest(
    recording_key: str, child_id: str, amendment: Amendment,
    deleted: tuple[OccurrenceEvidence, ...], anchor: OccurrenceEvidence | None,
) -> Manifest:
    manifest = Manifest(
        recording_key, child_id, amendment, deleted, anchor,
        inserted_occurrences(recording_key, amendment), issue_number(recording_key, amendment.edit_id),
    )
    validate_manifest(manifest)
    return manifest


def validate_manifest(manifest: Manifest) -> None:
    require_text(manifest.recording_key, 'recording key')
    require_text(manifest.child_id, 'child revision id')
    if manifest.child_id == manifest.parent_id:
        raise ValidationError('child and parent revision are identical')
    if manifest.receipt_id != issue_number(manifest.recording_key, manifest.edit_id):
        raise ValidationError('issue receipt does not match the recording and edit')
    if len(manifest.deleted) != manifest.amendment.delete_count:
        raise ValidationError('deletion evidence count differs from the amendment')
    if len(set(manifest.deleted)) != len(manifest.deleted):
        raise ValidationError('deletion evidence repeats an occurrence')
    if (manifest.anchor is None) != (manifest.amendment.start == 0):
        raise ValidationError('anchor does not agree with the amendment position')
    if manifest.anchor is not None and manifest.anchor in manifest.deleted:
        raise ValidationError('anchor also appears in deletion evidence')
    references = manifest.deleted if manifest.anchor is None else (*manifest.deleted, manifest.anchor)
    if any(item.recording_key != manifest.recording_key for item in references):
        raise ValidationError('edit evidence belongs to a different recording')
    if manifest.inserted != inserted_occurrences(manifest.recording_key, manifest.amendment):
        raise ValidationError('inserted readings or their evidence differ from the amendment')
