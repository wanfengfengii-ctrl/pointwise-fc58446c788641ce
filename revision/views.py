import json
import sqlite3
from dataclasses import dataclass
from typing import TYPE_CHECKING

from identity import canonical_json
from revision.edits import Amendment, inserted_occurrences, work_number
from source.evidence import ReadingOccurrence, parse_occurrences

if TYPE_CHECKING:
    from revision.freeze import FrozenRevision


@dataclass(frozen=True, slots=True)
class WorkingView:
    work_id: str
    recording_key: str
    parent_id: str
    edit_id: str
    rows: tuple[ReadingOccurrence, ...]


def build_working_view(
    parent: 'FrozenRevision', amendment: Amendment, bounds: tuple[int, int],
) -> WorkingView:
    start, end = bounds
    rows = parent.rows[:start] + inserted_occurrences(parent.recording_key, amendment) + parent.rows[end:]
    return WorkingView(
        work_number(parent.recording_key, amendment), parent.recording_key,
        parent.revision_id, amendment.edit_id, rows,
    )


def initialize_working_views(conn: sqlite3.Connection) -> None:
    conn.executescript('''
        CREATE TABLE IF NOT EXISTS working_views (
            work_id TEXT PRIMARY KEY,
            recording_key TEXT NOT NULL,
            parent_id TEXT NOT NULL REFERENCES frozen_revisions(revision_id),
            edit_id TEXT NOT NULL,
            rows TEXT NOT NULL,
            FOREIGN KEY (recording_key, edit_id) REFERENCES amendments(recording_key, edit_id)
        );
        CREATE TABLE IF NOT EXISTS working_heads (
            recording_key TEXT PRIMARY KEY REFERENCES recordings(recording_key),
            work_id TEXT NOT NULL REFERENCES working_views(work_id)
        );
    ''')


def load_working_view(conn: sqlite3.Connection, work_id: str) -> WorkingView | None:
    row = conn.execute(
        'SELECT recording_key, parent_id, edit_id, rows FROM working_views WHERE work_id = ?',
        (work_id,),
    ).fetchone()
    if row is None:
        return None
    recording_key, parent_id, edit_id, rows = row
    return WorkingView(work_id, recording_key, parent_id, edit_id, parse_occurrences(json.loads(rows)))


def load_current_working_view(conn: sqlite3.Connection, recording_key: str) -> WorkingView | None:
    row = conn.execute(
        'SELECT work_id FROM working_heads WHERE recording_key = ?', (recording_key,)
    ).fetchone()
    return None if row is None else load_working_view(conn, row[0])


def store_working_view(conn: sqlite3.Connection, view: WorkingView) -> None:
    conn.execute(
        'INSERT INTO working_views(work_id, recording_key, parent_id, edit_id, rows) VALUES (?, ?, ?, ?, ?)',
        (view.work_id, view.recording_key, view.parent_id, view.edit_id,
         canonical_json([row.as_data() for row in view.rows])),
    )
    conn.execute('''
        INSERT INTO working_heads(recording_key, work_id) VALUES (?, ?)
        ON CONFLICT(recording_key) DO UPDATE SET work_id = excluded.work_id
    ''', (view.recording_key, view.work_id))
