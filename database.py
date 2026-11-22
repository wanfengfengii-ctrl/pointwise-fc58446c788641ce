import sqlite3
from contextlib import contextmanager
from os import PathLike
from typing import Iterator


DatabasePath = str | PathLike[str]


def connect(path: DatabasePath) -> sqlite3.Connection:
    conn = sqlite3.connect(path, isolation_level=None)
    try:
        conn.execute('PRAGMA foreign_keys = ON')
    except BaseException:
        conn.close()
        raise
    return conn


@contextmanager
def transaction(conn: sqlite3.Connection) -> Iterator[sqlite3.Connection]:
    conn.execute('BEGIN IMMEDIATE')
    try:
        yield conn
        conn.commit()
    except BaseException:
        if conn.in_transaction:
            conn.rollback()
        raise


def open_source(path: DatabasePath) -> sqlite3.Connection:
    from exchange.receipts import initialize_issues
    from revision.edits import initialize_amendments
    from revision.freeze import initialize_revisions
    from revision.views import initialize_working_views
    from source.recordings import initialize_recordings

    conn = connect(path)
    try:
        initialize_recordings(conn)
        initialize_amendments(conn)
        initialize_working_views(conn)
        initialize_revisions(conn)
        initialize_issues(conn)
    except BaseException:
        conn.close()
        raise
    return conn
