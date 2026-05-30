import os

TOKEN = os.getenv("TOKEN")

ADMIN_IDS = [
    int(x.strip())
    for x in os.getenv("ADMIN_IDS", "").split(",")
    if x.strip()
]

BINANCE_API_KEY = os.getenv("BINANCE_API_KEY", "")
BINANCE_API_SECRET = os.getenv("BINANCE_API_SECRET", "")
BINANCE_WALLET_ADDRESS = os.getenv("BINANCE_WALLET_ADDRESS", "")
BINANCE_NETWORK = os.getenv("BINANCE_NETWORK", "BEP-20")