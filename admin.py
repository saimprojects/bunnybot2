import database
import json
import config
import re
from html import escape as html_escape
import utils


def is_admin(user_id):
    try:
        return int(user_id) == int(config.ADMIN_ID)
    except Exception:
        return False




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

    if len(fields) != 6:
        fields = [x.strip() for x in block.split("|")]

    if len(fields) != 6:
        raise ValueError(
            "Product format must have 6 fields: "
            "Name | Duration | Price | Description | Note | Sticker Emoji ID"
        )

    return {
        "name": fields[0],
        "duration": fields[1],
        "price": float(fields[2]),
        "stock": 0,
        # Database compatibility ke liye rating/features default save rahenge,
        # lekin admin format aur product details mein show/use nahi honge.
        "rating": 0,
        "description": fields[3],
        "features": [],
        "note": fields[4],
        "emoji_id": fields[5],
    }

def parse_bulk_products_format(text):
    blocks = re.findall(r'\[(.*?)\]', text, flags=re.DOTALL)

    if not blocks:
        return [parse_product_block(text)]

    return [parse_product_block(block) for block in blocks]


def html_code(value):
    return f"<code>{html_escape(str(value))}</code>"


def ce(name, fallback=None):
    return utils.ce(name, fallback)


def html_bold(value):
    return f"<b>{html_escape(str(value))}</b>"


def product_edit_format(product):
    if not product:
        return ""
    return (
        f"{product[1]} | {product[2]} | {product[3]} | "
        f"{product[6]} | {product[8]} | {product[9] if len(product) > 9 and product[9] else 'None'}"
    )


def get_product_detail_edit_guide(product):
    current_format = product_edit_format(product)
    return (
        f"{ce('edit_stock')} <b>Edit Product Details</b>\n\n"
        "Change only the fields you want, but send the full line back in the same format.\n\n"
        "<b>Format:</b>\n"
        "<code>Name | Duration | Price | Description | Note | Sticker Emoji ID</code>\n\n"
        "<b>Current:</b>\n"
        f"{html_code(current_format)}\n\n"
        "<b>Example:</b>\n"
        "<code>netflix | 3month | 7 | testing2 | testing | 1873678163871</code>"
    )


def edit_product_details_admin(product_id, block):
    product = database.get_product(product_id)
    if not product:
        return f"{ce('cancel')} Product not found."

    parsed = parse_product_block(block)
    database.update_product_details(
        product_id,
        parsed["name"],
        parsed["duration"],
        parsed["price"],
        parsed["description"],
        parsed["note"],
        parsed["emoji_id"]
    )
    return f"{ce('confirm')} Product ID {html_code(product_id)} details updated successfully."


def stock_edit_format(product_id, items):
    formatted_items = []
    for item in items:
        data = item.get("data", {})
        pairs = []
        for key, value in data.items():
            pairs.append(f"{key}:{value}")
        formatted_items.append("{" + ",".join(pairs) + "}")
    return f"{product_id}[" + ",".join(formatted_items) + "]"


def get_stock_detail_edit_guide(product_id):
    product = database.get_product(product_id)
    if not product:
        return None

    items = database.get_stock_items_for_edit(product_id)
    current_format = stock_edit_format(product_id, items)
    if not items:
        current_format = f"{product_id}[{{email:example,password:example}}]"

    return (
        f"{ce('edit_stock')} <b>Edit Stock Details</b>\n\n"
        "This edits only unsold stock items. Sold delivered items are not changed.\n"
        "Send the full updated stock block back after editing.\n\n"
        "<b>Format:</b>\n"
        "<code>PID[{field:value},{field:value}]</code>\n\n"
        "<b>Current:</b>\n"
        f"{html_code(current_format)}\n\n"
        "<b>Example:</b>\n"
        f"<code>{product_id}[{{email:user1@example.com,password:pass1}},{{email:user2@example.com,password:pass2}}]</code>"
    )


def edit_stock_details_admin(product_id, text):
    sections = parse_stock_bulk_format(text)
    if len(sections) != 1:
        return f"{ce('cancel')} Send one product stock block only."

    parsed_product_id, items = sections[0]
    if parsed_product_id != product_id:
        return f"{ce('cancel')} Product ID mismatch. Expected {html_code(product_id)}, got {html_code(parsed_product_id)}."

    product = database.get_product(product_id)
    if not product:
        return f"{ce('cancel')} Product not found."

    inserted = database.replace_unsold_stock_items(product_id, items)
    return f"{ce('confirm')} Product ID {html_code(product_id)} stock details updated. Unsold stock is now {html_code(inserted)}."


def add_product_admin(name, duration, price, description, note, emoji_id):
    try:
        database.add_product(
            name,
            duration,
            price,
            0,
            0,          # rating default, hidden
            description,
            [],         # features default, hidden
            note,
            emoji_id
        )
        return (
            f"{ce('confirm')} Product {html_bold(name)} added successfully "
            f"with stock {html_code(0)} and sticker ID {html_code(emoji_id)}."
        )
    except Exception as e:
        return f"{ce('cancel')} Error adding product: {html_escape(str(e))}"

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

        return f"{ce('confirm')} Successfully added {html_bold(added_count)} products with stock {html_code(0)}."

    except Exception as e:
        return f"{ce('cancel')} Error adding bulk products: {html_escape(str(e))}"


def add_stock_bulk_admin(stock_sections):
    try:
        total_added = 0
        report = f"{ce('box')} <b>Stock Add Report:</b>\n\n"

        for product_id, items_data in stock_sections:
            product = database.get_product(product_id)
            if not product:
                report += f"{ce('cancel')} Product ID {html_code(product_id)} not found.\n"
                continue

            added_count = 0

            for item in items_data:
                if item:
                    database.add_unsold_item(product_id, item)
                    added_count += 1

            if added_count > 0:
                database.update_product_stock(product_id, added_count)

            total_added += added_count
            report += f"{ce('confirm')} Product ID {html_code(product_id)}: Added {html_code(added_count)} items.\n"

        report += f"\n{utils.DIVIDER}\nTotal Added: {html_bold(total_added)}"
        return report

    except Exception as e:
        return f"{ce('cancel')} Error adding stock: {html_escape(str(e))}"


def add_freebie_stock_bulk_admin(stock_sections):
    try:
        total_added = 0
        report = f"{ce('gift')} <b>Freebie Stock Add Report:</b>\n\n"

        for product_id, items_data in stock_sections:
            product = database.get_product(product_id)
            if not product:
                report += f"{ce('cancel')} Product ID {html_code(product_id)} not found.\n"
                continue

            is_freebie = product[10] if len(product) > 10 else False
            if not is_freebie:
                report += f"{ce('cancel')} Product ID {html_code(product_id)} is not marked as a freebie.\n"
                continue

            added_count = 0
            for item in items_data:
                if item:
                    database.add_unsold_item(product_id, item)
                    added_count += 1

            if added_count > 0:
                database.update_product_stock(product_id, added_count)

            total_added += added_count
            report += f"{ce('confirm')} Product ID {html_code(product_id)}: Added {html_code(added_count)} freebie items.\n"

        report += f"\nTotal Added: {html_bold(total_added)}"
        return report

    except Exception as e:
        return f"{ce('cancel')} Error adding freebie stock: {html_escape(str(e))}"


def get_all_products_admin():
    products = database.get_all_products()

    if not products:
        return f"{ce('no_orders')} No products in the database."

    message = f"{ce('box')} <b>All Products:</b>\n\n"

    for p in products:
        stock_status = f"{ce('confirm')} In Stock" if p[4] > 0 else f"{ce('cancel')} OUT OF STOCK"

        message += (
            f"{ce('id')} ID: {html_code(p[0])}\n"
            f"{ce('box')} Name: {html_bold(p[1])}\n"
            f"{ce('date')} Duration: {html_escape(str(p[2]))}\n"
            f"{ce('wallet')} Price: {html_escape(str(p[3]))} USDT\n"
            f"{ce('box')} Stock: {html_escape(str(p[4]))} - {stock_status}\n"
            f"{ce('puzzle')} Sticker ID: {html_code(p[9] if len(p) > 9 and p[9] else 'None')}\n"
            f"{utils.DIVIDER}\n"
        )

    return message


def edit_product_price(product_id, new_price):
    try:
        product = database.get_product(product_id)

        if not product:
            return f"{ce('cancel')} Product not found."

        database.set_product_price(product_id, new_price)
        return f"{ce('confirm')} Price for product ID {html_code(product_id)} updated to {html_escape(str(new_price))} USDT."

    except Exception as e:
        return f"{ce('cancel')} Error updating price: {html_escape(str(e))}"


def edit_product_stock(product_id, new_stock):
    try:
        product = database.get_product(product_id)

        if not product:
            return f"{ce('cancel')} Product not found."

        database.set_product_stock(product_id, new_stock)
        return f"{ce('confirm')} Stock for product ID {html_code(product_id)} updated to {html_escape(str(new_stock))}."

    except Exception as e:
        return f"{ce('cancel')} Error updating stock: {html_escape(str(e))}"


def delete_product_admin(product_id):
    try:
        product = database.get_product(product_id)

        if not product:
            return f"{ce('cancel')} Product not found."

        database.delete_product(product_id)
        return f"{ce('confirm')} Product {html_bold(product[1])} deleted successfully."

    except Exception as e:
        return f"{ce('cancel')} Error deleting product: {html_escape(str(e))}"


def get_all_orders_admin():
    orders = database.get_all_orders(limit=20)

    if not orders:
        return f"{ce('no_orders')} No orders found."

    message = f"{ce('edit_stock')} <b>Recent Orders (last 20):</b>\n\n"

    for o in orders:
        product = database.get_product(o[2])
        product_name = product[1] if product else "Unknown"

        message += (
            f"{ce('receipt')} Order ID: {html_code(o[0])}\n"
            f"{ce('profile')} User ID: {html_code(o[1])}\n"
            f"{ce('box')} Product: {html_escape(str(product_name))}\n"
            f"{ce('quantity')} Qty: {html_escape(str(o[3]))}\n"
            f"{ce('wallet')} Amount: {html_escape(str(o[4]))} USDT\n"
            f"{ce('deposit')} Method: {html_escape(str(o[5]))}\n"
            f"{ce('confirm')} Status: {html_escape(str(o[6]))}\n"
            f"{ce('date')} Date: {html_escape(str(o[7]))}\n"
            f"{utils.DIVIDER}\n"
        )

    return message


def add_balance_admin(user_id, amount):
    try:
        user = database.get_user(user_id)

        if not user:
            return f"{ce('cancel')} User not found."

        database.update_user_wallet(user_id, amount)
        database.add_transaction(user_id, "Deposit (Admin)", amount)

        return f"{ce('confirm')} Added {html_escape(str(amount))} USDT to user {html_code(user_id)} wallet."

    except Exception as e:
        return f"{ce('cancel')} Error adding balance: {html_escape(str(e))}"


def get_withdrawal_requests_admin():
    withdrawals = database.get_pending_withdrawals()

    if not withdrawals:
        return f"{ce('no_orders')} No pending withdrawal requests."

    message = f"{ce('withdraw')} <b>Pending Withdrawals:</b>\n\n"

    for req in withdrawals:
        message += (
            f"{ce('id')} Withdrawal ID: {html_code(req[0])}\n"
            f"{ce('profile')} User ID: {html_code(req[1])}\n"
            f"{ce('wallet')} Amount: {html_escape(str(req[2]))} USDT\n"
            f"{ce('pin')} Address: {html_code(req[3])}\n"
            f"{ce('hourglass')} Status: {html_escape(str(req[4]))}\n"
            f"{ce('date')} Date: {html_escape(str(req[5]))}\n"
            f"{utils.DIVIDER}\n"
        )

    return message


def approve_withdrawal_admin(withdrawal_id):
    try:
        withdrawal = database.get_withdrawal(withdrawal_id)

        if not withdrawal:
            return f"{ce('cancel')} Withdrawal request not found."

        if withdrawal[4] != "Pending":
            return f"{ce('warning')} Withdrawal already marked as {html_escape(str(withdrawal[4]))}."

        database.update_withdrawal_status(withdrawal_id, "Approved")

        return f"{ce('confirm')} Withdrawal request {html_code(withdrawal_id)} approved. Send funds manually."

    except Exception as e:
        return f"{ce('cancel')} Error approving withdrawal: {html_escape(str(e))}"


def get_stats_admin():
    conn = database.get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) FROM users")
    total_users = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM products")
    total_products = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM orders")
    total_orders = cursor.fetchone()[0]

    cursor.execute("SELECT SUM(total_amount) FROM orders WHERE status = 'Confirmed'")
    total_revenue = cursor.fetchone()[0] or 0

    cursor.execute("SELECT SUM(wallet_balance) FROM users")
    total_wallet = cursor.fetchone()[0] or 0

    cursor.execute("SELECT COUNT(*) FROM withdrawals WHERE status = 'Pending'")
    total_pending_withdrawals = cursor.fetchone()[0]

    cursor.execute("SELECT SUM(stock) FROM products")
    total_stock = cursor.fetchone()[0] or 0

    cursor.execute("SELECT COUNT(*) FROM unsold_items WHERE is_sold = 0")
    total_unsold_items = cursor.fetchone()[0]

    conn.close()

    return (
        f"{ce('stats')} <b>Bot Statistics:</b>\n\n"
        f"{ce('users')} Total Users: {html_escape(str(total_users))}\n"
        f"{ce('box')} Total Products: {html_escape(str(total_products))}\n"
        f"{ce('box')} Product Stock Count: {html_escape(str(total_stock))}\n"
        f"{ce('clipboard')} Unsold Items Count: {html_escape(str(total_unsold_items))}\n"
        f"{ce('order')} Total Orders: {html_escape(str(total_orders))}\n"
        f"{ce('wallet')} Total Revenue: {html_escape(str(round(total_revenue, 2)))} USDT\n"
        f"{ce('wallet_purse')} Users Wallet Balance: {html_escape(str(round(total_wallet, 2)))} USDT\n"
        f"{ce('withdraw')} Pending Withdrawals: {html_escape(str(total_pending_withdrawals))}\n"
    )

def get_freebies_settings_admin():
    config_data = database.get_freebies_config()
    status = f"Enabled {ce('confirm')}" if config_data[3] else f"Disabled {ce('cancel')}"
    
    return (
        f"{ce('gift')} <b>Freebies Settings</b>\n\n"
        f"Status: {status}\n"
        f"Channel ID: {html_code(config_data[1])}\n"
        f"Channel Link: {html_escape(str(config_data[2]))}\n\n"
        f"{utils.DIVIDER}\n"
        f"To update, send:\n"
        f"{html_code('freebie_setup | channel_id | channel_link | enable/disable')}"
    )

def get_freebie_products_admin():
    products = database.get_freebie_products()
    if not products:
        return f"{ce('no_orders')} No products are currently set as Freebies."
        
    message = f"{ce('gift')} <b>Freebie Products:</b>\n\n"
    for p in products:
        message += f"{ce('id')} ID: {html_code(p[0])} | {ce('box')} Name: {html_bold(p[1])}\n"
    
    message += f"\nTo toggle a product as freebie, send:\n{html_code('toggle_freebie | product_id')}"
    return message


def toggle_product_freebie_admin(product_id):
    product = database.get_product(product_id)
    if not product:
        return f"{ce('cancel')} Product not found."

    current = product[10] if len(product) > 10 else False
    database.toggle_product_freebie(product_id, not current)
    new_status = "enabled" if not current else "disabled"
    return f"{ce('confirm')} Freebie status for product ID {html_code(product_id)} is now {html_bold(new_status)}."


def guide_add_product():
    return (
        f"{ce('deposit')} <b>Add Product</b>\n\n"
        "Send one product in this full format:\n"
        "<code>Name | Duration | Price | Description | Note | Sticker Emoji ID</code>\n\n"
        "Example:\n"
        "<code>netflix | 1month | 3 | testing | testing | 1873678163871</code>"
    )


def guide_bulk_products():
    return (
        f"{ce('deposit')} <b>Bulk Products</b>\n\n"
        "Send each product inside square brackets.\n\n"
        "Format:\n"
        "<code>[Name | Duration | Price | Description | Note | Sticker Emoji ID]</code>\n\n"
        "Example:\n"
        "<code>[netflix | 1month | 3 | testing | testing | 1873678163871][prime | 1month | 2 | testing | testing | 1873678163871]</code>"
    )


def guide_add_stock():
    return (
        f"{ce('box')} <b>Add Stock/Items</b>\n\n"
        "Send stock for one or more product IDs. Every item goes inside braces.\n\n"
        "Format:\n"
        "<code>PID[{field:value},{field:value}]</code>\n\n"
        "Example:\n"
        "<code>1[{email:user1@example.com,password:pass1},{email:user2@example.com,password:pass2}]</code>"
    )


def guide_edit_price():
    return (
        f"{ce('wallet')} <b>Edit Price</b>\n\n"
        "Send product ID and new price.\n\n"
        "Format:\n"
        "<code>PID | Price</code>\n\n"
        "Example:\n"
        "<code>1 | 4.5</code>"
    )


def guide_edit_stock_count():
    return (
        f"{ce('edit_stock')} <b>Edit Stock Count</b>\n\n"
        "This changes only the visible stock number. To edit credentials, use Edit Stock Details.\n\n"
        "Format:\n"
        "<code>PID | Stock</code>\n\n"
        "Example:\n"
        "<code>1 | 10</code>"
    )


def guide_add_balance():
    return (
        f"{ce('wallet')} <b>Add Balance</b>\n\n"
        "Send user ID and amount to add to wallet.\n\n"
        "Format:\n"
        "<code>UID | Amt</code>\n\n"
        "Example:\n"
        "<code>123456789 | 5</code>"
    )


def guide_broadcast():
    return (
        f"{ce('broadcast')} <b>Broadcast</b>\n\n"
        "Send plain text. To include a custom emoji, write its ID like this:\n"
        "<code>{[8887897]}</code>\n\n"
        "Example:\n"
        "<code>New stock is live {[8887897]}</code>"
    )


def guide_delete_product():
    return (
        f"{ce('delete')} <b>Delete Product</b>\n\n"
        "Send the product ID to delete.\n\n"
        "Format:\n"
        "<code>PID</code>\n\n"
        "Example:\n"
        "<code>1</code>"
    )


def guide_order_details():
    return (
        f"{ce('order_details')} <b>Order Details</b>\n\n"
        "Send the order ID.\n\n"
        "Format:\n"
        "<code>ORDXXXXXXXX</code>"
    )


def guide_approve_withdrawal():
    return (
        f"{ce('withdraw')} <b>Approve Withdrawal</b>\n\n"
        "Send pending withdrawal ID.\n\n"
        "Format:\n"
        "<code>Withdrawal ID</code>\n\n"
        "Example:\n"
        "<code>1</code>"
    )


def guide_freebie_products():
    return (
        get_freebie_products_admin()
        + "\n\nUse this format to toggle any product:\n"
        + html_code("toggle_freebie | product_id")
    )


def guide_freebie_stock():
    return (
        f"{ce('gift')} <b>Freebie Stock</b>\n\n"
        "Add stock only for products already marked as freebies.\n\n"
        "Format:\n"
        "<code>PID[{field:value},{field:value}]</code>\n\n"
        "Example:\n"
        "<code>1[{email:free1@example.com,password:pass1}]</code>"
    )
