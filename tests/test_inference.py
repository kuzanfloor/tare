from pathlib import Path

import pytest

from tare.inference import InferenceEvent, parse_quote, select_rail

FIXTURE = Path(__file__).parent / "fixtures" / "quote_402.b64"


def real_quote_header() -> str:
    return FIXTURE.read_text().strip()


def test_parse_quote_reads_every_rail_from_a_real_402():
    quote = parse_quote(real_quote_header())

    assert quote.quote_id
    assert len(quote.rails) == 3
    assert {r.network.split(":")[0] for r in quote.rails} == {"solana", "eip155"}


def test_solana_usdc_rail_is_selected_and_base_is_never_returned():
    quote = parse_quote(real_quote_header())

    rail = select_rail(quote, asset="USDC")

    assert rail.network.startswith("solana:")
    assert not rail.network.startswith("eip155")
    assert rail.asset == "USDC"


def test_select_rail_fails_closed_when_the_requested_rail_is_absent():
    quote = parse_quote(real_quote_header())

    with pytest.raises(ValueError, match="no solana rail"):
        select_rail(quote, asset="DOGE")


def test_charged_cannot_exceed_the_quoted_cap():
    with pytest.raises(ValueError, match="cap"):
        InferenceEvent(
            cid="a",
            model="deepseek-v3-2",
            quoted_micro=707,
            charged_micro=900,
            route="marketplace",
            rail="solana",
        )


def test_surplus_settlement_is_recorded_as_producing_no_onchain_volume():
    event = InferenceEvent(
        cid="a",
        model="deepseek-v3-2",
        quoted_micro=707,
        charged_micro=412,
        route="marketplace",
        rail="solana",
        settle="surplus",
    )

    assert event.onchain is False
