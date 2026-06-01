import os

TOKEN = os.getenv("TOKEN", "").strip()
ADMIN_IDS = [
    int(admin_id.strip())
    for admin_id in os.getenv("ADMIN_IDS", "").split(",")
    if admin_id.strip().isdigit()
]

BINANCE_API_KEY = os.getenv("BINANCE_API_KEY", "").strip()
BINANCE_API_SECRET = os.getenv("BINANCE_API_SECRET", "").strip()
BINANCE_WALLET_ADDRESS = os.getenv("BINANCE_WALLET_ADDRESS", "").strip()
BINANCE_NETWORK = os.getenv("BINANCE_NETWORK", "BEP-20").strip()

BINANCE_PAY_ID = os.getenv("BINANCE_PAY_ID", BINANCE_WALLET_ADDRESS).strip()