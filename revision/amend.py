import sqlite3
from collections.abc import Iterable

from database import transaction
from errors import ConflictError, NotFoundError
from revision.edits import Amendment, load_amendment, register_amendment, work_number
from revision.freeze import load_frozen_revision
from revision.ranges import checked_range
from revision.views import WorkingView, build_working_view, load_working_view, store_working_view
from source.readings import parse_rows


def amend(
    conn: sqlite3.Connection, edit_id: str, parent_id: str, start: int,
    delete_count: int, inserts: Iterable[object],
) -> WorkingView:
    amendment = Amendment(edit_id, parent_id, start, delete_count, parse_rows(inserts))
    with transaction(conn):
        parent = load_frozen_revision(conn, parent_id)
        if parent is None:
            raise NotFoundError(f'unknown frozen parent: {parent_id}')
        existing = load_amendment(conn, parent.recording_key, edit_id)
        if existing is not None:
            if existing != amendment:
                raise ConflictError(f'edit {edit_id} is already bound to another amendment')
            key = work_number(parent.recording_key, existing)
            work = load_working_view(conn, key)
            if work is None:
                raise NotFoundError(f'missing working view for registered edit: {edit_id}')
            return work
        bounds = checked_range(len(parent.rows), start, delete_count)
        view = build_working_view(parent, amendment, bounds)
        register_amendment(conn, parent.recording_key, amendment)
        store_working_view(conn, view)
        return view
