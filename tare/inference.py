from __future__ import annotations

import base64
import json
from dataclasses import dataclass


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
