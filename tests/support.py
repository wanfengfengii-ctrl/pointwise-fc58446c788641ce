from contextlib import closing
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

from archive.root import open_archive
from archive.storage import ArchiveStore
from database import open_source
from exchange.issue import issue
from revision.amend import amend
from revision.freeze import freeze
from source.import_rows import import_root
from source.readings import Reading


class DatabaseTests(TestCase):
    def setUp(self):
        directory = TemporaryDirectory(prefix='bridge-archive-test-')
        self.addCleanup(directory.cleanup)
        self.directory = Path(directory.name)

    def source(self):
        return closing(open_source(self.directory / 'source.sqlite3'))

    def archive(self, name='archive'):
        return ArchiveStore(self.directory / f'{name}.sqlite3')


def original(conn):
    recording = import_root(conn, 'bridge-run', [Reading('A', 7), Reading('B', 7), Reading('C', 9)])
    return recording, freeze(conn, recording_id=recording.recording_id)


def issue_edit(conn, parent, edit_id, start, delete_count, inserts=()):
    work = amend(conn, edit_id, parent.revision_id, start, delete_count, inserts)
    child = freeze(conn, work_id=work.work_id)
    return child, issue(conn, edit_id, child.revision_id)


def detached_shift(test, *, replace_beta=True):
    with test.source() as conn:
        recording, root = original(conn)
        alpha, alpha_one = issue_edit(conn, root, 'alpha-1', 2, 0, [Reading('X', 8)])
        beta_rows = [Reading('Y', 6)] if replace_beta else []
        _, beta = issue_edit(conn, root, 'beta', 1, 1, beta_rows)
        _, alpha_two = issue_edit(conn, alpha, 'alpha-2', 2, 1, [Reading('Z', 10)])
    (test.directory / 'source.sqlite3').unlink()
    return recording, root, {'alpha-1': alpha_one, 'beta': beta, 'alpha-2': alpha_two}


def open_initial(store, recording, root):
    return open_archive(store, recording, root.revision_id)


def row_names(report):
    return [row.name for row in report.rows]


def fail_commit_after(conn, table):
    if table not in {'issues', 'admissions'}:
        raise ValueError('unsupported commit guard target')
    conn.executescript(f'''
        CREATE TABLE test_commit_parent (id INTEGER PRIMARY KEY);
        CREATE TABLE test_commit_guard (
            id INTEGER REFERENCES test_commit_parent(id) DEFERRABLE INITIALLY DEFERRED
        );
        CREATE TRIGGER test_reject_commit AFTER INSERT ON {table}
        BEGIN
            INSERT INTO test_commit_guard VALUES (1);
        END;
    ''')
