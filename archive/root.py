from archive.publish import edition_number, publish_edition
from archive.storage import ArchiveStore, RootState
from errors import ConflictError, ValidationError
from revision.freeze import root_revision_number
from source.recordings import Recording


def open_archive(store: ArchiveStore, recording: Recording, root_revision_id: str) -> str:
    if not isinstance(recording, Recording) or root_revision_id != root_revision_number(recording.key):
        raise ValidationError('root revision does not match the supplied recording')
    with store.transaction():
        old_root = store.load_root(recording.recording_id)
        if old_root is not None:
            if old_root.recording != recording or old_root.revision_id != root_revision_id:
                raise ConflictError(f'archive root already exists for {recording.recording_id}')
            return old_root.initial_edition_id
        initial = edition_number(recording.key, ())
        store.store_root(RootState(recording, root_revision_id, initial))
        return publish_edition(store, recording, (), recording.occurrences())
