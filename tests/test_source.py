from archive.admit import admit
from archive.root import open_archive
from audit.retrieve import retrieve
from errors import ConflictError, NotFoundError, ValidationError
from revision.freeze import freeze
from source.import_rows import import_root
from source.readings import Reading
from source.recordings import load_recording
from tests.support import DatabaseTests, issue_edit, open_initial, row_names


class RootTests(DatabaseTests):
    def test_order_and_missing(self):
        with self.source() as conn:
            recording = import_root(conn, 'strain', [Reading('A', 7), Reading('M', None), Reading('A', 7)])
            self.assertEqual(load_recording(conn, 'strain'), recording)
            root = freeze(conn, recording_id='strain')
            self.assertEqual(freeze(conn, recording_id='strain'), root)
            self.assertEqual([row.reading.value for row in root.rows], [7, None, 7])
            self.assertNotEqual(root.rows[0].occurrence_id, root.rows[2].occurrence_id)
            catalogued = conn.execute('SELECT occurrence_id FROM recording_rows ORDER BY ordinal').fetchall()
            self.assertEqual([row[0] for row in catalogued], [row.occurrence_id for row in root.rows])

        # T1.root_archive
        with self.archive() as store:
            report = retrieve(store, open_initial(store, recording, root))
            self.assertEqual(row_names(report), ['A', 'M', 'A'])
            self.assertEqual([row.position for row in report.rows], [0, 1, 2])
            self.assertEqual([row.evidence.ordinal for row in report.rows], [0, 1, 2])
            self.assertEqual([row.evidence.kind for row in report.rows], ['root', 'root', 'root'])
            self.assertEqual([row.occurrence_id for row in report.rows], [row.occurrence_id for row in root.rows])
            self.assertNotEqual(report.rows[0].occurrence_id, report.rows[2].occurrence_id)
            self.assertEqual([row.missing for row in report.rows], [False, True, False])
            self.assertEqual(report.total, 14)

    def test_invalid_reading(self):
        with self.source() as conn:
            for value in (True, 7.0, '7', []):
                with self.subTest(value=value):
                    with self.assertRaises(ValidationError):
                        import_root(conn, 'invalid', [Reading('A', 7), {'name': 'B', 'value': value}])
                    self.assertIsNone(load_recording(conn, 'invalid'))
                    self.assertEqual(conn.execute('SELECT count(*) FROM recording_rows').fetchone()[0], 0)
            with self.assertRaises(NotFoundError):
                freeze(conn, recording_id='invalid')

    def test_repeat_import(self):
        with self.source() as conn:
            rows = [Reading('A', 7), Reading('M', None), Reading('B', 7)]
            recording = import_root(conn, 'strain', rows)
            self.assertEqual(import_root(conn, 'strain', [row.as_data() for row in rows]), recording)
            with self.assertRaises(ConflictError):
                import_root(conn, 'strain', [rows[0], rows[1], Reading('B', 8)])
            # T2.order_conflict
            with self.assertRaises(ConflictError):
                import_root(conn, 'strain', [rows[0], rows[2], rows[1]])
            self.assertEqual(load_recording(conn, 'strain'), recording)
            root = freeze(conn, recording_id='strain')
            self.assertEqual([row.reading.name for row in root.rows], ['A', 'M', 'B'])

    def test_archive_reopen(self):
        with self.source() as conn:
            recording = import_root(conn, 'strain', [Reading('A', 7)])
            root = freeze(conn, recording_id='strain')
            _, issued = issue_edit(conn, root, 'tail', 1, 0, [Reading('B', 2)])
        with open_source_for_conflict(self.directory) as other:
            conflict = import_root(other, 'strain', [Reading('A', 8)])
            conflict_root = freeze(other, recording_id='strain')
        with self.archive() as store:
            with self.assertRaises(ValidationError):
                open_archive(store, recording, conflict_root.revision_id)
            self.assertIsNone(store.load_root('strain'))
            initial = open_initial(store, recording, root)
            accepted = admit(store, 'strain', issued.wire)
        with self.archive() as store:
            self.assertEqual(open_initial(store, recording, root), initial)
            with self.assertRaises(ConflictError):
                open_initial(store, conflict, conflict_root)
            self.assertEqual(store.load_current('strain'), accepted.edition_id)
            self.assertEqual(admit(store, 'strain', issued.wire), accepted)
            self.assertEqual(row_names(retrieve(store, initial)), ['A'])
            self.assertEqual(retrieve(store, accepted.edition_id).total, 9)


def open_source_for_conflict(directory):
    from contextlib import closing
    from database import open_source

    return closing(open_source(directory / 'other-source.sqlite3'))
