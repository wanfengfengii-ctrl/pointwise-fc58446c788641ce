import argparse
import json
from contextlib import closing
from pathlib import Path
from tempfile import TemporaryDirectory

from archive.admit import admit
from archive.root import open_archive
from archive.storage import ArchiveStore
from audit.retrieve import Reconciliation, retrieve
from database import open_source
from exchange.issue import issue
from revision.amend import amend
from revision.freeze import freeze
from source.import_rows import import_root


def details(report: Reconciliation) -> list[list]:
    return [[row.name, row.value, row.evidence.kind, row.evidence.edit_id, row.evidence.ordinal] for row in report.rows]


def run(sample: dict) -> dict:
    actual = []
    downstream = []
    with TemporaryDirectory(prefix='bridge-archive-demo-') as work_dir:
        directory = Path(work_dir)
        with closing(open_source(directory / 'source.sqlite3')) as conn:
            recording = import_root(conn, sample['recording_id'], sample['rows'])
            root = freeze(conn, recording_id=recording.recording_id)
            frozen = {None: root.revision_id}
            packages = {}
            for item in sample['edits']:
                edit_id = item['edit_id']
                work = amend(
                    conn, edit_id, frozen[item['parent']], item['start'], item['delete_count'], item['inserts'],
                )
                child = freeze(conn, work_id=work.work_id)
                frozen[edit_id] = child.revision_id
                packages[edit_id] = issue(conn, edit_id, child.revision_id).wire
        for index, order in enumerate(sample['delivery_orders']):
            path = directory / f'archive-{index}.sqlite3'
            with ArchiveStore(path) as store:
                initial = open_archive(store, recording, root.revision_id)
                for edit_id in order:
                    admit(store, recording.recording_id, packages[edit_id])
                current = store.load_current(recording.recording_id)
            with ArchiveStore(path) as reopened:
                final = retrieve(reopened, current)
                old = retrieve(reopened, initial)
                actual.append(details(final))
                downstream.append({'current_total': final.total, 'initial_rows': details(old), 'initial_total': old.total})

    expected_rows = [
        ['A', 7, 'root', None, 0], ['Y', 6, 'edit', 'beta', 0],
        ['Z', 10, 'edit', 'alpha-2', 0], ['C', 9, 'root', None, 2],
    ]
    expected_totals = {
        'current_total': 32, 'initial_total': 23,
        'initial_rows': [['A', 7, 'root', None, 0], ['B', 7, 'root', None, 1], ['C', 9, 'root', None, 2]],
    }
    expected = [expected_rows, expected_rows]
    downstream_expected = [expected_totals, expected_totals]
    if actual != expected:
        raise AssertionError(f'SPLICE_WRONG_OCCURRENCE expected {expected!r}, received {actual!r}')
    if downstream != downstream_expected:
        raise AssertionError(f'incorrect reconciliation expected {downstream_expected!r}, received {downstream!r}')
    return {
        'case_id': 'T5', 'input': sample, 'expected': expected, 'actual': actual,
        'downstream_expected': downstream_expected, 'downstream_actual': downstream,
        'code_paths': ['exchange/issue.py', 'archive/admit.py', 'archive/merge.py', 'archive/occurrences.py',
                       'archive/publish.py', 'audit/retrieve.py', 'audit/totals.py'],
        'oracle': '逐项手算确认 B 和 X 退出、C 保留原据，再独立相加 7+6+10+9 与 7+7+9。',
    }


def main() -> None:
    parser = argparse.ArgumentParser(description='Run and reconcile the frozen bridge shift sample')
    parser.add_argument('sample', type=Path)
    args = parser.parse_args()
    sample = json.loads(args.sample.read_text(encoding='utf-8'))
    print('POINTWISE_SCENARIO ' + json.dumps(run(sample), ensure_ascii=True, separators=(',', ':')))


if __name__ == '__main__':
    main()
