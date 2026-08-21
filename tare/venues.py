from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

USDC_DECIMALS = 1_000_000
LAMPORTS_PER_SOL = 1_000_000_000


class ReadState(StrEnum):
    OK = "OK"
    UNAVAILABLE = "UNAVAILABLE"


@dataclass(frozen=True)
class Mark:
    venue: str
    symbol: str
    state: ReadState
    price: float | None = None
    slot: int | None = None
    reason: str | None = None


@dataclass(frozen=True)
class Basis:
    state: ReadState
    value: float | None = None
    pct: float | None = None
    reason: str | None = None


def parse_jupiter_quote(payload: dict) -> Mark:
    out = int(payload["outAmount"]) / USDC_DECIMALS
    inp = int(payload["inAmount"]) / LAMPORTS_PER_SOL
    return Mark(venue="jupiter", symbol="SOL", state=ReadState.OK, price=out / inp)


def parse_phoenix_mark(payload: dict) -> Mark:
    return Mark(
        venue="phoenix",
        symbol=payload["symbol"],
        state=ReadState.OK,
        price=float(payload["markPrice"]["price"]),
        slot=payload.get("slot"),
    )


def basis(spot: Mark, perp: Mark) -> Basis:
    # A leg that could not be read is not a leg worth zero. Computing a basis
    # from a missing side would report a spread that was never observed.
    for leg in (spot, perp):
        if leg.state is not ReadState.OK or leg.price is None:
            return Basis(state=ReadState.UNAVAILABLE, reason=f"{leg.venue}:{leg.reason or 'no_price'}")
    gap = spot.price - perp.price
    return Basis(state=ReadState.OK, value=gap, pct=gap / perp.price * 100)


PHOENIX_BASE = "https://perp-api.phoenix.trade"
JUPITER_BASE = "https://api.jup.ag"
SOL_MINT = "So11111111111111111111111111111111111111112"
USDC_MINT = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"


def _get_json(url: str, timeout: float) -> dict:
    import json
    import urllib.request

    with urllib.request.urlopen(url, timeout=timeout) as response:
        return json.loads(response.read())


def fetch_phoenix_mark(symbol: str, base: str = PHOENIX_BASE, timeout: float = 8.0) -> Mark:
    try:
        return parse_phoenix_mark(_get_json(f"{base}/v1/market/{symbol}/mark-price", timeout))
    except Exception as exc:
        # Fail into a state, never into an exception reaching the book and never
        # into a zero that would read as a real quote.
        return Mark(
            venue="phoenix", symbol=symbol, state=ReadState.UNAVAILABLE,
            reason=type(exc).__name__.lower(),
        )


def fetch_jupiter_spot(
    lamports: int = LAMPORTS_PER_SOL, base: str = JUPITER_BASE, timeout: float = 8.0
) -> Mark:
    url = (
        f"{base}/swap/v1/quote?inputMint={SOL_MINT}&outputMint={USDC_MINT}"
        f"&amount={lamports}&slippageBps=50"
    )
    try:
        return parse_jupiter_quote(_get_json(url, timeout))
    except Exception as exc:
        return Mark(
            venue="jupiter", symbol="SOL", state=ReadState.UNAVAILABLE,
            reason=type(exc).__name__.lower(),
        )
