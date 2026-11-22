import json
import sqlite3
from dataclasses import dataclass

from audit.ledger import initialize_ledger
from database import DatabasePath, connect, transaction
from errors import NotFoundError
from identity import canonical_json
from source.recordings import Recording


@dataclass(frozen=True, slots=True)
class RootState:
    recording: Recording
    revision_id: str
    initial_edition_id: str


@dataclass(frozen=True, slots=True)
class AdmissionReceipt:
    receipt_id: str
    package_id: str
    edit_id: str
    edition_id: str


class ArchiveStore:
    def __init__(self, path: DatabasePath):
        self.connection = connect(path)
        try:
            self.initialize_schema()
        except BaseException:
            self.connection.close()
            raise

    def __enter__(self) -> 'ArchiveStore':
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        self.close()

    def close(self) -> None:
        self.connection.close()

    def initialize_schema(self) -> None:
        self.connection.executescript('''
            CREATE TABLE IF NOT EXISTS archive_roots (
                recording_id TEXT PRIMARY KEY,
                recording_key TEXT NOT NULL UNIQUE,
                revision_id TEXT NOT NULL UNIQUE,
                initial_edition_id TEXT NOT NULL REFERENCES editions(edition_id) DEFERRABLE INITIALLY DEFERRED,
                body TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS editions (
                edition_id TEXT PRIMARY KEY,
                recording_key TEXT NOT NULL REFERENCES archive_roots(recording_key)
            );
            CREATE TABLE IF NOT EXISTS current_editions (
                recording_id TEXT PRIMARY KEY REFERENCES archive_roots(recording_id),
                edition_id TEXT NOT NULL REFERENCES editions(edition_id)
            );
            CREATE TABLE IF NOT EXISTS admissions (
                package_id TEXT PRIMARY KEY,
                recording_key TEXT NOT NULL REFERENCES archive_roots(recording_key),
                edit_id TEXT NOT NULL,
                child_id TEXT NOT NULL,
                receipt_id TEXT NOT NULL UNIQUE,
                edition_id TEXT NOT NULL REFERENCES editions(edition_id),
                wire BLOB NOT NULL,
                UNIQUE (recording_key, edit_id),
                UNIQUE (recording_key, child_id)
            );
        ''')
        initialize_ledger(self.connection)

    def transaction(self):
        return transaction(self.connection)

    def load_root(self, recording_id: str) -> RootState | None:
        row = self.connection.execute(
            'SELECT body, revision_id, initial_edition_id FROM archive_roots WHERE recording_id = ?',
            (recording_id,),
        ).fetchone()
        if row is None:
            return None
        body, revision_id, initial_edition_id = row
        return RootState(Recording.from_data(json.loads(body)), revision_id, initial_edition_id)

    def store_root(self, root: RootState) -> None:
        self.connection.execute('''
            INSERT INTO archive_roots(recording_id, recording_key, revision_id, initial_edition_id, body)
            VALUES (?, ?, ?, ?, ?)
        ''', (root.recording.recording_id, root.recording.key, root.revision_id,
              root.initial_edition_id, canonical_json(root.recording.as_data())))

    def load_current(self, recording_id: str) -> str:
        row = self.connection.execute(
            'SELECT edition_id FROM current_editions WHERE recording_id = ?', (recording_id,)
        ).fetchone()
        if row is None:
            raise NotFoundError(f'no current edition for recording: {recording_id}')
        return row[0]

    def find_admission(
        self, recording_key: str, *, package_id: str | None = None, edit_id: str | None = None,
    ) -> tuple[AdmissionReceipt, bytes] | None:
        if (package_id is None) == (edit_id is None):
            raise ValueError('provide exactly one package id or edit id')
        row = self.connection.execute('''
            SELECT receipt_id, package_id, edit_id, edition_id, wire FROM admissions
            WHERE recording_key = ? AND (package_id = ? OR edit_id = ?)
        ''', (recording_key, package_id, edit_id)).fetchone()
        if row is None:
            return None
        receipt_id, number, edit, edition_id, wire = row
        return AdmissionReceipt(receipt_id, number, edit, edition_id), wire

    def record_admission(
        self, recording_key: str, child_id: str, receipt: AdmissionReceipt, wire: bytes,
    ) -> None:
        self.connection.execute('''
            INSERT INTO admissions(package_id, recording_key, edit_id, child_id, receipt_id, edition_id, wire)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (receipt.package_id, recording_key, receipt.edit_id, child_id,
              receipt.receipt_id, receipt.edition_id, wire))

    def load_accepted(self, recording_key: str) -> tuple[bytes, ...]:
        rows = self.connection.execute(
            'SELECT wire FROM admissions WHERE recording_key = ? ORDER BY package_id', (recording_key,)
        )
        return tuple(wire for (wire,) in rows)

    def save_edition(self, recording_key: str, edition_id: str) -> None:
        self.connection.execute(
            'INSERT INTO editions(edition_id, recording_key) VALUES (?, ?)', (edition_id, recording_key)
        )

    def set_current(self, recording_id: str, edition_id: str) -> None:
        self.connection.execute('''
            INSERT INTO current_editions(recording_id, edition_id) VALUES (?, ?)
            ON CONFLICT(recording_id) DO UPDATE SET edition_id = excluded.edition_id
        ''', (recording_id, edition_id))
