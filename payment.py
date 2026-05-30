import database
import config
import time
import random

def process_binance_payment(user_id, order_id, product_id, quantity, total_amount):
    """
    Real project mein yahan Binance API se payment verify hogi.
    Abhi simulation hai — 80% success rate.
    """
    print(f"[Binance] Checking payment for user {user_id}, amount {total_amount} USDT")
    time.sleep(2)  # Network delay simulate

    if random.random() > 0.2:
        return True, "Payment confirmed successfully."
    else:
        return False, "❌ Payment not found. Please try again or contact support."

def process_wallet_payment(user_id, order_id, product_id, quantity, total_amount):
    user = database.get_user(user_id)
    if not user:
        return False, "User not found."

    current_balance = user[3]

    if current_balance >= total_amount:
        database.update_user_wallet(user_id, -total_amount)
        database.add_transaction(user_id, "Purchase", -total_amount)
        return True, "Payment successful using wallet."
    else:
        required = round(total_amount - current_balance, 4)
        return False, (
            f"❌ *Insufficient Balance*\n\n"
            f"Your Balance: {current_balance} USDT\n"
            f"Required: {total_amount} USDT\n"
            f"Short by: {required} USDT"
        )

def get_binance_payment_details(total_amount):
    return (
        f"💳 *Binance Payment*\n\n"
        f"Send exactly: *{total_amount} USDT*\n\n"
        f"📍 *Address:*\n`{config.BINANCE_WALLET_ADDRESS}`\n\n"
        f"🔁 *Network:* {config.BINANCE_NETWORK} \\(USDT\\)\n\n"
        f"⏳ Payment auto-detect hoga ~30 seconds mein\n\n"
        f"━━━━━━━━━━━━━━━━━━"
    )

def get_wallet_payment_summary(user_id, total_amount):
    user = database.get_user(user_id)
    if not user:
        return "Error: User not found."

    current_balance = user[3]
    status = "✅ Sufficient" if current_balance >= total_amount else "❌ Insufficient"

    return (
        f"👛 *Wallet Payment*\n\n"
        f"Your Balance: *{current_balance} USDT*\n"
        f"Total Amount: *{total_amount} USDT*\n\n"
        f"━━━━━━━━━━━━━━━━━━\n\n"
        f"Balance Status: *{status}*"
    )