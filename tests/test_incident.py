from itertools import permutations

from archive.admit import admit
from audit.retrieve import retrieve
from errors import MissingParentError
from exchange.codec import decode_package
from revision.amend import amend
from revision.freeze import freeze
from source.readings import Reading
from tests.support import DatabaseTests, detached_shift, issue_edit, open_initial, original, row_names


class DelayedIssueTests(DatabaseTests):
    def delayed_package(self, conn):
        recording, root = original(conn)
        old = amend(conn, 'old', root.revision_id, 1, 1, [Reading('R', 4)])
        old_child = freeze(conn, work_id=old.work_id)
        ahead = amend(conn, 'advance', old_child.revision_id, 0, 0, [Reading('N', 1)])
        ahead_child = freeze(conn, work_id=ahead.work_id)
        return recording, root, old_child, ahead_child

    def test_delayed_issue_binds_frozen_parent_offline(self):
        with self.source() as conn:
            recording, root, old_child, ahead_child = self.delayed_package(conn)
            from exchange.issue import issue
            delayed = issue(conn, 'old', old_child.revision_id)
            ahead = issue(conn, 'advance', ahead_child.revision_id)
        (self.directory / 'source.sqlite3').unlink()

        manifest = decode_package(delayed.wire).manifest
        self.assertEqual(manifest.deleted, (root.rows[1].evidence,))
        self.assertEqual(manifest.anchor, root.rows[0].evidence)
        self.assertEqual(root.rows[0].reading.value, root.rows[1].reading.value)
        self.assertNotEqual(root.rows[0].occurrence_id, root.rows[1].occurrence_id)

        with self.archive() as store:
            initial = open_initial(store, recording, root)
            with self.assertRaises(MissingParentError):
                admit(store, recording.recording_id, ahead.wire)
            accepted = admit(store, recording.recording_id, delayed.wire)
            report = retrieve(store, accepted.edition_id)
            self.assertEqual(row_names(report), ['A', 'R', 'C'])
            self.assertEqual([row.value for row in report.rows], [7, 4, 9])
            self.assertEqual(report.total, 20)
            self.assertEqual(report.rows[0].evidence, root.rows[0].evidence)
            self.assertEqual(report.rows[-1].evidence, root.rows[2].evidence)
            latest = admit(store, recording.recording_id, ahead.wire)
        with self.archive() as store:
            final = retrieve(store, latest.edition_id)
            self.assertEqual(row_names(final), ['N', 'A', 'R', 'C'])
            self.assertEqual(final.total, 21)
            self.assertEqual([row.evidence.edit_id for row in final.rows], ['advance', None, 'old', None])
            old = retrieve(store, initial)
            self.assertEqual(row_names(old), ['A', 'B', 'C'])
            self.assertEqual(old.total, 23)


class ConvergenceTests(DatabaseTests):
    def test_every_legal_order_converges(self):
        recording, root, packages = detached_shift(self)
        names = ('alpha-1', 'beta', 'alpha-2')
        finals = []
        for index, order in enumerate(permutations(names)):
            with self.subTest(order=order):
                with self.archive(f'converge-{index}') as store:
                    open_initial(store, recording, root)
                    pending = list(order)
                    while pending:
                        key = pending.pop(0)
                        try:
                            latest = admit(store, recording.recording_id, packages[key].wire)
                        except MissingParentError:
                            pending.append(key)
                    current = store.load_current(recording.recording_id)
                with self.archive(f'converge-{index}') as store:
                    final = retrieve(store, current)
                    self.assertEqual(row_names(final), ['A', 'Y', 'Z', 'C'], 'SPLICE_WRONG_OCCURRENCE')
                    self.assertEqual(final.total, 32)
                    self.assertEqual([row.evidence.edit_id for row in final.rows], [None, 'beta', 'alpha-2', None])
                    self.assertEqual(final.rows[-1].evidence, root.rows[2].evidence)
                    finals.append(final)
        self.assertEqual(len(finals), 6)
        self.assertTrue(all(report == finals[0] for report in finals))

    def test_head_anchor_levels(self):
        with self.source() as conn:
            recording, root = original(conn)
            outer, first = issue_edit(conn, root, 'm-head', 0, 0, [Reading('M', 3)])
            _, second = issue_edit(conn, outer, 'n-head', 0, 0, [Reading('N', 4)])
        (self.directory / 'source.sqlite3').unlink()
        reports = []
        for index, order in enumerate(((first, second), (second, first))):
            with self.archive(f'head-{index}') as store:
                open_initial(store, recording, root)
                pending = list(order)
                while pending:
                    package = pending.pop(0)
                    try:
                        latest = admit(store, recording.recording_id, package.wire)
                    except MissingParentError:
                        pending.append(package)
                current = store.load_current(recording.recording_id)
            with self.archive(f'head-{index}') as store:
                reports.append(retrieve(store, current))
        for report in reports:
            self.assertEqual(row_names(report), ['N', 'M', 'A', 'B', 'C'])
            self.assertEqual(report.total, 30)
        self.assertEqual(reports[0], reports[1])

    def test_delete_only_control_reopens(self):
        recording, root, packages = detached_shift(self, replace_beta=False)
        with self.archive() as store:
            initial = open_initial(store, recording, root)
            admit(store, recording.recording_id, packages['alpha-1'].wire)
            middle = admit(store, recording.recording_id, packages['beta'].wire)
            self.assertEqual(row_names(retrieve(store, middle.edition_id)), ['A', 'X', 'C'])
            latest = admit(store, recording.recording_id, packages['alpha-2'].wire)
            current = store.load_current(recording.recording_id)
        with self.archive() as store:
            self.assertEqual(store.load_current(recording.recording_id), current)
            final = retrieve(store, latest.edition_id)
            self.assertEqual(row_names(final), ['A', 'Z', 'C'])
            self.assertEqual(final.total, 26)
            self.assertEqual(final.rows[-1].evidence, root.rows[2].evidence)
            old = retrieve(store, initial)
            self.assertEqual(row_names(old), ['A', 'B', 'C'])
            self.assertEqual(old.total, 23)
