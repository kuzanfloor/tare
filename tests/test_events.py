import json
from datetime import datetime

import pytest

from tare.events import (
    Decision,
    DecisionState,
    Mode,
    Outcome,
    OutcomeStatus,
    summarise,
    append_event,
    tally_decisions,
)


def test_could_not_measure_requires_a_reason():
    with pytest.raises(ValueError, match="unmeasured_reason"):
        Outcome(cid="d-1", status=OutcomeStatus.COULD_NOT_MEASURE, horizon_s=3600)


def test_could_not_measure_rejects_a_pnl_value():
    with pytest.raises(ValueError, match="pnl"):
        Outcome(
            cid="d-1",
            status=OutcomeStatus.COULD_NOT_MEASURE,
            horizon_s=3600,
            unmeasured_reason="fill unconfirmed: rpc timeout",
            pnl_usd=0.0,
        )


def test_summary_counts_unmeasured_in_the_denominator():
    outcomes = [
        Outcome(cid="a", status=OutcomeStatus.MEASURED, horizon_s=60, pnl_usd=1.0),
        Outcome(cid="b", status=OutcomeStatus.MEASURED, horizon_s=60, pnl_usd=-2.0),
        Outcome(
            cid="c",
            status=OutcomeStatus.COULD_NOT_MEASURE,
            horizon_s=60,
            unmeasured_reason="fill unconfirmed: rpc timeout",
        ),
    ]

    summary = summarise(outcomes)

    assert summary.n == 3
    assert summary.measured == 2
    assert summary.unmeasured == 1


def test_summary_refuses_to_mix_paper_and_live():
    outcomes = [
        Outcome(cid="a", status=OutcomeStatus.MEASURED, horizon_s=60, pnl_usd=1.0, mode=Mode.PAPER),
        Outcome(cid="b", status=OutcomeStatus.MEASURED, horizon_s=60, pnl_usd=1.0, mode=Mode.LIVE),
    ]

    with pytest.raises(ValueError, match="PAPER"):
        summarise(outcomes)


def test_unverified_decisions_are_not_counted_as_executed():
    decisions = [
        Decision(cid="a", agent="executor", action="quote", state=DecisionState.EXECUTED),
        Decision(
            cid="b",
            agent="executor",
            action="quote",
            state=DecisionState.UNVERIFIED,
            reason="ack_timeout_2000ms",
        ),
    ]

    tally = tally_decisions(decisions)

    assert tally.executed == 1
    assert tally.unverified == 1
    assert tally.n == 2


def test_append_event_writes_one_jsonl_line_with_a_tz_aware_timestamp(tmp_path):
    path = tmp_path / "tare.jsonl"
    decision = Decision(cid="a", agent="executor", action="quote", state=DecisionState.EXECUTED)

    append_event(path, "tare.decision", decision)

    lines = path.read_text().splitlines()
    assert len(lines) == 1
    record = json.loads(lines[0])
    assert record["topic"] == "tare.decision"
    assert record["cid"] == "a"
    assert record["state"] == "EXECUTED"
    assert datetime.fromisoformat(record["ts"]).tzinfo is not None


def test_attribution_that_does_not_reconcile_with_pnl_is_rejected():
    with pytest.raises(ValueError, match="attribution"):
        Outcome(
            cid="a",
            status=OutcomeStatus.MEASURED,
            horizon_s=60,
            pnl_usd=-3.86,
            attribution={"spread_usd": 1.00, "fees_usd": -0.50},
        )


def test_attribution_that_reconciles_is_accepted():
    outcome = Outcome(
        cid="a",
        status=OutcomeStatus.MEASURED,
        horizon_s=60,
        pnl_usd=-3.86,
        attribution={
            "spread_usd": 1.42,
            "adverse_selection_usd": -4.90,
            "fees_usd": -0.26,
            "inference_usd": -0.12,
        },
    )

    assert outcome.attribution["adverse_selection_usd"] == -4.90
