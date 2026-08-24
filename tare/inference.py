from __future__ import annotations

import base64
import json
from dataclasses import dataclass

MICROUNITS_PER_USD = 1_000_000
LAMPORTS_PER_SOL = 1_000_000_000


@dataclass(frozen=True)
class Rail:
    network: str
    asset: str
    pay_to: str
    amount_microunits: int
    mode: str


@dataclass(frozen=True)
class Quote:
    quote_id: str
    model: str
    rails: list[Rail]


def parse_quote(payment_required_header: str) -> Quote:
    raw = json.loads(base64.b64decode(payment_required_header))
    rails = [
        Rail(
            network=a["network"],
            asset=str(a["asset"]),
            pay_to=a["pay_to"],
            amount_microunits=int(a["amount_microunits"]),
            mode=a.get("mode", ""),
        )
        for a in raw["accepts"]
    ]
    return Quote(quote_id=raw["quote_id"], model=raw["accepts"][0].get("model", ""), rails=rails)


def select_rail(quote: Quote, asset: str = "USDC") -> Rail:
    # Solana only, and never by default: the live gateway also quotes Base
    # (eip155:8453) and the plain JSON error body defaults to it. Onchain Solana
    # volume is a judging criterion, so the rail is chosen, never inherited.
    for rail in quote.rails:
        if rail.network.startswith("solana:") and rail.asset == asset:
            return rail
    raise ValueError(f"no solana rail quoted for asset {asset}")


@dataclass(frozen=True)
class InferenceEvent:
    cid: str
    model: str
    quoted_micro: int
    charged_micro: int
    route: str
    rail: str
    settle: str = "onchain"
    tx: str | None = None

    def __post_init__(self) -> None:
        if self.charged_micro > self.quoted_micro:
            raise ValueError("charged_micro exceeds the quoted cap")

    @property
    def onchain(self) -> bool:
        # Surplus settles by signature against prior credit — no transaction,
        # therefore no onchain volume. Reported, never chosen silently.
        return self.settle == "onchain"


def build_payment_proof(quote: Quote, rail: Rail, payer: str, signature: str) -> str:
    # The gateway matches a payment to its quote by id. A proof echoing the
    # wrong quote settles nothing and the money is simply gone, so the quote
    # and rail are carried through rather than restated by the caller.
    return base64.b64encode(
        json.dumps(
            {
                "quote_id": quote.quote_id,
                "network": rail.network,
                "asset": rail.asset,
                "payer_wallet": payer,
                "signature": signature,
            }
        ).encode()
    ).decode()


def fee_dominance(charged_micro: int, lamports_fee: int, sol_usd: float) -> float:
    # How many times the settlement costs more than the thing it settles.
    # Measured 24/08 on a real call: 8 microunits of inference against a
    # 5,000-lamport fee is roughly 120x. This is why surplus settlement is not
    # a convenience — on-chain settlement of a sub-cent purchase is the
    # expensive path, and the instrument should say so rather than imply the
    # inference price is the cost.
    inference_usd = charged_micro / MICROUNITS_PER_USD
    fee_usd = lamports_fee / LAMPORTS_PER_SOL * sol_usd
    return fee_usd / inference_usd if inference_usd else float("inf")
