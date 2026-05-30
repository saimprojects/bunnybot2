import os
import logging

# Setup logging
logging.basicConfig(level=logging.INFO)

TOKEN = os.getenv("TOKEN")

# ADMIN_IDS with better error handling
admin_ids_raw = os.getenv("ADMIN_IDS", "")
ADMIN_IDS = []

if admin_ids_raw:
    try:
        ADMIN_IDS = [
            int(x.strip())
            for x in admin_ids_raw.split(",")
            if x.strip()
        ]
        print(f"✅ ADMIN_IDS loaded successfully: {ADMIN_IDS}")
    except ValueError as e:
        print(f"❌ Error parsing ADMIN_IDS: {e}")
        print(f"   Raw value: '{admin_ids_raw}'")
        print("   Make sure ADMIN_IDS contains only numbers separated by commas (e.g., '123456789,987654321')")
else:
    print("⚠️  WARNING: ADMIN_IDS environment variable is not set or empty")

BINANCE_API_KEY = os.getenv("BINANCE_API_KEY", "")
BINANCE_API_SECRET = os.getenv("BINANCE_API_SECRET", "")
BINANCE_WALLET_ADDRESS = os.getenv("BINANCE_WALLET_ADDRESS", "")
BINANCE_NETWORK = os.getenv("BINANCE_NETWORK", "BEP-20")

# Optional: Function to check admin status
def is_admin(user_id: int) -> bool:
    """Check if user is an admin"""
    if not ADMIN_IDS:
        print("⚠️  No admins configured!")
        return False
    return user_id in ADMIN_IDS

# For debugging
if __name__ == "__main__":
    print("\n--- Configuration Summary ---")
    print(f"TOKEN: {'✅ Set' if TOKEN else '❌ Missing'}")
    print(f"ADMIN_IDS: {ADMIN_IDS if ADMIN_IDS else '❌ Empty/Invalid'}")
    print(f"BINANCE_API_KEY: {'✅ Set' if BINANCE_API_KEY else '❌ Missing'}")
    print(f"BINANCE_API_SECRET: {'✅ Set' if BINANCE_API_SECRET else '❌ Missing'}")
    print(f"BINANCE_WALLET_ADDRESS: {'✅ Set' if BINANCE_WALLET_ADDRESS else '❌ Missing'}")
    print(f"BINANCE_NETWORK: {BINANCE_NETWORK}")