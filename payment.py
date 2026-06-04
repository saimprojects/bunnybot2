"""
Payment helpers for the Telegram shop bot.

This module provides helper functions to work with Binance Pay and
wallet payments.  Binance API keys and wallet settings are read
from ``config.py``.  The helpers do not themselves initiate any
transactions; they only verify transaction history and parse
responses.  Wallet balance changes and orders are handled via
``database.py``.
"""

import time
import json
import hmac
import hashlib
import urllib.parse
import urllib.request
import urllib.error
from html import escape as html_escape

import config
import database


# Custom emoji IDs for payment messages.  Only custom emojis are used.
EMOJIS = {
    "cancel": "5210952531676504517",   # ❌
    "confirm": "5206607081334906820",  # ✅
    "binance": "6222208096257712941", # Binance icon
}


def tg(emoji_id: str, fallback: str) -> str:
    """Return a Telegram custom emoji span."""
    return f'<tg-emoji emoji-id="{emoji_id}">{fallback}</tg-emoji>'


def safe(value) -> str:
    return html_escape(str(value)) if value is not None else ""


def get_binance_pay_id() -> str:
    """Return the configured Binance Pay ID or wallet address."""
    return (
        getattr(config, "BINANCE_PAY_ID", "")
        or getattr(config, "BINANCE_WALLET_ADDRESS", "")
    ).strip()


def sign_query(params: dict) -> str:
    secret = config.BINANCE_API_SECRET.strip()
    query = urllib.parse.urlencode(params)
    signature = hmac.new(
        secret.encode("utf-8"),
        query.encode("utf-8"),
        hashlib.sha256
    ).hexdigest()
    return query + "&signature=" + signature


def binance_signed_get(path: str, params: dict):
    api_key = config.BINANCE_API_KEY.strip()
    api_secret = config.BINANCE_API_SECRET.strip()
    if not api_key or not api_secret:
        return False, "BINANCE_API_KEY / BINANCE_API_SECRET missing."
    params["timestamp"] = int(time.time() * 1000)
    params.setdefault("recvWindow", 5000)
    query = sign_query(params)
    url = "https://api.binance.com" + path + "?" + query
    req = urllib.request.Request(
        url,
        headers={
            "X-MBX-APIKEY": api_key,
            "Content-Type": "application/json",
        },
        method="GET"
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as response:
            raw = response.read().decode("utf-8")
            return True, json.loads(raw)
    except urllib.error.HTTPError as e:
        try:
            body = e.read().decode("utf-8")
        except Exception:
            body = str(e)
        return False, f"Binance HTTP error: {body}"
    except Exception as e:
        return False, f"Binance API error: {e}"


def get_pay_trade_history(minutes: int = 10, limit: int = 100):
    now_ms = int(time.time() * 1000)
    start_ms = now_ms - (minutes * 60 * 1000)
    params = {
        "startTime": start_ms,
        "endTime": now_ms,
        "limit": min(int(limit), 100),
    }
    return binance_signed_get("/sapi/v1/pay/transactions", params)


def get_transaction_amount_usdt(tx: dict):
    try:
        currency = str(tx.get("currency", "")).upper().strip()
        amount = float(tx.get("amount", 0))
        if currency in ("USDT", "USD"):
            return amount
    except Exception:
        pass
    for item in tx.get("fundsDetail", []) or []:
        try:
            currency = str(item.get("currency", "")).upper().strip()
            amount = float(item.get("amount", 0))
            if currency in ("USDT", "USD"):
                return amount
        except Exception:
            continue
    return None


def receiver_matches_our_binance_id(tx: dict) -> bool:
    our_id = get_binance_pay_id()
    if not our_id:
        return True
    receiver = tx.get("receiverInfo") or {}
    possible_ids = [
        receiver.get("binanceId"),
        receiver.get("accountId"),
        receiver.get("email"),
        receiver.get("phoneNumber"),
    ]
    possible_ids = [str(x).strip() for x in possible_ids if x]
    if not possible_ids:
        return True
    return our_id in possible_ids


def find_binance_payment_reference(reference: str, expected_amount: float, minutes_order: int = 10, minutes_offchain: int = 5):
    ref = str(reference).strip()
    expected = float(expected_amount)
    ok, result = get_pay_trade_history(minutes=minutes_order, limit=100)
    if not ok:
        return False, str(result)
    txs = result.get("data", [])
    for tx in txs:
        tx_id = str(tx.get("merchantTradeNo")) or str(tx.get("prepayId")) or ""
        if tx_id and ref.lower() in tx_id.lower():
            if not receiver_matches_our_binance_id(tx):
                continue
            amount = get_transaction_amount_usdt(tx)
            if amount is None:
                continue
            if abs(amount - expected) > 0.01:
                continue
            return True, tx
    return False, "No matching transaction found."
