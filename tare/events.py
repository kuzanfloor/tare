from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path


class Mode(StrEnum):
    PAPER = "PAPER"
    LIVE = "LIVE"


class OutcomeStatus(StrEnum):
    MEASURED = "MEASURED"
    PENDING = "PENDING"
    COULD_NOT_MEASURE = "COULD_NOT_MEASURE"


@dataclass(frozen=True)
class Outcome:
    cid: str
    status: OutcomeStatus
    horizon_s: int
    unmeasured_reason: str | None = None
    pnl_usd: float | None = None
    pnl_pct: float | None = None
    mode: Mode = Mode.PAPER
    attribution: dict[str, float] | None = None

    def __post_init__(self) -> None:
        if self.status is OutcomeStatus.COULD_NOT_MEASURE:
            if not self.unmeasured_reason:
                raise ValueError("unmeasured_reason is required when status is COULD_NOT_MEASURE")
            # `is not None` on purpose: 0.0 is falsy, and zero is the value that lies.
            if self.pnl_usd is not None or self.pnl_pct is not None:
                raise ValueError("pnl cannot be recorded when status is COULD_NOT_MEASURE")
        if self.attribution is not None and self.pnl_usd is not None:
            if abs(sum(self.attribution.values()) - self.pnl_usd) > 0.005:
                raise ValueError("attribution does not reconcile with pnl_usd")


@dataclass(frozen=True)
class Summary:
    n: int
    measured: int
    unmeasured: int
    mode: Mode


def summarise(outcomes: list[Outcome]) -> Summary:
    modes = {o.mode for o in outcomes}
    if len(modes) > 1:
        raise ValueError("cannot summarise PAPER and LIVE outcomes together")
    return Summary(
        n=len(outcomes),
        measured=sum(1 for o in outcomes if o.status is OutcomeStatus.MEASURED),
        unmeasured=sum(1 for o in outcomes if o.status is OutcomeStatus.COULD_NOT_MEASURE),
        mode=modes.pop() if modes else Mode.PAPER,
    )


class DecisionState(StrEnum):
    EXECUTED = "EXECUTED"
    REJECTED = "REJECTED"
    SKIPPED = "SKIPPED"
    FAILED = "FAILED"
    UNVERIFIED = "UNVERIFIED"


@dataclass(frozen=True)
class Decision:
    cid: str
    agent: str
    action: str
    state: DecisionState
    reason: str | None = None
    market: str | None = None
    venue: str | None = None
    confidence: float | None = None
    mode: Mode = Mode.PAPER


@dataclass(frozen=True)
class DecisionTally:
    n: int
    executed: int
    unverified: int


def tally_decisions(decisions: list[Decision]) -> DecisionTally:
    return DecisionTally(
        n=len(decisions),
        executed=sum(1 for d in decisions if d.state is DecisionState.EXECUTED),
        unverified=sum(1 for d in decisions if d.state is DecisionState.UNVERIFIED),
    )


def append_event(path: Path, topic: str, event: object) -> None:
    record = {"ts": datetime.now(UTC).isoformat(), "topic": topic, **asdict(event)}
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(record) + "\n")
