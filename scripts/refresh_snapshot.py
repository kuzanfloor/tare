"""Regenerate docs/snapshot.json from a paper run. No secrets, no orders."""

from __future__ import annotations

import json
import pathlib

from tare.book import Book, Fill
from tare.inference import InferenceEvent
from tare.loop import step
from tare.report import build_snapshot, snapshot_json

DOCS = pathlib.Path(__file__).resolve().parent.parent / "docs"
LEGS = [
    ("jupiter", 10.0, True), ("phoenix", -10.0, True),
    ("jupiter", 6.0, True), ("phoenix", -6.0, True),
    ("jupiter", 4.0, True), ("phoenix", -4.0, True),
    ("jupiter", 8.0, True), ("phoenix", -8.0, True),
]


def _judge(cid: str, settle: str):
    def judge(quoted_micro: int) -> InferenceEvent:
        return InferenceEvent(
            cid=cid, model="deepseek-v3-2", quoted_micro=quoted_micro,
            charged_micro=int(quoted_micro * 0.58), route="marketplace",
            rail="solana", settle=settle,
        )

    return judge


def main() -> None:
    journal = DOCS / "journal.jsonl"
    journal.unlink(missing_ok=True)
    book = Book(inventory_cap=90.0)

    for i, (venue, qty, confirmed) in enumerate(LEGS):
        book.apply_fill(Fill(venue, qty, confirmed))
        step(book, proposed_qty=abs(qty), cid=f"c-{i}", journal=journal,
             stake_usd=40.0, quoted_micro=707,
             judge_fn=_judge(f"c-{i}", "onchain" if i % 2 else "surplus"))

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
    (DOCS / "snapshot.json").write_text(json.dumps(payload, indent=2) + "\n")
    print(f"{payload['generated_at']}  decisions={payload['decisions']} "
          f"refused={payload['refused']} delta_status={payload['delta_status']}")


if __name__ == "__main__":
    main()
