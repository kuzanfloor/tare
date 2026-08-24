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


def test_payment_proof_echoes_the_quote_it_settles():
    import base64
    import json as _json

    from tare.inference import build_payment_proof

    quote = parse_quote(real_quote_header())
    rail = select_rail(quote, "USDC")

    proof = build_payment_proof(quote, rail, payer="PayerPubkey11111", signature="SigABC")

    decoded = _json.loads(base64.b64decode(proof))
    # the gateway matches the payment to the quote by id; a proof that echoes
    # the wrong quote settles nothing and the money is simply gone
    assert decoded["quote_id"] == quote.quote_id
    assert decoded["network"] == rail.network
    assert decoded["network"].startswith("solana:")
    assert decoded["asset"] == "USDC"
    assert decoded["payer_wallet"] == "PayerPubkey11111"
    assert decoded["signature"] == "SigABC"


def test_settlement_fee_dominates_the_inference_it_buys():
    from tare.inference import fee_dominance

    # measured 24/08: an 8-microunit call settled with a 5,000-lamport fee
    ratio = fee_dominance(charged_micro=8, lamports_fee=5000, sol_usd=94.0)

    assert ratio > 50
