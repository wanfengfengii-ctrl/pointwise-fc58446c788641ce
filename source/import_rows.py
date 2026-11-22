import sqlite3
from collections.abc import Iterable

from database import transaction
from errors import ConflictError
from source.readings import parse_rows
from source.recordings import Recording, load_recording, store_recording


def import_root(conn: sqlite3.Connection, recording_id: str, rows: Iterable[object]) -> Recording:
    candidate = Recording(recording_id, parse_rows(rows))
    with transaction(conn):
        existing = load_recording(conn, recording_id)
        if existing is None:
            store_recording(conn, candidate)
            return candidate
        if existing != candidate:
            raise ConflictError(f'recording {recording_id} has different ordered rows')
        return existing
