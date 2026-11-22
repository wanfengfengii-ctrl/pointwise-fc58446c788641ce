import sqlite3

from errors import ConflictError, NotFoundError, ValidationError
from exchange.codec import decode_package
from exchange.issue import issue
from exchange.manifest import issue_number
from exchange.receipts import load_issue
from revision.amend import amend
from revision.edits import load_amendment
from revision.freeze import freeze, load_frozen_revision
from revision.views import load_current_working_view
from source.import_rows import import_root
from source.readings import Reading
from tests.support import DatabaseTests, fail_commit_after, issue_edit, original


class IssueTests(DatabaseTests):
    def test_frozen_base(self):
        with self.source() as conn:
            recording, root = original(conn)
            old = amend(conn, 'old', root.revision_id, 1, 1, [Reading('R', 4)])
            old_child = freeze(conn, work_id=old.work_id)
            advanced = amend(conn, 'advance', old_child.revision_id, 0, 0, [Reading('N', 1)])
            self.assertEqual(load_current_working_view(conn, recording.key), advanced)
            self.assertEqual([row.reading.name for row in advanced.rows], ['N', 'A', 'R', 'C'])
            self.assertEqual(amend(conn, 'old', root.revision_id, 1, 1, [Reading('R', 4)]), old)
            self.assertEqual(load_current_working_view(conn, recording.key), advanced)
            with self.assertRaises(ConflictError):
                amend(conn, 'old', root.revision_id, 0, 1, [])
            self.assertEqual(load_frozen_revision(conn, old_child.revision_id), old_child)
            receipt = issue(conn, 'old', old_child.revision_id)
            manifest = decode_package(receipt.wire).manifest
            self.assertEqual(manifest.parent_id, root.revision_id)
            self.assertEqual(manifest.child_id, old_child.revision_id)
            self.assertEqual(manifest.deleted, (root.rows[1].evidence,))
            self.assertEqual(manifest.anchor, root.rows[0].evidence)
            self.assertNotEqual(manifest.deleted[0], manifest.anchor)
            self.assertEqual(manifest.inserted, (old_child.rows[1],))

    def test_package_roundtrip(self):
        with self.source() as conn:
            _, root = original(conn)
            child, receipt = issue_edit(conn, root, '补录', 3, 0, [Reading('缺测', None), Reading('S', -1)])
            with self.assertRaises(ValidationError):
                issue(conn, 'some-other-edit', child.revision_id)
        with self.source() as conn:
            readback = load_issue(conn, receipt.receipt_id)
            self.assertEqual(readback, receipt)
            self.assertEqual(issue(conn, '补录', child.revision_id), receipt)
            package = decode_package(readback.wire)
            self.assertEqual(package.wire, receipt.wire)
            self.assertEqual(package.package_id, receipt.package_id)
            self.assertEqual(package.manifest.receipt_id, receipt.receipt_id)
            self.assertEqual(package.manifest.amendment.inserts, (Reading('缺测', None), Reading('S', -1)))
            self.assertIsNone(load_issue(conn, 'unknown'))

    def test_issuance_atomic(self):
        with self.source() as conn:
            recording, root = original(conn)
            work = amend(conn, 'end', root.revision_id, 3, 0, [Reading('D', 2)])
            child = freeze(conn, work_id=work.work_id)
            receipt_id = issue_number(recording.key, 'end')
            fail_commit_after(conn, 'issues')
            with self.assertRaisesRegex(sqlite3.IntegrityError, 'FOREIGN KEY constraint failed'):
                issue(conn, 'end', child.revision_id)
            self.assertFalse(conn.in_transaction)
        with self.source() as conn:
            self.assertIsNone(load_issue(conn, receipt_id))
            self.assertEqual(conn.execute('SELECT count(*) FROM issues').fetchone()[0], 0)
            self.assertEqual(conn.execute('SELECT count(*) FROM test_commit_guard').fetchone()[0], 0)
            self.assertEqual(load_frozen_revision(conn, child.revision_id), child)
            conn.execute('DROP TRIGGER test_reject_commit')
            receipt = issue(conn, 'end', child.revision_id)
            self.assertEqual(load_issue(conn, receipt_id), receipt)
            self.assertEqual(issue(conn, 'end', child.revision_id), receipt)

    def test_out_of_range(self):
        with self.source() as conn:
            recording = import_root(conn, 'short', [Reading('A', 7), Reading('B', 7)])
            root = freeze(conn, recording_id='short')
            self.assertIsNone(load_current_working_view(conn, recording.key))
            for start, delete in ((1, 2), (3, 0), (2, 1), (-1, 0), (0, -1), (True, 0)):
                with self.subTest(start=start, delete=delete):
                    with self.assertRaises(ValidationError):
                        amend(conn, 'invalid', root.revision_id, start, delete, [])
            with self.assertRaises(NotFoundError):
                amend(conn, 'invalid', 'missing-parent', 0, 0, [])
            with self.assertRaises(NotFoundError):
                freeze(conn, work_id='missing-work')
            with self.assertRaises(NotFoundError):
                issue(conn, 'invalid', 'missing-child')
            self.assertIsNone(load_amendment(conn, recording.key, 'invalid'))
            self.assertIsNone(load_current_working_view(conn, recording.key))
            self.assertIsNone(load_issue(conn, issue_number(recording.key, 'invalid')))
            self.assertEqual(conn.execute('SELECT count(*) FROM working_views').fetchone()[0], 0)
            self.assertEqual(conn.execute('SELECT count(*) FROM frozen_revisions').fetchone()[0], 1)
            self.assertEqual(conn.execute('SELECT count(*) FROM issues').fetchone()[0], 0)

            # T4.range_edges
            front, first = issue_edit(conn, root, 'front', 0, 0, [Reading('F', 1)])
            tail, last = issue_edit(conn, root, 'tail', 2, 0, [Reading('T', -2)])
            self.assertEqual([row.reading.name for row in front.rows], ['F', 'A', 'B'])
            self.assertEqual([row.reading.name for row in tail.rows], ['A', 'B', 'T'])
            self.assertIsNone(decode_package(first.wire).manifest.anchor)
            self.assertEqual(decode_package(last.wire).manifest.anchor, root.rows[1].evidence)
            no_change = amend(conn, 'no-change', root.revision_id, 1, 0, [])
            same_rows = freeze(conn, work_id=no_change.work_id)
            self.assertEqual(same_rows.rows, root.rows)
            self.assertNotEqual(same_rows.revision_id, root.revision_id)
