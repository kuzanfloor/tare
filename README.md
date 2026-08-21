# tare

*Tare: the weight you subtract to get the true measure.*

A delta-neutral book on Solana — Jupiter spot against Phoenix perps — and an
instrument that refuses to guess.

The trading is not the interesting part. The interesting part is that this system
declines to state things it cannot prove, and publishes the declining.

---

## The rule everything else follows from

> **A fill that could not be confirmed is never recorded as zero P&L.**

Zero is a value. Not knowing is not a value. Most systems have two states — it
worked, or it didn't — and unconfirmed outcomes quietly become flat, because flat
is what an empty field looks like. Flat also looks like safety.

## Three states, never two

| | |
|---|---|
| **Decision** | `EXECUTED` · `REJECTED` · `SKIPPED` · `FAILED` · **`UNVERIFIED`** |
| **Outcome** | `MEASURED` · `PENDING` · **`COULD_NOT_MEASURE`** |
| **Delta** | `NEUTRAL` · `DIRECTIONAL` · **`UNKNOWN`** |

The bold ones are the point. They are enforced in code, not by convention:

- `COULD_NOT_MEASURE` **requires** a reason and **forbids** a P&L — checked with
  `is not None`, because `0.0` is falsy and zero is the value that lies.
- An aggregate keeps unmeasured rows in the denominator. `n` is the number of
  things that happened, not the number that were convenient to measure.
- Paper results are never aggregated with live ones.
- A P&L decomposition that does not reconcile with the total is rejected. You
  cannot publish a breakdown into spread, adverse selection, fees and inference
  cost unless the numbers actually add up.

## What that looks like when it matters

```
reported delta: 0.0    status: UNKNOWN
```

A hedge was sent. The acknowledgement never arrived. The arithmetic says flat —
and the book says it does not know that, refuses every further order, and writes
`delta_unknown_unconfirmed_fills` into the journal.

The ordinary failure here is not exotic. A conventional book marks the hedge
filled, reports delta zero, calls itself delta-neutral and keeps trading, while
carrying naked directional exposure it cannot see. It is invisible precisely when
it matters.

**Refusals are journalled like executions.** A system that records only what it
did cannot evidence what it declined to do — and the refusals *are* the risk
control.

---

## A number this repository published wrong, and how it was caught

The first run of the carry scan reported **908% APR on SOL** and 1887% on BNB.

Those are absurd on their face, which is the only reason they were checked. Phoenix
exposes funding through two endpoints. `/v1/funding/overview` reports `fundingRate`;
`/v1/funding/{symbol}/rates` reports `fundingRatePercentage`. Compared at identical
timestamps, the ratio is exactly **100.00**. The first is not a percentage.

Every carry number was inflated one hundred-fold, and the table looked entirely
plausible. It would have been published.

The scale factor is now a named constant with a regression test that reconciles the
two endpoints against real captured responses. The test exists because the number
was wrong, not because the number was suspicious.

*A quantity computed correctly from the wrong input passes every test that asserts
the same wrong quantity. The check costs one query and has to come before the
number, not after.*

## What the corrected scan found

68 markets, 166 hours of funding history, against a 0.07% round-trip perp fee:

| market | %/day | APR | days to clear fees | persistence |
|---|---:|---:|---:|---:|
| BNB | 0.0517 | 18.9% | 1.4 | 100% |
| NEAR | 0.0434 | 15.8% | 1.6 | 98% |
| GOLD | 0.0307 | 11.2% | 2.3 | 93% |
| SOL | 0.0250 | 9.1% | 2.8 | 97% |
| BTC | −0.0062 | −2.3% | 11.3 | **39%** |

**Nothing clears its fees intraday.** This is not a market-making strategy; it is a
carry trade with multi-day holds. That conclusion came from the data, and it
contradicted the premise the project started with.

**Persistence, not the mean, is what the trade lives on.** BTC averages negative
carry and would look tradeable on the mean alone — but the sign holds in only 39%
of periods, which is a coin flip with fees attached. Two markets with an identical
mean are not the same trade, and the test suite contains that case explicitly.

## Inference is priced before it is bought

Model calls are routed through [UsePod](https://usepod.ai) over x402. The `402`
response carries a **binding, per-request price quote, free, before the call is
made**. So judgment is purchased only when it can still change the outcome, and
only when it is cheap against what is being decided.

| stake | model | quote | % of stake | |
|---:|---|---:|---:|---|
| $0.10 | glm-5.1 | $0.005353 | 5.353% | not bought |
| $0.10 | deepseek-v3.2 | $0.000707 | 0.707% | bought |
| $5.00 | glm-5.1 | $0.005353 | 0.107% | bought |

Two details that are easy to get wrong, and are handled explicitly:

- The gateway quotes **three** rails, including Base — and the plain error body
  defaults to it. The Solana rail is selected, never inherited.
- Settling against surplus credit produces **no on-chain transaction**. That is
  cheaper, and it is reported rather than chosen silently.

The risk gates never call a model. A comparison answers them, so inference there
would be a flaky if-else that costs money on every tick.

---

## Run it

```
pytest
```

42 tests, no network required. Each was written and watched fail before the code
that satisfies it. Venue payloads in `tests/fixtures/` are real captured responses,
not invented ones.

```
tare/events.py     decision and outcome records, and the states they may hold
tare/book.py       position, delta, inventory cap
tare/loop.py       the deterministic gate ladder, and the journal
tare/judgment.py   whether a judgment is worth buying
tare/inference.py  x402 quote parsing and rail selection
tare/venues.py     Jupiter spot, Phoenix perps
tare/scan.py       carry against cost, across every market
```

## What this does not claim

- **No orders have ever been placed.** Reads only. Paper mode is the default in the
  code, not a configuration.
- **No realised performance.** 166 hours is one regime. A month of green is what
  negative expectancy looks like, right up until it isn't.
- **The carry table is a measurement, not a recommendation.** It says what funding
  did, not what it will do.
- **GOLD, WTIOIL and the equity perps follow exchange calendars and close.** Holding
  a hedge across a closure means the reference market is shut while the position is
  open. That is structural, not a bug to be fixed, and it is unhandled today.

Built for the [AnsemHack Clawrena](https://clawpump.tech/ansemhack).
