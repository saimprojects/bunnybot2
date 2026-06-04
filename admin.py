"""
Administrative helpers for the Telegram shop bot.

This module exposes higher‑level operations for administrators such as
adding products and stock items, editing product metadata, marking
products as freebies, adjusting user balances, and generating
summary statistics.  All functions wrap lower‑level database calls
and return human readable messages.

Only admins (as determined by ``config.ADMIN_ID``) should be allowed
to trigger these functions from the bot.
"""

import json
import re
import config
import database


def is_admin(user_id: int) -> bool:
    """Return True if ``user_id`` matches the configured ADMIN_ID."""
    try:
        return int(user_id) == int(config.ADMIN_ID)
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Parsing helpers for bulk product and stock formats
# ---------------------------------------------------------------------------

def _extract_product_stock_sections(text: str):
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


def _parse_item_block(block: str) -> dict:
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


def parse_stock_bulk_format(text: str):
    sections = _extract_product_stock_sections(text)
    parsed = []
    for product_id, item_blocks in sections:
        items = [_parse_item_block(block) for block in item_blocks]
        parsed.append((product_id, items))
    return parsed


def parse_product_block(block: str) -> dict:
    fields = [x.strip() for x in block.split(" | ")]
    if len(fields) != 6:
        fields = [x.strip() for x in block.split("|")]
    if len(fields) != 6:
        raise ValueError(
            "Product format must have 6 fields: Name | Duration | Price | Description | Note | Sticker Emoji ID"
        )
    return {
        "name": fields[0],
        "duration": fields[1],
        "price": float(fields[2]),
        "stock": 0,
        "rating": 0,
        "description": fields[3],
        "features": [],
        "note": fields[4],
        "emoji_id": fields[5],
    }


def parse_bulk_products_format(text: str):
    blocks = re.findall(r'\[(.*?)\]', text, flags=re.DOTALL)
    if not blocks:
        return [parse_product_block(text)]
    return [parse_product_block(block) for block in blocks]


def add_product_admin(name: str, duration: str, price: float, description: str, note: str, emoji_id: str) -> str:
    try:
        database.add_product(name, duration, price, 0, 0, description, [], note, emoji_id)
        return f"✅ Product *{name}* added successfully with stock `0` and sticker ID `{emoji_id}`."
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
                p["note"],
                p.get("emoji_id", "")
            )
            added_count += 1
        return f"✅ Successfully added *{added_count}* products with stock `0`."
    except Exception as e:
        return f"❌ Error adding bulk products: {e}"


def add_stock_bulk_admin(stock_sections):
    """Add stock items in bulk.

    Returns a tuple ``(message, products_to_broadcast)`` where
    ``message`` is a human readable summary and ``products_to_broadcast``
    is a list of dicts containing product data which should trigger a
    stock update broadcast.
    """
    try:
        report_lines = ["📦 *Stock Add Report:*", ""]
        products_to_broadcast = []
        for product_id, items_data in stock_sections:
            product = database.get_product(product_id)
            if not product:
                report_lines.append(f"❌ Product ID `{product_id}` not found.")
                continue
            added_count = 0
            for item in items_data:
                if item:
                    database.add_unsold_item(product_id, item)
                    added_count += 1
            if added_count > 0:
                current_stock = product[4]
                new_total_stock = current_stock + added_count
                database.set_product_stock(product_id, new_total_stock)
                updated_product = database.get_product(product_id)
                new_stock = updated_product[4] if updated_product else new_total_stock
                products_to_broadcast.append({
                    'product_id': product_id,
                    'added_count': added_count,
                    'product_name': product[1],
                    'new_stock': new_stock,
                })
                report_lines.append(f"✅ Added {added_count} items to *{product[1]}* (new stock: {new_stock}).")
            else:
                report_lines.append(f"⚠️ No valid items for product `{product_id}`.")
        return "\n".join(report_lines), products_to_broadcast
    except Exception as e:
        return f"❌ Error adding stock: {e}", []


def set_freebie(product_id: int, channel: str) -> str:
    """Mark a product as free for members of the specified channel."""
    try:
        database.set_product_free(product_id, channel)
        channel_desc = f"@{channel}" if channel else "(no channel)"
        return f"✅ Product `{product_id}` marked as free for {channel_desc}."
    except Exception as e:
        return f"❌ Error setting freebie: {e}"


def unset_freebie(product_id: int) -> str:
    try:
        database.unset_product_free(product_id)
        return f"✅ Product `{product_id}` is no longer a freebie."
    except Exception as e:
        return f"❌ Error unsetting freebie: {e}"


def edit_product_details(product_id: int, field_name: str, new_value: str) -> str:
    try:
        database.update_product_field(product_id, field_name, new_value)
        return f"✅ Updated {field_name} for product `{product_id}`."
    except Exception as e:
        return f"❌ Error editing product: {e}"


def edit_unsold_item_credentials(item_id: int, updates: dict) -> str:
    try:
        ok = database.update_unsold_item_data(item_id, updates)
        if not ok:
            return f"❌ Item ID `{item_id}` not found."
        return f"✅ Updated credentials for item `{item_id}`."
    except Exception as e:
        return f"❌ Error editing credentials: {e}"


def add_user_balance(user_id: int, amount: float) -> str:
    try:
        database.update_user_wallet(user_id, amount)
        database.add_transaction(user_id, "Admin Add Balance", amount)
        return f"✅ Added {amount} USDT to user `{user_id}`."
    except Exception as e:
        return f"❌ Error adding balance: {e}"


def approve_withdrawal_request(withdrawal_id: int) -> str:
    try:
        withdrawal = database.get_withdrawal(withdrawal_id)
        if not withdrawal:
            return f"❌ Withdrawal ID `{withdrawal_id}` not found."
        if withdrawal[4] != "Pending":
            return f"⚠️ Withdrawal ID `{withdrawal_id}` is already processed."
        database.update_withdrawal_status(withdrawal_id, "Approved")
        return f"✅ Withdrawal `{withdrawal_id}` marked as approved."
    except Exception as e:
        return f"❌ Error approving withdrawal: {e}"


def delete_product_admin(product_id: int) -> str:
    try:
        product = database.get_product(product_id)
        if not product:
            return f"❌ Product ID `{product_id}` not found."
        database.delete_product(product_id)
        return f"✅ Deleted product `{product_id}` and its stock."
    except Exception as e:
        return f"❌ Error deleting product: {e}"


def get_all_products_admin() -> str:
    try:
        products = database.get_all_products()
        if not products:
            return "⚠️ No products found."
        lines = ["📦 *Product List:*", ""]
        for p in products:
            pid, name, duration, price, stock, rating, description, features_json, note, emoji_id, *rest = (*p, None, None)
            is_free = rest[0] if len(rest) > 0 else 0
            free_channel = rest[1] if len(rest) > 1 else None
            sold = database.get_sold_count(pid)
            free_str = "🎁 Free" if is_free else ""
            channel_str = f" (@{free_channel})" if (is_free and free_channel) else ""
            lines.append(
                f"`{pid}`. *{name}* — {price} USDT | Stock: {stock} | Sold: {sold} {free_str}{channel_str}"
            )
        return "\n".join(lines)
    except Exception as e:
        return f"❌ Error fetching products: {e}"


def get_all_orders_admin(limit: int = 50) -> str:
    try:
        orders = database.get_all_orders_admin(limit)
        if not orders:
            return "⚠️ No orders found."
        lines = ["🧾 *Recent Orders:*", ""]
        for o in orders:
            order_id, user_id, product_id, qty, amount, pay_method, status, date_str, delivery_json = o
            product = database.get_product(product_id)
            product_name = product[1] if product else "Unknown"
            lines.append(
                f"`{order_id}` | User: `{user_id}` | Product: *{product_name}* | Qty: {qty} | {amount} USDT | {status} | {date_str}"
            )
        return "\n".join(lines)
    except Exception as e:
        return f"❌ Error fetching orders: {e}"


def get_withdrawal_requests_admin() -> str:
    try:
        withdrawals = database.get_pending_withdrawals()
        if not withdrawals:
            return "⚠️ No pending withdrawals."
        lines = ["💸 *Pending Withdrawals:*", ""]
        for w in withdrawals:
            wid, user_id, amount, address, status, date_str = w
            lines.append(
                f"`{wid}` | User: `{user_id}` | {amount} USDT | Address: `{address}` | {date_str}"
            )
        return "\n".join(lines)
    except Exception as e:
        return f"❌ Error fetching withdrawals: {e}"


def get_stats_admin() -> str:
    try:
        users = database.get_all_users()
        products_list = database.get_all_products()
        orders = database.get_all_orders_admin(1000)
        total_unsold = sum(database.get_unsold_count(p[0]) for p in products_list)
        total_sold = sum(database.get_sold_count(p[0]) for p in products_list)
        return (
            f"📊 *Stats*\n\n"
            f"👥 Users: {len(users)}\n"
            f"📦 Products: {len(products_list)}\n"
            f"🧾 Orders: {len(orders)}\n"
            f"🟢 Unsold Items: {total_unsold}\n"
            f"🔴 Sold Items: {total_sold}"
        )
    except Exception as e:
        return f"❌ Error fetching stats: {e}"
