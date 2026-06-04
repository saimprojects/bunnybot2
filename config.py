import os
from dotenv import load_dotenv

load_dotenv()

TOKEN: str = os.getenv("TOKEN", "").strip()
ADMIN_ID: int = int(os.getenv("ADMIN_ID", "0").strip() or 0)

BINANCE_API_KEY: str = os.getenv("BINANCE_API_KEY", "").strip()
BINANCE_API_SECRET: str = os.getenv("BINANCE_API_SECRET", "").strip()
BINANCE_WALLET_ADDRESS: str = os.getenv("BINANCE_WALLET_ADDRESS", "").strip()
BINANCE_NETWORK: str = os.getenv("BINANCE_NETWORK", "BEP-20").strip()

BINANCE_PAY_ID: str = os.getenv("BINANCE_PAY_ID", BINANCE_WALLET_ADDRESS).strip()

SHOP_DB_PATH: str = os.getenv("SHOP_DB_PATH", "shop.db").strip()