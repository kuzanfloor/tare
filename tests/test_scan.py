import json
from pathlib import Path

from tare.scan import FUNDING_RATE_SCALE, analyse_market

FIX = Path(__file__).parent / "fixtures"


def _overview() -> dict:
    return json.loads((FIX / "phoenix_funding_overview_sol.json").read_text())


def _rates() -> dict:
    return json.loads((FIX / "phoenix_funding_rates_sol.json").read_text())


def test_overview_funding_rate_is_one_hundred_times_the_published_percentage():
    # Regression. The first scan read overview.fundingRate as a percentage and
    # reported 908% APR on SOL. Reconciling the two endpoints at identical
    # timestamps gives exactly 100x. This test exists so that cannot recur.
    by_ts = {p["timestamp"]: float(p["fundingRate"]) for p in _overview()["points"]}
    checked = 0
    for rate in _rates()["rates"]:
        published = float(rate["fundingRatePercentage"])
        raw = by_ts.get(rate["timestamp"])
        if raw is None or published == 0:
            continue
        assert abs(raw / published - FUNDING_RATE_SCALE) < 0.5
        checked += 1
    assert checked >= 5


def test_a_market_with_too_few_settled_periods_is_not_analysed():
    thin = {"symbol": "THIN", "points": _overview()["points"][:5]}

    assert analyse_market(thin, round_trip_fee_pct=0.07) is None


def test_an_unsettled_trailing_period_is_not_averaged_in():
    points = _overview()["points"][:30]
    settled = {"symbol": "SOL", "points": points}
    # the live series ends with a period that has not settled: rate 0.0
    with_pending = {"symbol": "SOL", "points": points + [{**points[-1], "fundingRate": "0.0"}]}

    assert analyse_market(with_pending, 0.07).pct_per_period == (
        analyse_market(settled, 0.07).pct_per_period
    )


def _synthetic(symbol: str, rates: list[str]) -> dict:
    return {
        "symbol": symbol,
        "points": [
            {"timestamp": i * 3600, "fundingRate": r, "markPrice": "1.0"}
            for i, r in enumerate(rates)
        ],
    }


def test_persistence_separates_two_markets_with_the_same_mean():
    # Identical mean carry, completely different trade. A multi-day hold lives
    # on the sign holding for the whole period, which an average hides.
    steady = _synthetic("STEADY", ["0.10"] * 30)
    choppy = _synthetic("CHOPPY", ["0.30" if i % 2 else "-0.10" for i in range(30)])

    s = analyse_market(steady, 0.07)
    c = analyse_market(choppy, 0.07)

    assert s.pct_per_period == c.pct_per_period
    assert s.persistence == 1.0
    assert c.persistence == 0.5


def _carry(symbol: str, hours_to_clear: float):
    from tare.scan import Carry

    return Carry(
        symbol=symbol, mark=1.0, pct_per_period=0.001, pct_per_day=0.024,
        apr_pct=8.8, hours_to_clear_fees=hours_to_clear, persistence=1.0, n=100,
    )


def test_a_market_with_no_calendar_is_open_all_the_way_through():
    from datetime import UTC, datetime

    from tare.scan import survives_to_breakeven

    # crypto returns market_calendar_not_configured — nothing to close
    assert survives_to_breakeven(
        _carry("SOL", 67.0), next_transition=None, now=datetime.now(UTC)
    ) is True


def test_a_calendared_market_that_closes_before_breakeven_is_rejected():
    from datetime import UTC, datetime, timedelta

    from tare.scan import survives_to_breakeven

    now = datetime.now(UTC)
    # GOLD needs 55h of funding to cover its fees; the pit shuts in 8
    assert survives_to_breakeven(
        _carry("GOLD", 55.0), next_transition=now + timedelta(hours=8), now=now
    ) is False
    assert survives_to_breakeven(
        _carry("GOLD", 55.0), next_transition=now + timedelta(hours=80), now=now
    ) is True


def test_carry_rows_carry_their_verdict_and_why():
    from datetime import UTC, datetime, timedelta

    from tare.scan import carry_rows

    now = datetime.now(UTC)
    rows = carry_rows(
        [_carry("SOL", 68.0), _carry("GOLD", 54.0)],
        transitions={"GOLD": now + timedelta(hours=11)},
        now=now,
    )

    by_symbol = {r["symbol"]: r for r in rows}
    assert by_symbol["SOL"]["verdict"] == "hold"
    assert by_symbol["SOL"]["calendar"] == "24/7"
    assert by_symbol["GOLD"]["verdict"] == "reject"
    assert by_symbol["GOLD"]["closes_in_h"] == 11
    assert "closes" in by_symbol["GOLD"]["why"]
