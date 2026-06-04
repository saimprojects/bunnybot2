"""
Bot configuration

This module reads configuration values from environment variables.  To
run the bot you must at least define ``TOKEN``.  Optional values
include ``ADMIN_ID`` for the admin chat, Binance API credentials for
payment integration and wallet address/network information.
"""

import os

# Telegram bot token
TOKEN: str = os.getenv("TOKEN", "").strip()

# Chat ID of the bot administrator.  This should be a numeric ID and
# not a username.  If omitted or invalid the admin functions will be
# disabled.
ADMIN_ID: int = int(os.getenv("ADMIN_ID", "0").strip() or 0)

# Binance API credentials and settings
BINANCE_API_KEY: str = os.getenv("BINANCE_API_KEY", "").strip()
BINANCE_API_SECRET: str = os.getenv("BINANCE_API_SECRET", "").strip()
BINANCE_WALLET_ADDRESS: str = os.getenv("BINANCE_WALLET_ADDRESS", "").strip()
BINANCE_NETWORK: str = os.getenv("BINANCE_NETWORK", "BEP-20").strip()

BINANCE_PAY_ID: str = os.getenv("BINANCE_PAY_ID", BINANCE_WALLET_ADDRESS).strip()

# Optional: specify a custom path to the SQLite database file.  By
# default ``shop.db`` in the working directory will be used.
SHOP_DB_PATH: str = os.getenv("SHOP_DB_PATH", "shop.db").strip()
