import config
import database
import time
import json
import hmac
import hashlib
import urllib.parse
import urllib.request
import urllib.error
from html import escape as html_escape


# Custom Emoji IDs
EMOJIS = {
    "cancel": "5210952531676504517",   # ❌
    "confirm": "5206607081334906820",  # ✅
    "binance": "6222208096257712941",  # Binance icon
}


def tg(emoji_id, fallback):
    return f'<tg-emoji emoji-id="{emoji_id}">{fallback}</tg-emoji>'


def safe(value):
    return html_escape(str(value)) if value is not None else ""


def get_binance_pay_id():
    """
    BINANCE_PAY_ID env mein apni Binance ID / Pay ID set karo.
    Fallback BINANCE_WALLET_ADDRESS rakha hai taake purana config bhi work kare.
    """
    return getattr(config, "BINANCE_PAY_ID", "") or getattr(config, "BINANCE_WALLET_ADDRESS", "")


def sign_query(params):
    """
    Binance signed endpoint ke liye HMAC SHA256 query signature.
    /sapi/v1/pay/transactions standard Binance signed endpoint hai.
    """
    query = urllib.parse.urlencode(params)
    signature = hmac.new(
        config.BINANCE_API_SECRET.encode("utf-8"),
        query.encode("utf-8"),
        hashlib.sha256
    ).hexdigest()
    return query + "&signature=" + signature


def binance_signed_get(path, params):
    if not config.BINANCE_API_KEY or not config.BINANCE_API_SECRET:
        return False, "BINANCE_API_KEY / BINANCE_API_SECRET missing."

    params["timestamp"] = int(time.time() * 1000)
    params.setdefault("recvWindow", 5000)

    query = sign_query(params)
    url = "https://api.binance.com" + path + "?" + query

    req = urllib.request.Request(
        url,
        headers={
            "X-MBX-APIKEY": config.BINANCE_API_KEY,
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
    Binance Pay History:
    GET /sapi/v1/pay/transactions

    Last `minutes` ka data fetch karta hai.
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
    Binance Pay history mein amount main amount field ya fundsDetail ke andar aa sakta hai.
    USDT amount nikalne ki koshish karta hai.
    """
    # Direct amount/currency
    try:
        currency = str(tx.get("currency", "")).upper()
        amount = float(tx.get("amount", 0))
        if currency in ("USDT", "USD"):
            return amount
    except Exception:
        pass

    # fundsDetail list
    for item in tx.get("fundsDetail", []) or []:
        try:
            currency = str(item.get("currency", "")).upper()
            amount = float(item.get("amount", 0))
            if currency in ("USDT", "USD"):
                return amount
        except Exception:
            continue

    return None


def receiver_matches_our_binance_id(tx):
    """
    Safety check: payment receiver hamara Binance ID/Pay ID ho.
    Agar response mein receiverInfo available hai to match karega.
    Agar API own account ka history de raha hai aur receiverInfo missing/different hai,
    is check ko soft rakha gaya hai.
    """
    our_id = str(get_binance_pay_id()).strip()
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
    User ka diya hua Binance Order ID / off-chain transaction reference verify karta hai.

    Logic:
    - Last 10 minutes ki Binance Pay history fetch.
    - transactionId ya related reference exact match.
    - Amount expected_amount ke barabar ya zyada.
    - Receiver hamara Binance ID/Pay ID.
    """
    ref = str(reference).strip()
    expected = float(expected_amount)

    # screenshot jaisa: order ID last 10 min, off-chain ref last 5 min.
    ok, result = get_pay_trade_history(minutes=minutes_order, limit=100)

    if not ok:
        return False, str(result)

    txs = result.get("data", [])
    if isinstance(txs, dict):
        txs = txs.get("data", []) or txs.get("list", []) or []

    now_ms = int(time.time() * 1000)
    offchain_start = now_ms - (minutes_offchain * 60 * 1000)

    checked = 0

    for tx in txs:
        checked += 1

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

        # Off-chain reference ke liye recent 5 min check.
        offchain_match = exact_ref_match and (not tx_time or tx_time >= offchain_start)

        if not exact_ref_match and not offchain_match:
            continue

        if not receiver_matches_our_binance_id(tx):
            return False, "Transaction found, but receiver Binance ID does not match."

        amount = get_transaction_amount_usdt(tx)

        if amount is None:
            return False, "Transaction found, but USDT amount could not be read."

        # Receiver side income should normally be positive.
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
    User Binance ID / Pay ID par payment bhejta hai.
    Phir user jo Binance Order ID / off-chain transaction reference bhejta hai,
    bot Binance Pay trade history se auto verify karta hai.
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
        f"{tg(EMOJIS['binance'], '💳')} <b>Binance Payment</b>\n\n"
        f"Binance ID (tap to copy):\n"
        f"<code>{safe(binance_id)}</code>\n\n"
        f"Amount to transfer: <b>${safe(total_amount)}</b>\n\n"
        f"Please send the order ID or off-chain transaction reference after payment for verification.\n\n"
        f"━━━━━━━━━━━━━━━━━━"
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
        f"👛 <b>Wallet Payment</b>\n\n"
        f"Your Balance: <b>{safe(current_balance)} USDT</b>\n"
        f"Total Amount: <b>{safe(total_amount)} USDT</b>\n\n"
        f"━━━━━━━━━━━━━━━━━━\n\n"
        f"Balance Status: <b>{status}</b>"
    )
