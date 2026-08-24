"""Regenerate docs/snapshot.json from a paper run. No secrets, no orders."""

from __future__ import annotations

import json
import pathlib
import urllib.request
from datetime import UTC, datetime

from tare.book import Book, Fill
from tare.inference import InferenceEvent
from tare.loop import step
from tare.history import append_reading, history_span, load_history
from tare.report import build_snapshot, snapshot_json
from tare.scan import analyse_market, carry_rows

DOCS = pathlib.Path(__file__).resolve().parent.parent / "docs"
PHOENIX = "https://perp-api.phoenix.trade"
ROUND_TRIP_FEE_PCT = 0.07  # 0.035% taker per side, from Phoenix market data
TOP_N = 8
LEGS = [
    ("jupiter", 10.0, True), ("phoenix", -10.0, True),
    ("jupiter", 6.0, True), ("phoenix", -6.0, True),
    ("jupiter", 4.0, True), ("phoenix", -4.0, True),
    ("jupiter", 8.0, True), ("phoenix", -8.0, True),
]



def _get(url: str):
    try:
        with urllib.request.urlopen(url, timeout=20) as response:
            return json.loads(response.read())
    except Exception:
        return None


def live_carry() -> list[dict] | None:
    # Returns None, not an empty list, when the venue cannot be read. An empty
    # table looks like "no markets carry"; None lets the page say it could not
    # look rather than report an absence it never observed.
    overview = _get(f"{PHOENIX}/v1/funding/overview")
    if not overview or "series" not in overview:
        return None

    carries = [c for c in (analyse_market(s, ROUND_TRIP_FEE_PCT) for s in overview["series"]) if c]
    carries.sort(key=lambda c: -abs(c.apr_pct))
    top = carries[:TOP_N]

    transitions, calendars = {}, {}
    for carry in top:
        t = _get(f"{PHOENIX}/v1/market/{carry.symbol}/next-market-calendar-transition")
        if t and "utcNextTransition" in t:
            transitions[carry.symbol] = datetime.fromisoformat(
                t["utcNextTransition"].replace("Z", "+00:00")
            )
            calendars[carry.symbol] = t.get("marketCalendarId", "calendared")

    return carry_rows(top, transitions, datetime.now(UTC), calendars)


def main() -> None:
    journal = DOCS / "journal.jsonl"
    journal.unlink(missing_ok=True)
    book = Book(inventory_cap=90.0)

    for i, (venue, qty, confirmed) in enumerate(LEGS):
        book.apply_fill(Fill(venue, qty, confirmed))
        # No judge_fn: this run purchases no inference, so it reports none.
        # A fabricated cost on a page that claims to publish measurements is
        # the exact failure this project exists to catch.
        step(book, proposed_qty=abs(qty), cid=f"c-{i}", journal=journal)

    step(book, proposed_qty=200.0, cid="c-cap", journal=journal)
    book.apply_fill(Fill("phoenix", -5.0, confirmed=False))
    step(book, proposed_qty=5.0, cid="c-unk", journal=journal)

    payload = snapshot_json(build_snapshot(journal))
    payload.update(
        delta_status=str(book.delta_status()),
        spot_qty=book.position.spot_qty,
        perp_qty=book.position.perp_qty,
        delta=round(book.position.delta, 4),
        unconfirmed=book.unconfirmed,
    )
    payload["carry"] = live_carry()

    # Append before reporting the span, so the reading counts itself.
    history_path = DOCS / "history.jsonl"
    append_reading(history_path, payload)
    payload["history"] = history_span(load_history(history_path))

    (DOCS / "snapshot.json").write_text(json.dumps(payload, indent=2) + "\n")
    carry = payload["carry"]
    print(f"{payload['generated_at']}  decisions={payload['decisions']} "
          f"refused={payload['refused']} delta_status={payload['delta_status']} "
          f"carry={'unreadable' if carry is None else str(len(carry)) + ' markets'} "
          f"history={payload['history']['entries']} readings / {payload['history']['span_h']}h")


if __name__ == "__main__":
    main()
