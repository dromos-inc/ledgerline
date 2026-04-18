"""CSV serialization helpers.

Amounts come out of the DB in integer cents; CSVs present dollars with
two decimal places. Dates are ISO-8601.
"""

from __future__ import annotations

import csv
import io
from collections.abc import Iterable


def to_csv(header: Iterable[str], rows: Iterable[Iterable[object]]) -> str:
    """Serialize rows to a CSV string with the given header."""
    buf = io.StringIO()
    writer = csv.writer(buf, lineterminator="\n")
    writer.writerow(list(header))
    for row in rows:
        writer.writerow(list(row))
    return buf.getvalue()


def cents_to_dollars(cents: int) -> str:
    """Format an integer-cents value as a fixed-point dollar string."""
    negative = cents < 0
    abs_cents = abs(cents)
    whole = abs_cents // 100
    frac = abs_cents % 100
    sign = "-" if negative else ""
    return f"{sign}{whole}.{frac:02d}"
