import config
import database
import time
import json
import hmac
import hashlib
import random
import string
import urllib.request
import urllib.error
from html import escape as html_escape


EMOJIS = {
    "cancel": "5210952531676504517",
    "confirm": "5206607081334906820",
    "binance": "6222208096257712941",
}


def tg(emoji_id, fallback):
    return f'<tg-emoji emoji-id="{emoji_id}">{fallback}</tg-emoji>'


def safe(value):
    return html_escape(str(value)) if value is not None else ""


def random_nonce(length=32):
    chars = string.ascii_letters + string.digits
    return "".join(random.choice(chars) for _ in range(length))


def get_binance_account_id():
    return getattr(config, "BINANCE_PAY_ID", "") or getattr(config, "BINANCE_WALLET_ADDRESS", "")


def build_binance_pay_signature(timestamp, nonce, body):
    payload = f"{timestamp}\n{nonce}\n{body}\n"
    return hmac.new(
        config.BINANCE_API_SECRET.encode("utf-8"),
        payload.encode("utf-8"),
        hashlib.sha512
    ).hexdigest().upper()


def query_binance_pay_order(binance_order_id):
    if not config.BINANCE_API_KEY or not config.BINANCE_API_SECRET:
        return False, "Binance API key/secret missing."

    url = "https://bpay.binanceapi.com/binancepay/openapi/order/query"
    body_dict = {"merchantTradeNo": str(binance_order_id)}
    body = json.dumps(body_dict, separators=(",", ":"))

    timestamp = str(int(time.time() * 1000))
    nonce = random_nonce()
    signature = build_binance_pay_signature(timestamp, nonce, body)

    headers = {
        "Content-Type": "application/json",
        "BinancePay-Timestamp": timestamp,
        "BinancePay-Nonce": nonce,
        "BinancePay-Certificate-SN": config.BINANCE_API_KEY,
        "BinancePay-Signature": signature,
    }

    request = urllib.request.Request(url, data=body.encode("utf-8"), headers=headers, method="POST")

    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            raw = response.read().decode("utf-8")
            return True, json.loads(raw)
    except urllib.error.HTTPError as e:
        try:
            error_body = e.read().decode("utf-8")
        except Exception:
            error_body = str(e)
        return False, f"Binance HTTP error: {error_body}"
    except Exception as e:
        return False, f"Binance API error: {e}"


def verify_binance_order_id(binance_order_id, expected_amount):
    ok, result = query_binance_pay_order(binance_order_id)

    if not ok:
        return False, str(result)

    data = result.get("data") or {}
    status = str(data.get("status") or data.get("orderStatus") or data.get("bizStatus") or "").upper()

    paid_statuses = {"PAID", "SUCCESS", "COMPLETED", "PAY_SUCCESS"}

    if status and status not in paid_statuses:
        return False, f"Payment status is `{status}`."

    amount_raw = data.get("orderAmount") or data.get("totalFee") or data.get("amount") or data.get("transactAmount") or 0

    try:
        paid_amount = float(amount_raw)
        expected = float(expected_amount)
        if paid_amount + 1e-9 < expected:
            return False, f"Paid amount {paid_amount} is less than required {expected}."
    except Exception:
        pass

    return True, "Payment verified successfully."


def process_binance_payment(user_id, order_id, product_id, quantity, total_amount, binance_order_id=None):
    if not binance_order_id:
        return False, "Binance Order ID missing."

    print(f"[Binance] Verifying Binance Order ID {binance_order_id}, user {user_id}, amount {total_amount} USDT")

    success, msg = verify_binance_order_id(binance_order_id, total_amount)

    if success:
        database.add_transaction(user_id, "Binance Purchase", -float(total_amount))
        return True, f"{tg(EMOJIS['confirm'], '✅')} Payment verified successfully."

    return False, (
        f"{tg(EMOJIS['cancel'], '❌')} <b>Payment not verified.</b>\n\n"
        f"Reason: {safe(msg)}\n\n"
        f"Please check your Binance Order ID or contact support."
    )


def process_wallet_payment(user_id, order_id, product_id, quantity, total_amount):
    user = database.get_user(user_id)
    if not user:
        return False, "User not found."

    current_balance = float(user[3])

    if current_balance >= float(total_amount):
        database.update_user_wallet(user_id, -float(total_amount))
        database.add_transaction(user_id, "Purchase", -float(total_amount))
        return True, "Payment successful using wallet."

    required = round(total_amount - current_balance, 4)
    return False, (
        f"{tg(EMOJIS['cancel'], '❌')} <b>Insufficient Balance</b>\n\n"
        f"Your Balance: {safe(current_balance)} USDT\n"
        f"Required: {safe(total_amount)} USDT\n"
        f"Short by: {safe(required)} USDT"
    )


def get_binance_payment_details(total_amount):
    binance_id = get_binance_account_id()

    return (
        f"{tg(EMOJIS['binance'], '💳')} <b>Binance Payment</b>\n\n"
        f"Send exactly: <b>{safe(total_amount)} USDT</b>\n\n"
        f"{tg(EMOJIS['binance'], '💳')} <b>Binance ID:</b>\n"
        f"<code>{safe(binance_id)}</code>\n\n"
        f"After sending payment, click the button below.\n"
        f"Then send your <b>Binance Order ID / Transaction ID</b> for verification.\n\n"
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

