from __future__ import annotations

import statistics
from dataclasses import dataclass

# The /v1/funding/overview series reports fundingRate as the published
# percentage multiplied by one hundred. Reconciled against
# /v1/funding/{symbol}/rates at identical timestamps on 21/08: ratio 100.00.
# Reading it as a percentage overstates every carry number by 100x.
FUNDING_RATE_SCALE = 100

MIN_PERIODS = 24


@dataclass(frozen=True)
class Carry:
    symbol: str
    mark: float
    pct_per_period: float
    pct_per_day: float
    apr_pct: float
    hours_to_clear_fees: float
    persistence: float
    n: int


def analyse_market(series: dict, round_trip_fee_pct: float) -> Carry | None:
    # A period with a zero rate has not settled. Averaging it in drags the mean
    # toward zero and reports a carry nobody could have earned.
    points = [p for p in series.get("points", []) if float(p.get("fundingRate") or 0) != 0]
    if len(points) < MIN_PERIODS:
        return None

    rates = [float(p["fundingRate"]) / FUNDING_RATE_SCALE for p in points]
    stamps = [p["timestamp"] for p in points]
    hours = (stamps[-1] - stamps[0]) / 3600 / (len(stamps) - 1)
    mean = statistics.fmean(rates)
    if mean == 0:
        return None
    # Persistence, not the mean, is what a multi-day carry trade lives on:
    # the sign must hold for the whole holding period, and an average hides that.
    same_sign = sum(1 for r in rates if (r > 0) == (mean > 0))
    per_day = mean * (24 / hours)

    return Carry(
        symbol=series["symbol"],
        mark=float(points[-1]["markPrice"]),
        pct_per_period=mean,
        pct_per_day=per_day,
        apr_pct=per_day * 365,
        hours_to_clear_fees=round_trip_fee_pct / abs(mean) * hours,
        persistence=same_sign / len(rates),
        n=len(rates),
    )
