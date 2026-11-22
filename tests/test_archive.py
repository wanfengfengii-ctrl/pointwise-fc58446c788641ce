import json
import sqlite3
from dataclasses import replace
from itertools import permutations

from archive.admit import admit
from archive.publish import edition_number
from audit.retrieve import retrieve
from errors import ConflictError, MissingParentError, NotFoundError, ValidationError
from exchange.codec import decode_package, encode_package
from exchange.manifest import build_manifest
from revision.freeze import freeze
from source.import_rows import import_root
from source.readings import Reading
from tests.support import DatabaseTests, detached_shift, fail_commit_after, issue_edit, open_initial, original, row_names


class MergeTests(DatabaseTests):
    def test_deleted_anchor(self):
        recording, root, packages = detached_shift(self)
        orders = [('alpha-1', 'alpha-2', 'beta'), ('beta', 'alpha-1', 'alpha-2'), ('alpha-1', 'beta', 'alpha-2')]
        final_reports = []
        for index, order in enumerate(orders):
            with self.subTest(order=order):
                name = f'delivery-{index}'
                with self.archive(name) as store:
                    initial = open_initial(store, recording, root)
                    for key in order:
                        latest = admit(store, recording.recording_id, packages[key].wire)
                    self.assertEqual(store.load_current(recording.recording_id), latest.edition_id)
                with self.archive(name) as store:
                    final = retrieve(store, latest.edition_id)
                    self.assertEqual(row_names(final), ['A', 'Y', 'Z', 'C'], 'SPLICE_WRONG_OCCURRENCE')
                    self.assertEqual([row.value for row in final.rows], [7, 6, 10, 9])
                    self.assertEqual(final.total, 32)
                    self.assertEqual([row.evidence.edit_id for row in final.rows], [None, 'beta', 'alpha-2', None])
                    self.assertEqual(final.rows[-1].evidence, root.rows[2].evidence)
                    self.assertNotIn(root.rows[1].occurrence_id, [row.occurrence_id for row in final.rows])
                    alpha_insert = decode_package(packages['alpha-1'].wire).manifest.inserted[0]
                    self.assertNotIn(alpha_insert.occurrence_id, [row.occurrence_id for row in final.rows])
                    old = retrieve(store, initial)
                    self.assertEqual(row_names(old), ['A', 'B', 'C'])
                    self.assertEqual([row.evidence for row in old.rows], [row.evidence for row in root.rows])
                    self.assertEqual([row.value for row in old.rows], [7, 7, 9])
                    self.assertEqual(old.total, 23)
                    final_reports.append(final)
        self.assertEqual(len(final_reports), len(orders))
        self.assertTrue(all(report == final_reports[0] for report in final_reports))

    def test_author_position_shift(self):
        recording, root, packages = detached_shift(self, replace_beta=False)
        with self.archive() as store:
            open_initial(store, recording, root)
            admit(store, recording.recording_id, packages['alpha-1'].wire)
            beta = admit(store, recording.recording_id, packages['beta'].wire)
            before = retrieve(store, beta.edition_id)
            self.assertEqual(row_names(before), ['A', 'X', 'C'])
            latest = admit(store, recording.recording_id, packages['alpha-2'].wire)
            final = retrieve(store, latest.edition_id)
            self.assertEqual(row_names(final), ['A', 'Z', 'C'], 'SPLICE_WRONG_OCCURRENCE')
            self.assertEqual(final.total, 26)
            self.assertEqual(final.rows[-1].evidence, before.rows[-1].evidence)
            self.assertEqual(final.rows[-1].evidence, root.rows[2].evidence)
            self.assertEqual(final.rows[1].evidence.edit_id, 'alpha-2')

    def test_anchor_visibility(self):
        recording, root, packages = detached_shift(self)
        reports = []
        for index, order in enumerate(permutations(('alpha-1', 'beta'))):
            with self.archive(f'anchor-{index}') as store:
                open_initial(store, recording, root)
                for key in order:
                    latest = admit(store, recording.recording_id, packages[key].wire)
                report = retrieve(store, latest.edition_id)
                self.assertEqual(row_names(report), ['A', 'Y', 'X', 'C'], 'SPLICE_WRONG_OCCURRENCE')
                self.assertEqual(report.total, 30)
                self.assertEqual(report.rows[2].evidence.edit_id, 'alpha-1')
                self.assertEqual(report.rows[-1].evidence, root.rows[2].evidence)
                reports.append(report)
        self.assertEqual(reports[0], reports[1])

    def test_sibling_order(self):
        with self.source() as conn:
            recording, root = original(conn)
            a, first = issue_edit(conn, root, 'a', 1, 0, [Reading('P', 1), Reading('Q', 2)])
            _, last = issue_edit(conn, root, 'z', 1, 0, [Reading('R', 3), Reading('S', 4)])
            _, higher = issue_edit(conn, a, 'zz', 1, 0, [Reading('H', 5)])
        reports = []
        for index, order in enumerate(((last, first, higher), (first, higher, last))):
            with self.archive(f'siblings-{index}') as store:
                open_initial(store, recording, root)
                for package in order:
                    latest = admit(store, recording.recording_id, package.wire)
                report = retrieve(store, latest.edition_id)
                self.assertEqual(row_names(report), ['A', 'H', 'P', 'Q', 'R', 'S', 'B', 'C'])
                self.assertEqual([row.evidence.ordinal for row in report.rows[2:6]], [0, 1, 0, 1])
                self.assertEqual([row.evidence.edit_id for row in report.rows[1:6]], ['zz', 'a', 'a', 'z', 'z'])
                self.assertEqual(report.total, 38)
                reports.append(report)
        self.assertEqual(reports[0], reports[1])

    def test_empty_and_missing(self):
        with self.source() as conn:
            recording, root = original(conn)
            empty, clear = issue_edit(conn, root, 'clear', 0, 3)
            missing, fill = issue_edit(conn, empty, 'fill-missing', 0, 0, [Reading('M1', None), Reading('M2', None)])
            _, values = issue_edit(conn, missing, 'readings', 1, 0, [Reading('zero', 0), Reading('negative', -4)])
            wide = import_root(conn, 'wide', [Reading('wide', 2 ** 80), Reading('offset', -3)])
            wide_root = freeze(conn, recording_id='wide')
        with self.archive() as store:
            open_initial(store, recording, root)
            blank = retrieve(store, admit(store, recording.recording_id, clear.wire).edition_id)
            self.assertEqual((blank.rows, blank.total), ((), 0))
            all_missing = retrieve(store, admit(store, recording.recording_id, fill.wire).edition_id)
            self.assertEqual(row_names(all_missing), ['M1', 'M2'])
            self.assertTrue(all(row.missing for row in all_missing.rows))
            self.assertEqual(all_missing.total, 0)
            mixed = retrieve(store, admit(store, recording.recording_id, values.wire).edition_id)
            self.assertEqual([row.value for row in mixed.rows], [None, 0, -4, None])
            self.assertEqual([row.missing for row in mixed.rows], [True, False, False, True])
            self.assertEqual(mixed.total, -4)
            self.assertEqual(retrieve(store, open_initial(store, wide, wide_root)).total, 2 ** 80 - 3)
            with self.assertRaises(NotFoundError):
                retrieve(store, 'unknown-edition')

    def test_missing_parent(self):
        recording, root, packages = detached_shift(self)
        child = packages['alpha-2']
        manifest = decode_package(child.wire).manifest
        with self.archive() as store:
            initial = open_initial(store, recording, root)
            candidate = edition_number(recording.key, (child.package_id,))
            with self.assertRaises(MissingParentError) as rejected:
                admit(store, recording.recording_id, child.wire)
            self.assertEqual(rejected.exception.revision_id, manifest.parent_id)
            self.assertEqual(store.load_current(recording.recording_id), initial)
            self.assertEqual(store.load_accepted(recording.key), ())
            self.assertIsNone(store.find_admission(recording.key, package_id=child.package_id))
            with self.assertRaises(NotFoundError):
                retrieve(store, candidate)
            admit(store, recording.recording_id, packages['alpha-1'].wire)
            accepted = admit(store, recording.recording_id, child.wire)
            self.assertEqual(row_names(retrieve(store, accepted.edition_id)), ['A', 'B', 'Z', 'C'])
            self.assertEqual(admit(store, recording.recording_id, child.wire), accepted)
            self.assertEqual(len(store.load_accepted(recording.key)), 2)

    def test_duplicate_and_conflict(self):
        with self.source() as conn:
            recording, root = original(conn)
            _, first = issue_edit(conn, root, 'same', 1, 1, [Reading('Y', 6)])
            _, next_issue = issue_edit(conn, root, 'later', 2, 0, [Reading('X', 8)])
        with self.source() as conn:
            self.assertEqual(decode_package(first.wire).manifest.edit_id, 'same')
        with self.archive() as store:
            open_initial(store, recording, root)
            accepted = admit(store, recording.recording_id, first.wire)
            latest = admit(store, recording.recording_id, next_issue.wire)
            equivalent_wire = json.dumps(json.loads(first.wire), indent=2).encode('utf-8')
            self.assertEqual(admit(store, recording.recording_id, equivalent_wire), accepted)
            self.assertEqual(admit(store, recording.recording_id, first.wire), accepted)
            self.assertEqual(store.load_current(recording.recording_id), latest.edition_id)
            self.assertEqual(row_names(retrieve(store, accepted.edition_id)), ['A', 'Y', 'C'])

            # T7.binding_conflict uses a separately issued, internally valid package.
            with self.archive('source-independent') as separate:
                open_initial(separate, recording, root)
                with self.detached_conflict_source() as conn:
                    other_recording, other_root = original(conn)
                    self.assertEqual(other_recording, recording)
                    _, conflict = issue_edit(conn, other_root, 'same', 1, 1, [Reading('W', 3)])
                self.assertNotEqual(conflict.package_id, first.package_id)
                separate_result = admit(separate, recording.recording_id, conflict.wire)
                self.assertEqual(row_names(retrieve(separate, separate_result.edition_id)), ['A', 'W', 'C'])
            with self.assertRaises(ConflictError):
                admit(store, recording.recording_id, conflict.wire)
            tampered = json.loads(conflict.wire)
            tampered['package_id'] = first.package_id
            with self.assertRaises(ValidationError):
                admit(store, recording.recording_id, json.dumps(tampered).encode('utf-8'))
            self.assertIsNone(store.find_admission(recording.key, package_id=conflict.package_id))
            self.assertEqual(store.find_admission(recording.key, edit_id='same')[0], accepted)
            self.assertEqual(store.load_current(recording.recording_id), latest.edition_id)
            self.assertEqual(len(store.load_accepted(recording.key)), 2)

    def detached_conflict_source(self):
        from contextlib import closing
        from database import open_source

        return closing(open_source(self.directory / 'conflict-source.sqlite3'))

    def test_wrong_root(self):
        with self.source() as conn:
            recording, root = original(conn)
            _, first = issue_edit(conn, root, 'incoming', 2, 0, [Reading('X', 8)])
            other = import_root(conn, 'other', [Reading('A', 7), Reading('B', 7), Reading('C', 9)])
            other_root = freeze(conn, recording_id='other')
        with self.archive() as store:
            initial = open_initial(store, other, other_root)
            right = open_initial(store, recording, root)
            with self.assertRaises(ValidationError):
                admit(store, other.recording_id, first.wire)
            self.assertEqual(store.load_current(other.recording_id), initial)
            self.assertEqual(store.load_current(recording.recording_id), right)
            self.assertEqual(store.load_accepted(other.key), ())
            self.assertEqual(store.load_accepted(recording.key), ())

    def test_invalid_author_evidence(self):
        with self.source() as conn:
            recording, root = original(conn)
            _, issued = issue_edit(conn, root, 'replace', 1, 1, [Reading('Y', 6)])
        manifest = decode_package(issued.wire).manifest
        wrong_target = build_manifest(
            recording.key, manifest.child_id, manifest.amendment, (root.rows[2].evidence,), manifest.anchor,
        )
        wrong_anchor = replace(manifest, anchor=root.rows[2].evidence)
        wrong_child = replace(manifest, child_id='wrong-child')
        with self.archive() as store:
            initial = open_initial(store, recording, root)
            for candidate in (wrong_target, wrong_anchor, wrong_child):
                with self.subTest(candidate=candidate):
                    wire = encode_package(candidate)
                    with self.assertRaises(ValidationError):
                        admit(store, recording.recording_id, wire)
                    self.assertEqual(store.load_current(recording.recording_id), initial)
                    self.assertEqual(store.load_accepted(recording.key), ())
            accepted = admit(store, recording.recording_id, issued.wire)
            self.assertEqual(row_names(retrieve(store, accepted.edition_id)), ['A', 'Y', 'C'])

    def test_rollback_and_reopen(self):
        recording, root, packages = detached_shift(self)
        alpha = packages['alpha-1']
        candidate = edition_number(recording.key, (alpha.package_id,))
        with self.archive() as store:
            initial = open_initial(store, recording, root)
            old_report = retrieve(store, initial)
            fail_commit_after(store.connection, 'admissions')
            with self.assertRaisesRegex(sqlite3.IntegrityError, 'FOREIGN KEY constraint failed'):
                admit(store, recording.recording_id, alpha.wire)
            self.assertFalse(store.connection.in_transaction)
        with self.archive() as store:
            self.assertEqual(store.load_current(recording.recording_id), initial)
            self.assertEqual(retrieve(store, initial), old_report)
            self.assertEqual(store.load_accepted(recording.key), ())
            self.assertIsNone(store.find_admission(recording.key, package_id=alpha.package_id))
            with self.assertRaises(NotFoundError):
                retrieve(store, candidate)
            self.assertEqual(store.connection.execute('SELECT count(*) FROM ledger_rows').fetchone()[0], 3)
            self.assertEqual(store.connection.execute('SELECT count(*) FROM test_commit_guard').fetchone()[0], 0)
            store.connection.execute('DROP TRIGGER test_reject_commit')
            accepted = admit(store, recording.recording_id, alpha.wire)
            self.assertEqual(accepted.edition_id, candidate)
            self.assertEqual(row_names(retrieve(store, candidate)), ['A', 'B', 'X', 'C'])
            self.assertEqual(retrieve(store, candidate).total, 31)
            self.assertEqual(admit(store, recording.recording_id, alpha.wire), accepted)
            self.assertEqual(len(store.load_accepted(recording.key)), 1)
            self.assertEqual(store.connection.execute('SELECT count(*) FROM editions').fetchone()[0], 2)
