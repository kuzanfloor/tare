from __future__ import annotations

import json
from collections import Counter
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path


# A reading is only current for as long as the thing it reads stays put.
# Past this, the page must say so rather than keep displaying the number.
STALE_AFTER_S = 3600


@dataclass(frozen=True)
class Snapshot:
    decisions: int = 0
    executed: int = 0
    refused: int = 0
    skipped: int = 0
    refusals: dict[str, int] = field(default_factory=dict)
    inference_calls: int = 0
    inference_charged_micro: int = 0
    inference_quoted_micro: int = 0
    inference_onchain: int = 0


def build_snapshot(journal: Path) -> Snapshot:
    records = [json.loads(line) for line in journal.read_text().splitlines() if line]
    decisions = [r for r in records if r["topic"] == "tare.decision"]
    refusals = Counter(
        r["reason"] for r in decisions if r["state"] == "REJECTED" and r.get("reason")
    )
    infer = [r for r in records if r["topic"] == "tare.inference"]
    return Snapshot(
        decisions=len(decisions),
        executed=sum(1 for r in decisions if r["state"] == "EXECUTED"),
        refused=sum(1 for r in decisions if r["state"] == "REJECTED"),
        skipped=sum(1 for r in decisions if r["state"] == "SKIPPED"),
        refusals=dict(refusals),
        inference_calls=len(infer),
        inference_charged_micro=sum(r["charged_micro"] for r in infer),
        inference_quoted_micro=sum(r["quoted_micro"] for r in infer),
        inference_onchain=sum(1 for r in infer if r.get("settle") == "onchain"),
    )


def is_stale(age_s: float, stale_after_s: float = STALE_AFTER_S) -> bool:
    return age_s >= stale_after_s


def snapshot_json(snapshot: Snapshot) -> dict:
    # The reading carries its own age and its own expiry. A page that shows a
    # number without saying how old it is claims to be current when it is not.
    return {
        **asdict(snapshot),
        "generated_at": datetime.now(UTC).isoformat(),
        "stale_after_s": STALE_AFTER_S,
    }
