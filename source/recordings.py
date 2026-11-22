import json
import sqlite3
from dataclasses import dataclass, field

from identity import canonical_json, expect_fields, expect_list, fingerprint, require_text
from source.evidence import ReadingOccurrence, root_occurrences
from source.readings import Reading, parse_reading, parse_rows


def recording_key(recording_id: str, rows: tuple[Reading, ...]) -> str:
    return fingerprint('recording', [recording_id, [row.as_data() for row in rows]])


@dataclass(frozen=True, slots=True)
class Recording:
    recording_id: str
    rows: tuple[Reading, ...]
    key: str = field(init=False)

    def __post_init__(self) -> None:
        require_text(self.recording_id, 'recording id')
        rows = parse_rows(self.rows)
        object.__setattr__(self, 'rows', rows)
        object.__setattr__(self, 'key', recording_key(self.recording_id, rows))

    def occurrences(self) -> tuple[ReadingOccurrence, ...]:
        return root_occurrences(self.key, self.rows)

    def as_data(self) -> dict:
        return {'recording_id': self.recording_id, 'rows': [row.as_data() for row in self.rows]}

    @classmethod
    def from_data(cls, raw: object) -> 'Recording':
        data = expect_fields(raw, {'recording_id', 'rows'}, 'recording')
        return cls(data['recording_id'], tuple(parse_reading(row) for row in expect_list(data['rows'], 'recording rows')))


def initialize_recordings(conn: sqlite3.Connection) -> None:
    conn.executescript('''
        CREATE TABLE IF NOT EXISTS recordings (
            recording_id TEXT PRIMARY KEY,
            recording_key TEXT NOT NULL UNIQUE
        );
        CREATE TABLE IF NOT EXISTS recording_rows (
            recording_key TEXT NOT NULL REFERENCES recordings(recording_key),
            ordinal INTEGER NOT NULL CHECK (ordinal >= 0),
            occurrence_id TEXT NOT NULL UNIQUE,
            body TEXT NOT NULL,
            PRIMARY KEY (recording_key, ordinal)
        );
    ''')


def load_recording(conn: sqlite3.Connection, recording_id: str) -> Recording | None:
    row = conn.execute(
        'SELECT recording_key FROM recordings WHERE recording_id = ?', (recording_id,)
    ).fetchone()
    if row is None:
        return None
    bodies = conn.execute(
        'SELECT body FROM recording_rows WHERE recording_key = ? ORDER BY ordinal', row
    )
    return Recording(recording_id, tuple(parse_reading(json.loads(body)) for (body,) in bodies))


def store_recording(conn: sqlite3.Connection, recording: Recording) -> None:
    conn.execute(
        'INSERT INTO recordings(recording_id, recording_key) VALUES (?, ?)',
        (recording.recording_id, recording.key),
    )
    conn.executemany(
        'INSERT INTO recording_rows(recording_key, ordinal, occurrence_id, body) VALUES (?, ?, ?, ?)',
        (
            (recording.key, row.evidence.ordinal, row.occurrence_id, canonical_json(row.reading.as_data()))
            for row in recording.occurrences()
        ),
    )
