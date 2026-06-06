import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

TOKEN = os.getenv("TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))

# PostgreSQL Configuration
DATABASE_URL = os.getenv("DATABASE_URL")

# Fallback for individual components if DATABASE_URL is not provided
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_NAME = os.getenv("DB_NAME", "postgres")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASS = os.getenv("DB_PASS", "password")
DB_PORT = os.getenv("DB_PORT", "5432")

BINANCE_API_KEY = os.getenv("BINANCE_API_KEY", "")
BINANCE_API_SECRET = os.getenv("BINANCE_API_SECRET", "")
BINANCE_WALLET_ADDRESS = os.getenv("BINANCE_WALLET_ADDRESS", "")
BINANCE_NETWORK = os.getenv("BINANCE_NETWORK", "BEP-20")

BINANCE_PAY_ID = os.getenv("BINANCE_PAY_ID", BINANCE_WALLET_ADDRESS)
BINANCE_API_BASE_URL = os.getenv("BINANCE_API_BASE_URL", "https://api.binance.com")
BINANCE_PAYMENT_CURRENCY = os.getenv("BINANCE_PAYMENT_CURRENCY", "USDT")
BINANCE_PAYMENT_LOOKBACK_DAYS = int(os.getenv("BINANCE_PAYMENT_LOOKBACK_DAYS", "30"))

FREEBIES_CHANNEL_ID = os.getenv("FREEBIES_CHANNEL_ID", "")
FREEBIES_CHANNEL_LINK = os.getenv("FREEBIES_CHANNEL_LINK", "")
FREEBIES_ENABLED = os.getenv("FREEBIES_ENABLED", "true").lower() in ("1", "true", "yes", "enable", "enabled")
