import json

from tare.history import append_reading, load_history


def test_each_reading_is_appended_not_overwritten(tmp_path):
    path = tmp_path / "history.jsonl"

    append_reading(path, {"generated_at": "2026-08-22T10:00:00+00:00", "carry": []})
    append_reading(path, {"generated_at": "2026-08-22T11:00:00+00:00", "carry": []})

    assert len(load_history(path)) == 2


def test_history_keeps_the_newest_when_it_reaches_its_ceiling(tmp_path):
    path = tmp_path / "history.jsonl"

    for hour in range(6):
        append_reading(path, {"generated_at": f"2026-08-22T{hour:02d}:00:00+00:00", "carry": []}, max_entries=4)

    kept = load_history(path)
    assert len(kept) == 4
    assert kept[0]["generated_at"].startswith("2026-08-22T02")
    assert kept[-1]["generated_at"].startswith("2026-08-22T05")


def test_a_reading_keeps_only_what_the_history_needs(tmp_path):
    path = tmp_path / "history.jsonl"

    append_reading(path, {
        "generated_at": "2026-08-22T10:00:00+00:00",
        "delta_status": "UNKNOWN",
        "decisions": 10,
        "carry": [{"symbol": "SOL", "apr_pct": 9.1, "persistence": 0.97, "verdict": "hold", "why": "open continuously"}],
    })

    entry = load_history(path)[0]
    assert entry["carry"][0] == {"symbol": "SOL", "apr_pct": 9.1, "persistence": 0.97, "verdict": "hold"}
    assert "why" not in entry["carry"][0]


def test_span_reports_how_much_history_actually_exists(tmp_path):
    from tare.history import history_span

    path = tmp_path / "history.jsonl"
    for hour in (10, 11, 14):
        append_reading(path, {"generated_at": f"2026-08-22T{hour:02d}:00:00+00:00", "carry": []})

    span = history_span(load_history(path))

    assert span["entries"] == 3
    # 10:00 to 14:00 is four hours elapsed across three readings — the gap at
    # 12 and 13 is visible in the count, not smoothed away
    assert span["span_h"] == 4.0
    assert span["first"].startswith("2026-08-22T10")


def test_span_of_an_empty_history_claims_nothing():
    from tare.history import history_span

    span = history_span([])

    assert span["entries"] == 0
    assert span["span_h"] is None
