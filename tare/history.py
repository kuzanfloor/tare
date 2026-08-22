from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

# An hourly reading kept for a year is ~8,800 lines. The ceiling exists so the
# file stays reviewable by a person, not because storage is short.
MAX_ENTRIES = 4000

# Only what a time series needs. The prose reason belongs to the live reading,
# not to its history — it would triple the file to restate the obvious.
CARRY_FIELDS = ("symbol", "apr_pct", "persistence", "verdict")


def append_reading(path: Path, snapshot: dict, max_entries: int = MAX_ENTRIES) -> None:
    entry = {
        "generated_at": snapshot.get("generated_at"),
        "delta_status": snapshot.get("delta_status"),
        "decisions": snapshot.get("decisions"),
        "refused": snapshot.get("refused"),
        "carry": [
            {k: row[k] for k in CARRY_FIELDS if k in row}
            for row in (snapshot.get("carry") or [])
        ],
    }
    history = load_history(path)
    history.append(entry)
    # Timestamps are kept exactly as recorded. Gaps stay gaps: a missed run is
    # a fact about the history, and filling it would invent readings.
    kept = history[-max_entries:]
    path.write_text("".join(json.dumps(e) + "\n" for e in kept))


def load_history(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def history_span(history: list[dict]) -> dict:
    # Reports elapsed time AND the number of readings separately, because they
    # are different facts: three readings across four hours means a run was
    # missed, and averaging that away would claim continuity nobody observed.
    if not history:
        return {"entries": 0, "span_h": None, "first": None, "last": None}
    stamps = [e["generated_at"] for e in history if e.get("generated_at")]
    if not stamps:
        return {"entries": len(history), "span_h": None, "first": None, "last": None}
    first, last = min(stamps), max(stamps)
    span = (datetime.fromisoformat(last) - datetime.fromisoformat(first)).total_seconds() / 3600
    return {"entries": len(history), "span_h": round(span, 2), "first": first, "last": last}
