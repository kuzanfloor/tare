import json
from pathlib import Path

import pytest

from tare.venues import (
    Mark,
    ReadState,
    basis,
    fetch_phoenix_mark,
    parse_jupiter_quote,
    parse_phoenix_mark,
)

FIX = Path(__file__).parent / "fixtures"


def test_basis_is_unavailable_when_either_leg_could_not_be_read():
    spot = parse_jupiter_quote(json.loads((FIX / "jupiter_quote.json").read_text()))
    perp = Mark(venue="phoenix", symbol="SOL", state=ReadState.UNAVAILABLE, reason="http_503")

    result = basis(spot, perp)

    assert result.state is ReadState.UNAVAILABLE
    assert result.value is None
    assert result.pct is None


def test_basis_is_the_signed_gap_between_spot_and_mark():
    spot = parse_jupiter_quote(json.loads((FIX / "jupiter_quote.json").read_text()))
    perp = parse_phoenix_mark(json.loads((FIX / "phoenix_mark.json").read_text()))

    result = basis(spot, perp)

    assert result.state is ReadState.OK
    assert result.value == pytest.approx(spot.price - perp.price, abs=1e-9)


def test_a_venue_that_cannot_be_reached_reports_unavailable_not_a_price():
    # unroutable host — the read must fail into a state, never into an exception
    # reaching the book and never into a zero that looks like a real quote.
    mark = fetch_phoenix_mark("SOL", base="https://perp-api.invalid.localhost", timeout=2)

    assert mark.state is ReadState.UNAVAILABLE
    assert mark.price is None
    assert mark.reason
