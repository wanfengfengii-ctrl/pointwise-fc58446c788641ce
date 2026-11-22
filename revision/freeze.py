import json
import sqlite3
from dataclasses import dataclass

from database import transaction
from errors import NotFoundError, ValidationError
from identity import canonical_json, fingerprint, require_text
from revision.views import load_working_view
from source.evidence import ReadingOccurrence, parse_occurrences
from source.recordings import load_recording


@dataclass(frozen=True, slots=True)
class FrozenRevision:
    revision_id: str
    recording_key: str
    parent_id: str | None
    edit_id: str | None
    rows: tuple[ReadingOccurrence, ...]


def root_revision_number(recording_key: str) -> str:
    return fingerprint('root', recording_key)


def child_revision_number(work_id: str) -> str:
    return fingerprint('revision', work_id)


def initialize_revisions(conn: sqlite3.Connection) -> None:
    conn.execute('''
        CREATE TABLE IF NOT EXISTS frozen_revisions (
            revision_id TEXT PRIMARY KEY,
            recording_key TEXT NOT NULL REFERENCES recordings(recording_key),
            parent_id TEXT REFERENCES frozen_revisions(revision_id),
            edit_id TEXT,
            work_id TEXT UNIQUE REFERENCES working_views(work_id),
            rows TEXT NOT NULL,
            FOREIGN KEY (recording_key, edit_id) REFERENCES amendments(recording_key, edit_id)
        )
    ''')


def load_frozen_revision(conn: sqlite3.Connection, revision_id: str) -> FrozenRevision | None:
    row = conn.execute(
        'SELECT recording_key, parent_id, edit_id, rows FROM frozen_revisions WHERE revision_id = ?',
        (revision_id,),
    ).fetchone()
    if row is None:
        return None
    recording_key, parent_id, edit_id, rows = row
    return FrozenRevision(revision_id, recording_key, parent_id, edit_id, parse_occurrences(json.loads(rows)))


def freeze(
    conn: sqlite3.Connection, *, recording_id: str | None = None, work_id: str | None = None,
) -> FrozenRevision:
    if (recording_id is None) == (work_id is None):
        raise ValidationError('freeze requires exactly one recording id or work id')
    with transaction(conn):
        if recording_id is not None:
            require_text(recording_id, 'recording id')
            recording = load_recording(conn, recording_id)
            if recording is None:
                raise NotFoundError(f'unknown recording: {recording_id}')
            candidate = FrozenRevision(
                root_revision_number(recording.key), recording.key, None, None, recording.occurrences(),
            )
        else:
            require_text(work_id, 'work id')
            work = load_working_view(conn, work_id)
            if work is None:
                raise NotFoundError(f'unknown work revision: {work_id}')
            candidate = FrozenRevision(
                child_revision_number(work.work_id), work.recording_key, work.parent_id, work.edit_id, work.rows,
            )
        existing = load_frozen_revision(conn, candidate.revision_id)
        if existing is not None:
            return existing
        conn.execute('''
            INSERT INTO frozen_revisions(revision_id, recording_key, parent_id, edit_id, work_id, rows)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (candidate.revision_id, candidate.recording_key, candidate.parent_id,
              candidate.edit_id, work_id, canonical_json([row.as_data() for row in candidate.rows])))
        return candidate
