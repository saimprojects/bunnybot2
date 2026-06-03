import time
import json
import hmac
import hashlib
import urllib.parse
import urllib.request
import urllib.error
from html import escape as html_escape

from . import config
from . import database


# Custom Emoji IDs for payment messages.  These are defined here to
# avoid importing the full utils module just for confirmation/cancel
# icons.
EMOJIS = {
    "cancel": "5210952531676504517",   # ❌
    "confirm": "5206607081334906820",  # ✅
    "binance": "6222208096257712941",  # Binance icon
}


def tg(emoji_id, fallback):
    """Return a Telegram custom emoji span.

    The fallback is ignored because the bot uses custom emojis only.
    """
    return f'<tg-emoji emoji-id="{emoji_id}">{fallback}</tg-emoji>'


def safe(value):
    return html_escape(str(value)) if value is not None else ""


def get_binance_pay_id():
    """
    Return the configured Binance Pay ID.  ``BINANCE_PAY_ID`` in the
    environment takes precedence over ``BINANCE_WALLET_ADDRESS``.
    """
    return (
        getattr(config, "BINANCE_PAY_ID", "")
        or getattr(config, "BINANCE_WALLET_ADDRESS", "")
    ).strip()


def sign_query(params):
    """
    Build a signed query string for Binance signed endpoints.  Uses
    HMAC SHA256 with the API secret.
    """
    secret = config.BINANCE_API_SECRET.strip()
    query = urllib.parse.urlencode(params)
    signature = hmac.new(
        secret.encode("utf-8"),
        query.encode("utf-8"),
        hashlib.sha256
    ).hexdigest()
    return query + "&signature=" + signature


def binance_signed_get(path, params):
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


def get_pay_trade_history(minutes=10, limit=100):
    """
    Fetch Binance Pay transaction history for the last ``minutes`` minutes.
    """
    now_ms = int(time.time() * 1000)
    start_ms = now_ms - (minutes * 60 * 1000)

    params = {
        "startTime": start_ms,
        "endTime": now_ms,
        "limit": min(int(limit), 100),
    }

    return binance_signed_get("/sapi/v1/pay/transactions", params)


def get_transaction_amount_usdt(tx):
    """
    Extract the USDT amount from a Binance Pay transaction.  The amount
    may be present as a top‑level ``amount`` field or nested within
    ``fundsDetail``.
    """
    # Direct amount/currency
    try:
        currency = str(tx.get("currency", "")).upper().strip()
        amount = float(tx.get("amount", 0))
        if currency in ("USDT", "USD"):
            return amount
    except Exception:
        pass

    # fundsDetail list
    for item in tx.get("fundsDetail", []) or []:
        try:
            currency = str(item.get("currency", "")).upper().strip()
            amount = float(item.get("amount", 0))
            if currency in ("USDT", "USD"):
                return amount
        except Exception:
            continue

    return None


def receiver_matches_our_binance_id(tx):
    """
    Verify that the receiver in a transaction matches our configured
    Binance ID or Pay ID.  Some API responses may omit ``receiverInfo``
    entirely, in which case this check passes.
    """
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


def find_binance_payment_reference(reference, expected_amount, minutes_order=10, minutes_offchain=5):
    """
    Check Binance Pay history for a transaction matching the provided
    reference and amount.  The search spans the last ``minutes_order``
    minutes of order history and ``minutes_offchain`` minutes for
    off‑chain references.
    """
    ref = str(reference).strip()
    expected = float(expected_amount)

    ok, result = get_pay_trade_history(minutes=minutes_order, limit=100)

    if not ok:
        return False, str(result)

    txs = result.get("data", [])
    if isinstance(txs, dict):
        txs = txs.get("data", []) or txs.get("list", []) or []

    now_ms = int(time.time() * 1000)
    offchain_start = now_ms - (minutes_offchain * 60 * 1000)

    for tx in txs:
        tx_time = int(tx.get("transactionTime", 0) or tx.get("createTime", 0) or 0)

        possible_refs = [
            tx.get("transactionId"),
            tx.get("orderId"),
            tx.get("merchantTradeNo"),
            tx.get("prepayId"),
            tx.get("reference"),
            tx.get("offChainReference"),
            tx.get("offchainReference"),
        ]

        possible_refs = [str(x).strip() for x in possible_refs if x is not None]

        exact_ref_match = ref in possible_refs
        offchain_match = exact_ref_match and (not tx_time or tx_time >= offchain_start)

        if not exact_ref_match and not offchain_match:
            continue

        if not receiver_matches_our_binance_id(tx):
            return False, "Transaction found, but receiver Binance ID does not match."

        amount = get_transaction_amount_usdt(tx)

        if amount is None:
            return False, "Transaction found, but USDT amount could not be read."

        if amount < expected:
            return False, f"Transaction found but amount {amount} is less than required {expected}."

        return True, "Payment verified successfully."

    return False, (
        "Order ID was not found in Binance Pay during the last 10 minutes, "
        "and the off-chain transaction reference was not found during the last 5 minutes. "
        "Please try again."
    )


def process_binance_payment(user_id, order_id, product_id, quantity, total_amount, binance_order_id=None):
    """
    Verify a Binance Pay payment for an order.  If the payment matches
    the expected amount, record a negative transaction in the user's
    wallet.  The actual creation of the order and delivery of items
    happens in the main bot logic.
    """
    if not binance_order_id:
        return False, "Binance Order ID / transaction reference missing."

    print(
        f"[Binance Pay History] Checking ref={binance_order_id}, "
        f"user={user_id}, amount={total_amount} USDT"
    )

    success, msg = find_binance_payment_reference(
        reference=binance_order_id,
        expected_amount=total_amount,
        minutes_order=10,
        minutes_offchain=5,
    )

    if success:
        # Deduct from wallet to reflect the purchase.  The product
        # delivery is handled separately after this function returns.
        database.add_transaction(user_id, "Binance Pay Purchase", -float(total_amount))
        return True, f"{tg(EMOJIS['confirm'], '✅')} Payment verified successfully."

    return False, (
        f"{tg(EMOJIS['cancel'], '❌')} <b>Payment not verified.</b>\n\n"
        f"{safe(msg)}"
    )


def process_wallet_payment(user_id, order_id, product_id, quantity, total_amount):
    user = database.get_user(user_id)
    if not user:
        return False, "User not found."

    current_balance = user[3]

    if current_balance >= total_amount:
        database.update_user_wallet(user_id, -total_amount)
        database.add_transaction(user_id, "Purchase", -total_amount)
        return True, "Payment successful using wallet."

    required = round(total_amount - current_balance, 4)
    return False, (
        f"{tg(EMOJIS['cancel'], '❌')} <b>Insufficient Balance</b>\n\n"
        f"Your Balance: {safe(current_balance)} USDT\n"
        f"Required: {safe(total_amount)} USDT\n"
        f"Short by: {safe(required)} USDT"
    )


def get_binance_payment_details(total_amount):
    binance_id = get_binance_pay_id()

    return (
        f"{tg(EMOJIS['binance'], '💳')} <b>Binance Pay ID Payment</b>\n\n"
        f"Binance ID (tap to copy):\n"
        f"<code>{safe(binance_id)}</code>\n\n"
        f"Amount to transfer: <b>${safe(total_amount)}</b>\n\n"
        f"After payment, click <b>I have sent payment</b>.\n"
        f"Then send your <b>Binance Order ID</b> or <b>off-chain transaction reference</b> for auto verification.\n\n"
        f"━━━━━━━━━━━━━━━━━━"
    )


def get_binance_wallet_deposit_details(amount):
    binance_id = get_binance_pay_id()

    return (
        f"{tg(EMOJIS['binance'], '💳')} <b>Wallet Deposit via Binance Pay ID</b>\n\n"
        f"Binance ID (tap to copy):\n"
        f"<code>{safe(binance_id)}</code>\n\n"
        f"Amount to transfer: <b>${safe(amount)}</b>\n\n"
        f"After payment, click <b>I have sent payment</b>.\n"
        f"Then send your <b>Binance Order ID</b> or <b>off-chain transaction reference</b> for auto verification.\n\n"
        f"━━━━━━━━━━━━━━━━━━"
    )


def process_wallet_deposit_binance(user_id, amount, binance_order_id=None):
    if not binance_order_id:
        return False, "Binance Order ID / transaction reference missing."

    print(
        f"[Binance Pay Wallet Deposit] Checking ref={binance_order_id}, "
        f"user={user_id}, amount={amount} USDT"
    )

    success, msg = find_binance_payment_reference(
        reference=binance_order_id,
        expected_amount=amount,
        minutes_order=10,
        minutes_offchain=5,
    )

    if success:
        database.update_user_wallet(user_id, float(amount))
        database.add_transaction(user_id, "Binance Pay Deposit", float(amount))
        return True, (
            f"{tg(EMOJIS['confirm'], '✅')} <b>Deposit verified successfully.</b>\n\n"
            f"Your wallet has been credited with <b>{safe(amount)} USDT</b>."
        )

    return False, (
        f"{tg(EMOJIS['cancel'], '❌')} <b>Deposit not verified.</b>\n\n"
        f"{safe(msg)}"
    )


def get_wallet_payment_summary(user_id, total_amount):
    user = database.get_user(user_id)
    if not user:
        return "Error: User not found."

    current_balance = user[3]
    status = (
        f"{tg(EMOJIS['confirm'], '✅')} Sufficient"
        if current_balance >= total_amount
        else f"{tg(EMOJIS['cancel'], '❌')} Insufficient"
    )
    return (
        f"{tg(EMOJIS['binance'], '💳')} <b>Wallet Payment Summary</b>\n\n"
        f"Current Balance: <b>{safe(current_balance)} USDT</b>\n"
        f"Total Amount: <b>{safe(total_amount)} USDT</b>\n"
        f"Status: {status}"
    )