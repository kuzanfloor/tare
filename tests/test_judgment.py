from tare.events import Decision, DecisionState
from tare.judgment import should_buy_judgment


def _decision(state: DecisionState) -> Decision:
    return Decision(cid="c-1", agent="risk", action="rebalance", state=state)


def test_judgment_is_not_purchased_when_the_gates_already_refused():
    refused = _decision(DecisionState.REJECTED)

    assert should_buy_judgment(refused, stake_usd=100.0, quoted_micro=8) is False


def test_judgment_is_not_purchased_when_the_gates_already_skipped():
    skipped = _decision(DecisionState.SKIPPED)

    assert should_buy_judgment(skipped, stake_usd=100.0, quoted_micro=8) is False


def test_judgment_is_refused_when_it_costs_too_much_against_the_stake():
    go = _decision(DecisionState.EXECUTED)

    # glm-5.1 quoted 5353 microunits live = $0.005353. Against a $0.10 stake
    # that is 5.4% of what is being decided — not worth buying.
    assert should_buy_judgment(go, stake_usd=0.10, quoted_micro=5353) is False


def test_judgment_is_bought_when_it_is_cheap_against_the_stake():
    go = _decision(DecisionState.EXECUTED)

    # the same quote against a $100 stake is 0.005% — buy it
    assert should_buy_judgment(go, stake_usd=100.0, quoted_micro=5353) is True
