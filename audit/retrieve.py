from dataclasses import dataclass

from archive.storage import ArchiveStore
from audit.ledger import load_ledger
from audit.provenance import ReportRow
from audit.totals import sum_valid_readings
from errors import NotFoundError
from identity import require_text


@dataclass(frozen=True, slots=True)
class Reconciliation:
    edition_id: str
    rows: tuple[ReportRow, ...]
    total: int


def retrieve(store: ArchiveStore, edition_id: str) -> Reconciliation:
    require_text(edition_id, 'edition id')
    rows = load_ledger(store.connection, edition_id)
    if rows is None:
        raise NotFoundError(f'unknown edition: {edition_id}')
    return Reconciliation(edition_id, rows, sum_valid_readings(rows))
