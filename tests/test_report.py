from tare.book import Book, Fill
from tare.loop import step
from tare.report import build_snapshot


def test_snapshot_breaks_refusals_down_by_reason(tmp_path):
    journal = tmp_path / "tare.jsonl"

    directional = Book(inventory_cap=100.0)
    directional.apply_fill(Fill(venue="jupiter", qty=10.0, confirmed=True))
    step(directional, proposed_qty=10.0, cid="c-1", journal=journal)

    unknown = Book(inventory_cap=100.0)
    unknown.apply_fill(Fill(venue="phoenix", qty=-10.0, confirmed=False))
    step(unknown, proposed_qty=5.0, cid="c-2", journal=journal)

    capped = Book(inventory_cap=1.0)
    capped.apply_fill(Fill(venue="jupiter", qty=0.9, confirmed=True))
    step(capped, proposed_qty=5.0, cid="c-3", journal=journal)

    snapshot = build_snapshot(journal)

    assert snapshot.decisions == 3
    assert snapshot.executed == 1
    assert snapshot.refused == 2
    assert snapshot.refusals["delta_unknown_unconfirmed_fills"] == 1
    assert snapshot.refusals["inventory_cap_exceeded"] == 1


def _judge(cid: str, settle: str):
    from tare.inference import InferenceEvent

    def _j(quoted_micro: int) -> InferenceEvent:
        return InferenceEvent(
            cid=cid, model="deepseek-v3-2", quoted_micro=quoted_micro,
            charged_micro=412, route="marketplace", rail="solana", settle=settle,
        )

    return _j


def test_snapshot_separates_onchain_spend_from_surplus_settlement(tmp_path):
    journal = tmp_path / "tare.jsonl"

    for cid, settle in (("c-1", "onchain"), ("c-2", "surplus")):
        book = Book(inventory_cap=100.0)
        book.apply_fill(Fill(venue="jupiter", qty=10.0, confirmed=True))
        step(book, proposed_qty=10.0, cid=cid, journal=journal,
             stake_usd=100.0, quoted_micro=707, judge_fn=_judge(cid, settle))

    snapshot = build_snapshot(journal)

    assert snapshot.inference_calls == 2
    assert snapshot.inference_charged_micro == 824
    assert snapshot.inference_onchain == 1


def test_snapshot_json_keeps_the_refusals_and_the_unbought_judgment_visible(tmp_path):
    from tare.report import snapshot_json

    journal = tmp_path / "tare.jsonl"
    capped = Book(inventory_cap=1.0)
    capped.apply_fill(Fill(venue="jupiter", qty=0.9, confirmed=True))
    step(capped, proposed_qty=5.0, cid="c-1", journal=journal)

    payload = snapshot_json(build_snapshot(journal))

    assert payload["refused"] == 1
    assert payload["refusals"]["inventory_cap_exceeded"] == 1
    assert payload["inference_calls"] == 0


def test_snapshot_json_says_when_it_was_read_and_when_that_goes_stale(tmp_path):
    from datetime import UTC, datetime

    from tare.report import STALE_AFTER_S, snapshot_json

    journal = tmp_path / "tare.jsonl"
    book = Book(inventory_cap=100.0)
    book.apply_fill(Fill(venue="jupiter", qty=1.0, confirmed=True))
    step(book, proposed_qty=1.0, cid="c-1", journal=journal)

    payload = snapshot_json(build_snapshot(journal))

    generated = datetime.fromisoformat(payload["generated_at"])
    assert generated.tzinfo is not None
    assert abs((datetime.now(UTC) - generated).total_seconds()) < 60
    assert payload["stale_after_s"] == STALE_AFTER_S


def test_a_reading_older_than_its_window_is_stale():
    from tare.report import is_stale

    assert is_stale(age_s=3600, stale_after_s=3600) is True
    assert is_stale(age_s=3599, stale_after_s=3600) is False
