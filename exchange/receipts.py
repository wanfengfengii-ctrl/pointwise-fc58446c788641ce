import sqlite3
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class IssueReceipt:
    receipt_id: str
    package_id: str
    child_id: str
    wire: bytes


def initialize_issues(conn: sqlite3.Connection) -> None:
    conn.execute('''
        CREATE TABLE IF NOT EXISTS issues (
            receipt_id TEXT PRIMARY KEY,
            package_id TEXT NOT NULL UNIQUE,
            child_id TEXT NOT NULL REFERENCES frozen_revisions(revision_id),
            recording_key TEXT NOT NULL,
            edit_id TEXT NOT NULL,
            wire BLOB NOT NULL,
            UNIQUE (recording_key, edit_id),
            FOREIGN KEY (recording_key, edit_id) REFERENCES amendments(recording_key, edit_id)
        )
    ''')


def load_issue(conn: sqlite3.Connection, receipt_id: str) -> IssueReceipt | None:
    row = conn.execute(
        'SELECT package_id, child_id, wire FROM issues WHERE receipt_id = ?', (receipt_id,)
    ).fetchone()
    return None if row is None else IssueReceipt(receipt_id, *row)


def record_issue(conn: sqlite3.Connection, recording_key: str, edit_id: str, receipt: IssueReceipt) -> None:
    conn.execute('''
        INSERT INTO issues(receipt_id, package_id, child_id, recording_key, edit_id, wire)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (receipt.receipt_id, receipt.package_id, receipt.child_id, recording_key, edit_id, receipt.wire))
