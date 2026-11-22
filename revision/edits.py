import json
import sqlite3
from dataclasses import dataclass

from errors import ValidationError
from identity import canonical_json, expect_fields, expect_list, fingerprint, require_text
from source.evidence import OccurrenceEvidence, ReadingOccurrence
from source.readings import Reading, parse_rows


@dataclass(frozen=True, slots=True)
class Amendment:
    edit_id: str
    parent_id: str
    start: int
    delete_count: int
    inserts: tuple[Reading, ...]

    def __post_init__(self) -> None:
        require_text(self.edit_id, 'edit id')
        require_text(self.parent_id, 'parent revision id')
        if any(type(value) is not int or value < 0 for value in (self.start, self.delete_count)):
            raise ValidationError('row position and deletion count must be nonnegative integers')
        object.__setattr__(self, 'inserts', parse_rows(self.inserts))

    def as_data(self) -> dict:
        return {
            'edit_id': self.edit_id,
            'parent_id': self.parent_id,
            'start': self.start,
            'delete_count': self.delete_count,
            'inserts': [row.as_data() for row in self.inserts],
        }

    @classmethod
    def from_data(cls, raw: object) -> 'Amendment':
        data = expect_fields(raw, {'edit_id', 'parent_id', 'start', 'delete_count', 'inserts'}, 'amendment')
        return cls(
            data['edit_id'], data['parent_id'], data['start'], data['delete_count'],
            parse_rows(expect_list(data['inserts'], 'inserted readings')),
        )


def work_number(recording_key: str, amendment: Amendment) -> str:
    return fingerprint('work', [recording_key, amendment.as_data()])


def inserted_occurrences(recording_key: str, amendment: Amendment) -> tuple[ReadingOccurrence, ...]:
    return tuple(
        ReadingOccurrence(row, OccurrenceEvidence(recording_key, amendment.edit_id, position))
        for position, row in enumerate(amendment.inserts)
    )


def initialize_amendments(conn: sqlite3.Connection) -> None:
    conn.execute('''
        CREATE TABLE IF NOT EXISTS amendments (
            recording_key TEXT NOT NULL REFERENCES recordings(recording_key),
            edit_id TEXT NOT NULL,
            parent_id TEXT NOT NULL REFERENCES frozen_revisions(revision_id),
            body TEXT NOT NULL,
            PRIMARY KEY (recording_key, edit_id)
        )
    ''')


def load_amendment(conn: sqlite3.Connection, recording_key: str, edit_id: str) -> Amendment | None:
    row = conn.execute(
        'SELECT body FROM amendments WHERE recording_key = ? AND edit_id = ?',
        (recording_key, edit_id),
    ).fetchone()
    return None if row is None else Amendment.from_data(json.loads(row[0]))


def register_amendment(conn: sqlite3.Connection, recording_key: str, amendment: Amendment) -> None:
    conn.execute(
        'INSERT INTO amendments(recording_key, edit_id, parent_id, body) VALUES (?, ?, ?, ?)',
        (recording_key, amendment.edit_id, amendment.parent_id, canonical_json(amendment.as_data())),
    )
