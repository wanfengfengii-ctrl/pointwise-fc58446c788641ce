from collections.abc import Iterable

from audit.provenance import ReportRow


def sum_valid_readings(rows: Iterable[ReportRow]) -> int:
    total = 0
    for row in rows:
        if row.value is not None:
            total += row.value
    return total
