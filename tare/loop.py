from __future__ import annotations

from pathlib import Path

from tare.book import Book, DeltaStatus
from collections.abc import Callable

from tare.events import Decision, DecisionState, append_event
from tare.inference import InferenceEvent
from tare.judgment import should_buy_judgment


def _reject(cid: str, reason: str) -> Decision:
    return Decision(
        cid=cid, agent="risk", action="rebalance", state=DecisionState.REJECTED, reason=reason
    )


def decide(book: Book, proposed_qty: float, cid: str) -> Decision:
    # Deterministic gates only — no model in this path. A comparison answers
    # each of these, so an LLM here would be a flaky if-else that costs money.
    # Order is deliberate: unknown delta outranks every other consideration.
    if book.delta_status() is DeltaStatus.UNKNOWN:
        return _reject(cid, "delta_unknown_unconfirmed_fills")
    if book.would_breach_cap(proposed_qty):
        return _reject(cid, "inventory_cap_exceeded")
    if book.delta_status() is DeltaStatus.NEUTRAL:
        return Decision(
            cid=cid,
            agent="risk",
            action="rebalance",
            state=DecisionState.SKIPPED,
            reason="within_neutral_band",
        )
    return Decision(
        cid=cid,
        agent="risk",
        action="rebalance",
        state=DecisionState.EXECUTED,
        reason="rebalance_to_neutral",
    )


def step(
    book: Book,
    proposed_qty: float,
    cid: str,
    journal: Path,
    stake_usd: float = 0.0,
    quoted_micro: int | None = None,
    judge_fn: Callable[[int], InferenceEvent] | None = None,
) -> Decision:
    # Every decision is journalled, including the refusals. A system that only
    # records what it did cannot evidence what it declined to do — and the
    # refusals are the risk control.
    decision = decide(book, proposed_qty, cid)
    append_event(journal, "tare.decision", decision)

    # Judgment is bought only when it can still change the outcome and only when
    # it is cheap against the stake. The price is known ex ante and for free, so
    # nothing is spent discovering that it was not worth spending.
    if quoted_micro is None or judge_fn is None:
        return decision
    if should_buy_judgment(decision, stake_usd, quoted_micro):
        append_event(journal, "tare.inference", judge_fn(quoted_micro))
    return decision
