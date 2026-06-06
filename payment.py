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
import urllib.parse
from html import escape as html_escape
import utils


def tg(emoji_id, fallback):
    return utils.tg(emoji_id, fallback)


def ce(name):
    return utils.ce(name)


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


def build_binance_spot_signature(query_string):
    return hmac.new(
        config.BINANCE_API_SECRET.encode("utf-8"),
        query_string.encode("utf-8"),
        hashlib.sha256
    ).hexdigest()


def signed_binance_get(path, params=None):
    if not config.BINANCE_API_KEY or not config.BINANCE_API_SECRET:
        return False, "Binance API key/secret missing."

    params = dict(params or {})
    params["timestamp"] = int(time.time() * 1000)
    query_string = urllib.parse.urlencode(params)
    signature = build_binance_spot_signature(query_string)
    base_url = getattr(config, "BINANCE_API_BASE_URL", "https://api.binance.com").rstrip("/")
    url = f"{base_url}{path}?{query_string}&signature={signature}"
    headers = {"X-MBX-APIKEY": config.BINANCE_API_KEY}
    request = urllib.request.Request(url, headers=headers, method="GET")

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


def query_binance_pay_transactions():
    lookback_days = int(getattr(config, "BINANCE_PAYMENT_LOOKBACK_DAYS", 30) or 30)
    end_time = int(time.time() * 1000)
    start_time = end_time - (lookback_days * 24 * 60 * 60 * 1000)
    params = {
        "startTime": start_time,
        "endTime": end_time,
        "limit": 100,
    }
    return signed_binance_get("/sapi/v1/pay/transactions", params)


def iter_transaction_rows(payload):
    if isinstance(payload, list):
        return payload

    if not isinstance(payload, dict):
        return []

    data = payload.get("data")
    if isinstance(data, list):
        return data

    if isinstance(data, dict):
        for key in ("rows", "list", "data", "transactions"):
            value = data.get(key)
            if isinstance(value, list):
                return value

    for key in ("rows", "list", "transactions"):
        value = payload.get(key)
        if isinstance(value, list):
            return value

    return []


def transaction_references(row):
    keys = (
        "transactionId",
        "transactionID",
        "transaction_id",
        "txId",
        "txID",
        "orderId",
        "orderID",
        "merchantTradeNo",
        "prepayId",
        "referenceId",
        "reference",
        "refId",
    )
    refs = []
    for key in keys:
        value = row.get(key)
        if value is not None and str(value).strip():
            refs.append(str(value).strip())
    return refs


def transaction_amount_and_currency(row, expected_currency):
    expected_currency = str(expected_currency or "").upper()
    funds_detail = row.get("fundsDetail") or row.get("funds") or []

    if isinstance(funds_detail, list):
        for fund in funds_detail:
            if not isinstance(fund, dict):
                continue
            currency = str(fund.get("currency") or fund.get("asset") or "").upper()
            if expected_currency and currency and currency != expected_currency:
                continue
            amount = fund.get("amount") or fund.get("qty") or fund.get("quantity")
            if amount is not None:
                return amount, currency or expected_currency

    amount = (
        row.get("amount")
        or row.get("orderAmount")
        or row.get("totalFee")
        or row.get("transactAmount")
        or row.get("quantity")
    )
    currency = (
        row.get("currency")
        or row.get("coin")
        or row.get("asset")
        or row.get("orderCurrency")
        or expected_currency
    )
    return amount, str(currency or expected_currency).upper()


def verify_binance_pay_history_reference(payment_reference, expected_amount):
    ok, result = query_binance_pay_transactions()

    if not ok:
        return False, str(result)

    reference = str(payment_reference).strip()
    expected_currency = getattr(config, "BINANCE_PAYMENT_CURRENCY", "USDT")
    rows = iter_transaction_rows(result)

    if isinstance(result, dict) and result.get("success") is False:
        return False, str(result.get("message") or result.get("msg") or result)

    for row in rows:
        if not isinstance(row, dict):
            continue
        if reference not in transaction_references(row):
            continue

        status = str(row.get("status") or row.get("orderStatus") or row.get("bizStatus") or "").upper()
        if status and status not in {"SUCCESS", "COMPLETED", "PAID", "PAY_SUCCESS"}:
            return False, f"Payment status is `{status}`."

        amount_raw, currency = transaction_amount_and_currency(row, expected_currency)

        if expected_currency and currency and currency.upper() != expected_currency.upper():
            return False, f"Currency mismatch. Expected {expected_currency}, got {currency}."

        try:
            paid_amount = float(amount_raw)
            expected = float(expected_amount)
            if paid_amount + 1e-9 < expected:
                return False, f"Paid amount {paid_amount} is less than required {expected}."
        except Exception:
            return False, "Payment amount could not be verified."

        return True, "Payment verified successfully."

    return False, "Payment reference not found in Binance Pay transaction history."


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


def verify_binance_reference(payment_reference, expected_amount):
    success, msg = verify_binance_pay_history_reference(payment_reference, expected_amount)
    if success:
        return True, msg

    fallback_success, fallback_msg = verify_binance_order_id(payment_reference, expected_amount)
    if fallback_success:
        return True, fallback_msg

    return False, f"{msg} Fallback check: {fallback_msg}"


def process_binance_payment(user_id, order_id, product_id, quantity, total_amount, binance_order_id=None):
    if not binance_order_id:
        return False, "Binance payment reference missing."

    payment_reference = str(binance_order_id).strip()

    if database.is_payment_reference_used(payment_reference):
        return False, f"{ce('cancel')} <b>This payment reference is already used.</b>"

    print(f"[Binance] Verifying Binance payment reference {payment_reference}, user {user_id}, amount {total_amount} USDT")

    success, msg = verify_binance_reference(payment_reference, total_amount)

    if success:
        recorded = database.record_verified_payment(
            payment_reference,
            user_id,
            float(total_amount),
            getattr(config, "BINANCE_PAYMENT_CURRENCY", "USDT"),
            "Product Purchase",
            order_id
        )
        if not recorded:
            return False, f"{ce('cancel')} <b>This payment reference is already used.</b>"
        database.add_transaction(user_id, "Binance Purchase", -float(total_amount))
        return True, f"{ce('confirm')} Payment verified successfully."

    return False, (
        f"{ce('cancel')} <b>Payment not verified.</b>\n\n"
        f"Reason: {safe(msg)}\n\n"
        f"Please check your Transaction ID / Reference ID or contact support."
    )


def process_wallet_deposit(user_id, amount, payment_reference):
    if not payment_reference:
        return False, "Binance payment reference missing."

    payment_reference = str(payment_reference).strip()

    try:
        amount = float(amount)
    except Exception:
        return False, "Deposit amount is invalid."

    if amount <= 0:
        return False, "Deposit amount must be greater than 0."

    if database.is_payment_reference_used(payment_reference):
        return False, f"{ce('cancel')} <b>This payment reference is already used.</b>"

    success, msg = verify_binance_reference(payment_reference, amount)

    if not success:
        return False, (
            f"{ce('cancel')} <b>Payment not verified.</b>\n\n"
            f"Reason: {safe(msg)}\n\n"
            f"Please check your Transaction ID / Reference ID or contact support."
        )

    recorded = database.record_verified_payment(
        payment_reference,
        user_id,
        amount,
        getattr(config, "BINANCE_PAYMENT_CURRENCY", "USDT"),
        "Wallet Deposit",
        None
    )
    if not recorded:
        return False, f"{ce('cancel')} <b>This payment reference is already used.</b>"

    database.update_user_wallet(user_id, amount)
    database.add_transaction(user_id, "Wallet Deposit (Binance)", amount)
    return True, f"{ce('confirm')} Wallet deposit verified. Balance updated."


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
        f"{ce('cancel')} <b>Insufficient Balance</b>\n\n"
        f"Your Balance: {safe(current_balance)} USDT\n"
        f"Required: {safe(total_amount)} USDT\n"
        f"Short by: {safe(required)} USDT"
    )


def get_binance_payment_details(total_amount):
    binance_id = get_binance_account_id()

    return (
        f"{ce('diamond')} <b>Binance Payment</b>\n\n"
        f"Send exactly: <b>{safe(total_amount)} USDT</b>\n\n"
        f"{ce('diamond')} <b>Binance ID:</b>\n"
        f"<code>{safe(binance_id)}</code>\n\n"
        f"After sending payment, click the button below.\n"
        f"Then send your <b>Transaction ID / Reference ID</b> for verification.\n\n"
        f"{utils.DIVIDER}"
    )


def get_wallet_payment_summary(user_id, total_amount):
    user = database.get_user(user_id)
    if not user:
        return "Error: User not found."

    current_balance = user[3]
    status = (
        f"{ce('confirm')} Sufficient"
        if current_balance >= total_amount
        else f"{ce('cancel')} Insufficient"
    )

    return (
        f"{ce('wallet_purse')} <b>Wallet Payment</b>\n\n"
        f"Your Balance: <b>{safe(current_balance)} USDT</b>\n"
        f"Total Amount: <b>{safe(total_amount)} USDT</b>\n\n"
        f"{utils.DIVIDER}\n\n"
        f"Balance Status: <b>{status}</b>"
    )
