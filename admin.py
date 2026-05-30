import database
import json
import config
import re


def is_admin(user_id):
    return str(user_id) == str(config.ADMIN_ID)


def _extract_product_stock_sections(text):
    pattern = r'(\d+)\s*\[(.*?)\]'
    matches = re.findall(pattern, text, flags=re.DOTALL)

    if not matches:
        raise ValueError("Invalid stock format. Use: product_id[{field:value},{field:value}]")

    sections = []
    for product_id, block in matches:
        item_blocks = re.findall(r'\{(.*?)\}', block, flags=re.DOTALL)
        if not item_blocks:
            raise ValueError(f"No stock items found for product ID {product_id}.")
        sections.append((int(product_id), item_blocks))

    return sections


def _parse_item_block(block):
    item = {}
    parts = [p.strip() for p in block.split(",") if p.strip()]

    for part in parts:
        if ":" not in part:
            raise ValueError(f"Invalid item field: {part}")

        key, value = part.split(":", 1)
        key = key.strip()
        value = value.strip()

        if not key or not value:
            raise ValueError(f"Invalid item field: {part}")

        item[key] = value

    if not item:
        raise ValueError("Empty item data.")

    return item


def parse_stock_bulk_format(text):
    sections = _extract_product_stock_sections(text)

    parsed = []
    for product_id, item_blocks in sections:
        items = [_parse_item_block(block) for block in item_blocks]
        parsed.append((product_id, items))

    return parsed


def parse_product_block(block):
    fields = [x.strip() for x in block.split(" | ")]

    if len(fields) != 7:
        fields = [x.strip() for x in block.split("|")]

    if len(fields) != 7:
        raise ValueError(
            "Product format must have 7 fields: "
            "Name | Duration | Price | Rating | Description | features | Note"
        )

    features = [f.strip() for f in fields[5].split(",") if f.strip()]

    return {
        "name": fields[0],
        "duration": fields[1],
        "price": float(fields[2]),
        "stock": 0,
        "rating": float(fields[3]),
        "description": fields[4],
        "features": features,
        "note": fields[6],
    }


def parse_bulk_products_format(text):
    blocks = re.findall(r'\[(.*?)\]', text, flags=re.DOTALL)

    if not blocks:
        return [parse_product_block(text)]

    return [parse_product_block(block) for block in blocks]


def add_product_admin(name, duration, price, rating, description, features_str, note):
    try:
        try:
            features = json.loads(features_str) if features_str else []
        except Exception:
            features = [f.strip() for f in features_str.split(",") if f.strip()]

        database.add_product(name, duration, price, 0, rating, description, features, note)
        return f"✅ Product *{name}* added successfully with stock `0`."
    except Exception as e:
        return f"❌ Error adding product: {e}"


def add_bulk_products_admin(products_data):
    try:
        added_count = 0

        for p in products_data:
            database.add_product(
                p["name"],
                p["duration"],
                p["price"],
                0,
                p["rating"],
                p["description"],
                p["features"],
                p["note"]
            )
            added_count += 1

        return f"✅ Successfully added *{added_count}* products with stock `0`."

    except Exception as e:
        return f"❌ Error adding bulk products: {e}"


def add_stock_bulk_admin(stock_sections):
    try:
        total_added = 0
        report = "📦 *Stock Add Report:*\n\n"

        for product_id, items_data in stock_sections:
            product = database.get_product(product_id)
            if not product:
                report += f"❌ Product ID `{product_id}` not found.\n"
                continue

            added_count = 0

            for item in items_data:
                if item:
                    database.add_unsold_item(product_id, item)
                    added_count += 1

            if added_count > 0:
                database.update_product_stock(product_id, added_count)

            total_added += added_count
            report += f"✅ Product ID `{product_id}`: Added `{added_count}` items.\n"

        report += f"\n━━━━━━━━━━━━━━━━━━\nTotal Added: *{total_added}*"
        return report

    except Exception as e:
        return f"❌ Error adding stock: {e}"


def get_all_products_admin():
    products = database.get_all_products()

    if not products:
        return "No products in the database."

    message = "📦 *All Products:*\n\n"

    for p in products:
        stock_status = "✅ In Stock" if p[4] > 0 else "❌ OUT OF STOCK"

        message += (
            f"🆔 ID: `{p[0]}`\n"
            f"📦 Name: *{p[1]}*\n"
            f"📅 Duration: {p[2]}\n"
            f"💰 Price: {p[3]} USDT\n"
            f"📦 Stock: {p[4]} — {stock_status}\n"
            f"⭐ Rating: {p[5]}/5\n"
            f"━━━━━━━━━━━━━━━━━━\n"
        )

    return message


def edit_product_price(product_id, new_price):
    try:
        product = database.get_product(product_id)

        if not product:
            return "❌ Product not found."

        database.set_product_price(product_id, new_price)
        return f"✅ Price for product ID {product_id} updated to {new_price} USDT."

    except Exception as e:
        return f"❌ Error updating price: {e}"


def edit_product_stock(product_id, new_stock):
    try:
        product = database.get_product(product_id)

        if not product:
            return "❌ Product not found."

        database.set_product_stock(product_id, new_stock)
        return f"✅ Stock for product ID {product_id} updated to {new_stock}."

    except Exception as e:
        return f"❌ Error updating stock: {e}"


def delete_product_admin(product_id):
    try:
        product = database.get_product(product_id)

        if not product:
            return "❌ Product not found."

        database.delete_product(product_id)
        return f"✅ Product *{product[1]}* deleted successfully."

    except Exception as e:
        return f"❌ Error deleting product: {e}"


def get_all_orders_admin():
    orders = database.get_all_orders(limit=20)

    if not orders:
        return "No orders found."

    message = "📝 *Recent Orders (last 20):*\n\n"

    for o in orders:
        product = database.get_product(o[2])
        product_name = product[1] if product else "Unknown"

        message += (
            f"🧾 Order ID: `{o[0]}`\n"
            f"👤 User ID: `{o[1]}`\n"
            f"📦 Product: {product_name}\n"
            f"🔢 Qty: {o[3]}\n"
            f"💰 Amount: {o[4]} USDT\n"
            f"💳 Method: {o[5]}\n"
            f"✅ Status: {o[6]}\n"
            f"📅 Date: {o[7]}\n"
            f"━━━━━━━━━━━━━━━━━━\n"
        )

    return message


def add_balance_admin(user_id, amount):
    try:
        user = database.get_user(user_id)

        if not user:
            return "❌ User not found."

        database.update_user_wallet(user_id, amount)
        database.add_transaction(user_id, "Deposit (Admin)", amount)

        return f"✅ Added {amount} USDT to user `{user_id}` wallet."

    except Exception as e:
        return f"❌ Error adding balance: {e}"


def get_withdrawal_requests_admin():
    withdrawals = database.get_pending_withdrawals()

    if not withdrawals:
        return "No pending withdrawal requests."

    message = "💸 *Pending Withdrawals:*\n\n"

    for req in withdrawals:
        message += (
            f"🆔 Withdrawal ID: `{req[0]}`\n"
            f"👤 User ID: `{req[1]}`\n"
            f"💰 Amount: {req[2]} USDT\n"
            f"📍 Address: `{req[3]}`\n"
            f"⏳ Status: {req[4]}\n"
            f"📅 Date: {req[5]}\n"
            f"━━━━━━━━━━━━━━━━━━\n"
        )

    return message


def approve_withdrawal_admin(withdrawal_id):
    try:
        withdrawal = database.get_withdrawal(withdrawal_id)

        if not withdrawal:
            return "❌ Withdrawal request not found."

        if withdrawal[4] != "Pending":
            return f"⚠️ Withdrawal already marked as {withdrawal[4]}."

        database.update_withdrawal_status(withdrawal_id, "Approved")

        return f"✅ Withdrawal request `{withdrawal_id}` approved. Send funds manually."

    except Exception as e:
        return f"❌ Error approving withdrawal: {e}"


def get_stats_admin():
    conn = database.sqlite3.connect(database.DATABASE_NAME)
    cursor = conn.cursor()

    total_users = cursor.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    total_products = cursor.execute("SELECT COUNT(*) FROM products").fetchone()[0]
    total_orders = cursor.execute("SELECT COUNT(*) FROM orders").fetchone()[0]

    total_revenue = cursor.execute(
        "SELECT SUM(total_amount) FROM orders WHERE status = 'Confirmed'"
    ).fetchone()[0] or 0

    total_wallet = cursor.execute(
        "SELECT SUM(wallet_balance) FROM users"
    ).fetchone()[0] or 0

    total_pending_withdrawals = cursor.execute(
        "SELECT COUNT(*) FROM withdrawals WHERE status = 'Pending'"
    ).fetchone()[0]

    total_stock = cursor.execute(
        "SELECT SUM(stock) FROM products"
    ).fetchone()[0] or 0

    total_unsold_items = cursor.execute(
        "SELECT COUNT(*) FROM unsold_items WHERE is_sold = 0"
    ).fetchone()[0]

    conn.close()

    return (
        f"📊 *Bot Statistics:*\n\n"
        f"👥 Total Users: {total_users}\n"
        f"📦 Total Products: {total_products}\n"
        f"📦 Product Stock Count: {total_stock}\n"
        f"📋 Unsold Items Count: {total_unsold_items}\n"
        f"🛒 Total Orders: {total_orders}\n"
        f"💰 Total Revenue: {round(total_revenue, 2)} USDT\n"
        f"👛 Users Wallet Balance: {round(total_wallet, 2)} USDT\n"
        f"💸 Pending Withdrawals: {total_pending_withdrawals}\n"
    )
