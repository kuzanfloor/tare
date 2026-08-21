from __future__ import annotations

from tare.events import Decision, DecisionState

MAX_COST_RATIO = 0.01
MICROUNITS_PER_USD = 1_000_000


def should_buy_judgment(
    decision: Decision,
    stake_usd: float,
    quoted_micro: int,
    max_cost_ratio: float = MAX_COST_RATIO,
) -> bool:
    # Judgment may veto an action, never resurrect a refusal. If the
    # deterministic gates already decided, no model can change the outcome —
    # buying inference there is spending money on a foregone conclusion.
    if decision.state is not DecisionState.EXECUTED:
        return False
    # And it is only worth buying if it is cheap against what is being decided.
    # The quote is known ex ante and for free, so this is a real comparison
    # rather than an estimate — which is the whole point of reading the 402.
    return (quoted_micro / MICROUNITS_PER_USD) <= stake_usd * max_cost_ratio
