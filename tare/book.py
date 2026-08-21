from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

NEUTRAL_BAND = 0.01


class DeltaStatus(StrEnum):
    NEUTRAL = "NEUTRAL"
    DIRECTIONAL = "DIRECTIONAL"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class Position:
    spot_qty: float = 0.0
    perp_qty: float = 0.0

    @property
    def delta(self) -> float:
        return self.spot_qty + self.perp_qty

    @property
    def gross(self) -> float:
        return abs(self.spot_qty) + abs(self.perp_qty)


@dataclass(frozen=True)
class Fill:
    venue: str
    qty: float
    confirmed: bool


class Book:
    def __init__(self, inventory_cap: float = float("inf")) -> None:
        self.position = Position()
        self.inventory_cap = inventory_cap
        self.unconfirmed = 0
        self._pending_gross = 0.0

    def apply_fill(self, fill: Fill) -> None:
        # An unconfirmed fill moves nothing. Assuming a hedge landed when it did
        # not is how a "delta-neutral" book becomes quietly directional.
        if not fill.confirmed:
            self.unconfirmed += 1
            self._pending_gross += abs(fill.qty)
            return
        if fill.venue == "phoenix":
            self.position = Position(self.position.spot_qty, self.position.perp_qty + fill.qty)
        else:
            self.position = Position(self.position.spot_qty + fill.qty, self.position.perp_qty)

    def delta_status(self) -> DeltaStatus:
        # Three states, never two. With a fill outstanding we cannot assert
        # neutrality *or* exposure — and "unknown" must not round to "fine".
        if self.unconfirmed:
            return DeltaStatus.UNKNOWN
        if abs(self.position.delta) <= NEUTRAL_BAND:
            return DeltaStatus.NEUTRAL
        return DeltaStatus.DIRECTIONAL

    def would_breach_cap(self, qty: float) -> bool:
        # Deliberately asymmetric with apply_fill: for *reporting* an unconfirmed
        # fill is unknown, but for *risk* it is assumed to have landed. Both
        # directions err toward safety.
        return self.position.gross + self._pending_gross + abs(qty) > self.inventory_cap
