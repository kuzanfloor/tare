"""Buy one inference call and pay for it on Solana.

The pure parts — quote parsing, rail selection, proof construction — live in
`tare.inference` and are tested there. This module is the I/O around them.
"""

from __future__ import annotations

import base64
import json
import os
import time
import urllib.error
import urllib.request
from pathlib import Path

from tare.inference import InferenceEvent, build_payment_proof, parse_quote, select_rail

USEPOD = "https://api.usepod.ai/proxy/x402/v1/chat/completions"
RPC = "https://api.mainnet-beta.solana.com"
USDC_MINT = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"
KEYPAIR = Path.home() / ".config" / "kuzanfloor" / "x402-keypair.json"

# UsePod sits behind Cloudflare, which 403s urllib's default agent with error
# 1010. That failure reads like an auth problem and is not one.
UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0 Safari/537.36"


def _header(headers: dict, name: str) -> str | None:
    for key, value in headers.items():
        if key.lower() == name.lower():
            return value
    return None


def _rpc(method: str, params: list) -> dict:
    request = urllib.request.Request(
        RPC,
        data=json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params}).encode(),
        headers={"Content-Type": "application/json", "User-Agent": UA},
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.loads(response.read())


def _post(body: bytes, extra: dict | None = None) -> tuple[int, dict, bytes]:
    request = urllib.request.Request(USEPOD, data=body, method="POST")
    request.add_header("Content-Type", "application/json")
    request.add_header("User-Agent", UA)
    for key, value in (extra or {}).items():
        request.add_header(key, value)
    try:
        with urllib.request.urlopen(request, timeout=90) as response:
            return response.status, dict(response.headers), response.read()
    except urllib.error.HTTPError as error:
        return error.code, dict(error.headers), error.read()


def buy_one(cid: str, prompt: str, model: str = "deepseek-v3.2", max_tokens: int = 16):
    """Quote, pay on the Solana rail, settle. Returns (InferenceEvent, reply) or None.

    Returns None rather than raising: a publisher that cannot buy inference must
    report that it bought none, not crash and leave the last reading standing.
    """
    from solders.hash import Hash
    from solders.keypair import Keypair
    from solders.message import Message
    from solders.pubkey import Pubkey
    from solders.transaction import Transaction
    from spl.token.constants import TOKEN_PROGRAM_ID
    from spl.token.instructions import get_associated_token_address, transfer_checked
    from spl.token.models import TransferCheckedParams

    if not KEYPAIR.exists():
        return None
    keypair = Keypair.from_bytes(bytes(json.loads(KEYPAIR.read_text())))
    mint = Pubkey.from_string(USDC_MINT)

    # Serialised once. The quote binds a hash of method, path and body, so the
    # settling request must be byte-identical to the one that was quoted.
    body = json.dumps(
        {"model": model, "messages": [{"role": "user", "content": prompt}], "max_tokens": max_tokens}
    ).encode()

    status, headers, _ = _post(body)
    quoted = _header(headers, "payment-required")
    if status != 402 or not quoted:
        return None
    quote = parse_quote(quoted)
    rail = select_rail(quote, "USDC")  # fails closed rather than falling to Base

    instruction = transfer_checked(
        TransferCheckedParams(
            program_id=TOKEN_PROGRAM_ID,
            source=get_associated_token_address(keypair.pubkey(), mint),
            mint=mint,
            dest=get_associated_token_address(Pubkey.from_string(rail.pay_to), mint),
            owner=keypair.pubkey(),
            amount=rail.amount_microunits,
            decimals=6,
            signers=[],
        )
    )
    blockhash = Hash.from_string(
        _rpc("getLatestBlockhash", [{"commitment": "finalized"}])["result"]["value"]["blockhash"]
    )
    transaction = Transaction(
        [keypair], Message.new_with_blockhash([instruction], keypair.pubkey(), blockhash), blockhash
    )
    sent = _rpc("sendTransaction", [base64.b64encode(bytes(transaction)).decode(), {"encoding": "base64"}])
    if "error" in sent:
        return None
    signature = sent["result"]

    for _ in range(40):
        state = _rpc("getSignatureStatuses", [[signature], {"searchTransactionHistory": True}])
        value = state["result"]["value"][0]
        if value and value.get("confirmationStatus") in ("confirmed", "finalized"):
            if value.get("err"):
                return None
            break
        time.sleep(2)
    else:
        return None

    proof = build_payment_proof(quote, rail, str(keypair.pubkey()), signature)
    status, headers, payload = _post(body, {"PAYMENT-SIGNATURE": proof})
    if status != 200:
        return None

    answer = json.loads(payload)
    charged = answer.get("usage", {}).get("cost")
    event = InferenceEvent(
        cid=cid,
        model=model,
        quoted_micro=rail.amount_microunits,
        # Charged is reported by the gateway in dollars; the cap is what left
        # the wallet, so charged can never exceed it.
        charged_micro=min(int(round((charged or 0) * 1_000_000)), rail.amount_microunits),
        route=_header(headers, "x-pod-route") or "unknown",
        rail="solana",
        settle="onchain",
        tx=signature,
    )
    return event, answer["choices"][0]["message"]["content"].strip()
