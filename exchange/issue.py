import sqlite3

from database import transaction
from errors import ConflictError, NotFoundError, ValidationError
from exchange.codec import encode_package, package_number
from exchange.manifest import build_manifest, issue_number
from exchange.receipts import IssueReceipt, load_issue, record_issue
from identity import require_text
from revision.edits import load_amendment, work_number
from revision.freeze import child_revision_number, load_frozen_revision
from revision.ranges import checked_range


def issue(conn: sqlite3.Connection, edit_id: str, child_id: str) -> IssueReceipt:
    require_text(edit_id, 'edit id')
    require_text(child_id, 'child revision id')
    with transaction(conn):
        child = load_frozen_revision(conn, child_id)
        if child is None:
            raise NotFoundError(f'unknown frozen child: {child_id}')
        if child.edit_id != edit_id:
            raise ValidationError('frozen child does not belong to the requested edit')
        amendment = load_amendment(conn, child.recording_key, edit_id)
        if amendment is None or amendment.parent_id != child.parent_id:
            raise ValidationError('amendment and frozen child have different parents')
        if child_id != child_revision_number(work_number(child.recording_key, amendment)):
            raise ValidationError('frozen child does not bind the original amendment')
        parent = load_frozen_revision(conn, amendment.parent_id)
        if parent is None or parent.recording_key != child.recording_key:
            raise ValidationError('author parent is unavailable for this recording')
        receipt_id = issue_number(child.recording_key, edit_id)
        previous = load_issue(conn, receipt_id)
        if previous is not None:
            if previous.child_id != child_id:
                raise ConflictError('issue receipt is bound to another frozen child')
            return previous
        start, end = checked_range(len(parent.rows), amendment.start, amendment.delete_count)
        deleted = tuple(row.evidence for row in parent.rows[start:end])
        anchor = parent.rows[start - 1].evidence if start else None
        manifest = build_manifest(child.recording_key, child_id, amendment, deleted, anchor)
        receipt = IssueReceipt(receipt_id, package_number(manifest), child_id, encode_package(manifest))
        record_issue(conn, child.recording_key, edit_id, receipt)
        return receipt
