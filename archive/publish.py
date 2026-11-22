from collections.abc import Iterable

from archive.storage import ArchiveStore
from audit.ledger import store_ledger
from audit.provenance import report_rows
from identity import fingerprint
from source.evidence import ReadingOccurrence
from source.recordings import Recording


def edition_number(recording_key: str, package_ids: Iterable[str]) -> str:
    return fingerprint('edition', [recording_key, sorted(set(package_ids))])


def publish_edition(
    store: ArchiveStore, recording: Recording, package_ids: Iterable[str],
    rows: tuple[ReadingOccurrence, ...],
) -> str:
    number = edition_number(recording.key, package_ids)
    store.save_edition(recording.key, number)
    store_ledger(store.connection, number, report_rows(rows))
    store.set_current(recording.recording_id, number)
    return number
