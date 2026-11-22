import json
import sqlite3

from audit.provenance import ReportRow
from identity import canonical_json
from source.evidence import ReadingOccurrence


def initialize_ledger(conn: sqlite3.Connection) -> None:
    conn.execute('''
        CREATE TABLE IF NOT EXISTS ledger_rows (
            edition_id TEXT NOT NULL REFERENCES editions(edition_id),
            position INTEGER NOT NULL CHECK (position >= 0),
            occurrence_id TEXT NOT NULL,
            body TEXT NOT NULL,
            PRIMARY KEY (edition_id, position),
            UNIQUE (edition_id, occurrence_id)
        )
    ''')


def store_ledger(conn: sqlite3.Connection, edition_id: str, rows: tuple[ReportRow, ...]) -> None:
    conn.executemany(
        'INSERT INTO ledger_rows(edition_id, position, occurrence_id, body) VALUES (?, ?, ?, ?)',
        ((edition_id, row.position, row.occurrence_id, canonical_json(row.occurrence.as_data())) for row in rows),
    )


def load_ledger(conn: sqlite3.Connection, edition_id: str) -> tuple[ReportRow, ...] | None:
    if conn.execute('SELECT 1 FROM editions WHERE edition_id = ?', (edition_id,)).fetchone() is None:
        return None
    rows = conn.execute(
        'SELECT position, body FROM ledger_rows WHERE edition_id = ? ORDER BY position', (edition_id,)
    )
    return tuple(ReportRow(position, ReadingOccurrence.from_data(json.loads(body))) for position, body in rows)
