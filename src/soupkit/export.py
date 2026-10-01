"""Writing records out."""
from __future__ import annotations

import csv
import json
from collections.abc import Sequence
from pathlib import Path


def to_json(records: Sequence[dict[str, str]], path: str | Path, *, indent: int = 2) -> Path:
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(list(records), indent=indent, ensure_ascii=False), encoding="utf-8")
    return out


def to_csv(records: Sequence[dict[str, str]], path: str | Path) -> Path:
    """Write records to CSV.

    The header is the union of every record's keys, in first-seen order, so a row
    that happens to be missing a field does not truncate the whole file - which is
    what happens if you take the columns from `records[0]` alone.
    """
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    fieldnames: dict[str, None] = {}
    for record in records:
        for key in record:
            fieldnames.setdefault(key, None)

    with out.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(fieldnames))
        writer.writeheader()
        for record in records:
            writer.writerow(record)
    return out
