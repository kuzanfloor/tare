import json

from tare.book import Book, Fill
from tare.events import DecisionState
from tare.loop import decide, step


def test_no_new_risk_is_opened_while_the_book_delta_is_unknown():
    book = Book(inventory_cap=100.0)
    book.apply_fill(Fill(venue="phoenix", qty=-10.0, confirmed=False))

    decision = decide(book, proposed_qty=5.0, cid="c-1")

    assert decision.state is DecisionState.REJECTED
    assert "unknown" in decision.reason


def test_an_order_breaching_the_inventory_cap_is_rejected_with_its_reason():
    book = Book(inventory_cap=10.0)
    book.apply_fill(Fill(venue="jupiter", qty=8.0, confirmed=True))

    decision = decide(book, proposed_qty=5.0, cid="c-2")

    assert decision.state is DecisionState.REJECTED
    assert decision.reason == "inventory_cap_exceeded"


def test_a_book_already_inside_the_neutral_band_skips_rather_than_trades():
    book = Book(inventory_cap=100.0)
    book.apply_fill(Fill(venue="jupiter", qty=10.0, confirmed=True))
    book.apply_fill(Fill(venue="phoenix", qty=-10.0, confirmed=True))

    decision = decide(book, proposed_qty=5.0, cid="c-3")

    assert decision.state is DecisionState.SKIPPED
    assert decision.reason == "within_neutral_band"


def test_a_step_journals_exactly_one_decision_event(tmp_path):
    journal = tmp_path / "tare.jsonl"
    book = Book(inventory_cap=100.0)
    book.apply_fill(Fill(venue="jupiter", qty=10.0, confirmed=True))

    step(book, proposed_qty=5.0, cid="c-9", journal=journal)

    lines = journal.read_text().splitlines()
    assert len(lines) == 1
    assert json.loads(lines[0])["topic"] == "tare.decision"


def test_a_refusal_is_journalled_just_like_an_execution(tmp_path):
    journal = tmp_path / "tare.jsonl"
    book = Book(inventory_cap=1.0)
    book.apply_fill(Fill(venue="jupiter", qty=0.9, confirmed=True))

    step(book, proposed_qty=5.0, cid="c-10", journal=journal)

    record = json.loads(journal.read_text().splitlines()[0])
    assert record["state"] == "REJECTED"
    assert record["reason"] == "inventory_cap_exceeded"


def _judge(quoted_micro: int):
    from tare.inference import InferenceEvent

    return InferenceEvent(
        cid="c-11",
        model="deepseek-v3-2",
        quoted_micro=quoted_micro,
        charged_micro=412,
        route="marketplace",
        rail="solana",
    )


def test_a_bought_judgment_is_journalled_after_the_decision(tmp_path):
    journal = tmp_path / "tare.jsonl"
    book = Book(inventory_cap=100.0)
    book.apply_fill(Fill(venue="jupiter", qty=10.0, confirmed=True))

    step(
        book, proposed_qty=10.0, cid="c-11", journal=journal,
        stake_usd=100.0, quoted_micro=707, judge_fn=_judge,
    )

    topics = [json.loads(line)["topic"] for line in journal.read_text().splitlines()]
    assert topics == ["tare.decision", "tare.inference"]


def test_nothing_is_spent_on_judgment_that_cannot_pay_for_itself(tmp_path):
    journal = tmp_path / "tare.jsonl"
    book = Book(inventory_cap=100.0)
    book.apply_fill(Fill(venue="jupiter", qty=10.0, confirmed=True))

    step(
        book, proposed_qty=10.0, cid="c-12", journal=journal,
        stake_usd=0.10, quoted_micro=5353, judge_fn=_judge,
    )

    topics = [json.loads(line)["topic"] for line in journal.read_text().splitlines()]
    assert topics == ["tare.decision"]
