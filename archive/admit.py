from archive.dependencies import check_child_binding, resolve_parent
from archive.merge import check_author_evidence, merge_view
from archive.publish import publish_edition
from archive.storage import AdmissionReceipt, ArchiveStore
from errors import ConflictError, NotFoundError, ValidationError
from exchange.codec import decode_package
from identity import fingerprint, require_text


def admit(store: ArchiveStore, recording_id: str, wire: bytes) -> AdmissionReceipt:
    require_text(recording_id, 'recording id')
    package = decode_package(wire)
    manifest = package.manifest
    with store.transaction():
        root = store.load_root(recording_id)
        if root is None:
            raise NotFoundError(f'unknown archive recording: {recording_id}')
        recording = root.recording
        if manifest.recording_key != recording.key:
            raise ValidationError('package belongs to another recording')

        previous = store.find_admission(recording.key, package_id=package.package_id)
        if previous is None:
            previous = store.find_admission(recording.key, edit_id=manifest.edit_id)
        if previous is not None:
            receipt, prior_wire = previous
            if receipt.package_id != package.package_id or prior_wire != package.wire:
                raise ConflictError(f'conflicting package for edit {manifest.edit_id}')
            return receipt

        accepted = tuple(decode_package(body) for body in store.load_accepted(recording.key))
        by_child = {item.manifest.child_id: item.manifest for item in accepted}
        check_child_binding(root.revision_id, manifest, by_child)
        lineage = resolve_parent(root.revision_id, manifest.parent_id, by_child)
        check_author_evidence(root.revision_id, recording.occurrences(), lineage, manifest)
        manifests = tuple(item.manifest for item in accepted) + (manifest,)
        rows = merge_view(root.revision_id, recording.occurrences(), manifests)
        package_ids = [item.package_id for item in accepted]
        package_ids.append(package.package_id)
        edition_id = publish_edition(store, recording, package_ids, rows)
        receipt_id = fingerprint('admission', [recording.key, package.package_id, edition_id])
        receipt = AdmissionReceipt(receipt_id, package.package_id, manifest.edit_id, edition_id)
        store.record_admission(recording.key, manifest.child_id, receipt, package.wire)
        return receipt
