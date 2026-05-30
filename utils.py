import uuid
from telegram import InlineKeyboardButton, InlineKeyboardMarkup


def generate_order_id():
    return "ORD" + str(uuid.uuid4())[:8].upper()


def btn(text, callback_data=None, url=None, style="default"):
    if url:
        return InlineKeyboardButton(text=text, url=url, style=style)
    return InlineKeyboardButton(text=text, callback_data=callback_data, style=style)


def build_menu(buttons, n_cols, header_buttons=None, footer_buttons=None):
    menu = [buttons[i:i + n_cols] for i in range(0, len(buttons), n_cols)]
    if header_buttons:
        menu.insert(0, header_buttons)
    if footer_buttons:
        menu.append(footer_buttons)
    return InlineKeyboardMarkup(menu)


def main_menu_keyboard():
    buttons = [
        btn("🛍️ Products", callback_data='products', style="success"),
        btn("👤 Profile", callback_data='profile', style="primary"),
        btn("📜 Purchase History", callback_data='purchase_history', style="danger"),
        btn("🔎 Order Details", callback_data='order_details', style="primary"),
        btn("💰 Wallet", callback_data='wallet', style="success"),
        btn("🆘 Support", callback_data='support', style="danger"),
    ]
    return build_menu(buttons, n_cols=2)


def products_list_keyboard(products):
    buttons = []

    for p in products:
        product_id = p[0]
        product_name = p[1]
        stock = p[4]

        if stock and stock > 0:
            text = f"📦 {product_name} — Stock: {stock}"
            style = "success"
        else:
            text = f"📦 {product_name} ❌ OUT OF STOCK"
            style = "danger"

        buttons.append(btn(text, callback_data=f'product_{product_id}', style=style))

    buttons.append(btn("🔙 Back to Main Menu", callback_data='main_menu', style="primary"))
    return build_menu(buttons, n_cols=1)


def product_details_keyboard():
    buttons = [
        btn("🟢 Order Now", callback_data='order_now', style="success"),
        btn("🔙 Back to Products", callback_data='products', style="danger"),
    ]
    return build_menu(buttons, n_cols=1)


def quantity_selection_keyboard():
    buttons = [
        btn("🔙 Back to Product", callback_data='back_to_product_details', style="danger"),
    ]
    return build_menu(buttons, n_cols=1)


def payment_method_keyboard():
    buttons = [
        btn("💳 Pay with Binance", callback_data='pay_binance', style="primary"),
        btn("👛 Pay with Wallet", callback_data='pay_wallet', style="success"),
        btn("🔙 Back to Quantity", callback_data='back_to_quantity', style="danger"),
    ]
    return build_menu(buttons, n_cols=1)


def binance_payment_keyboard():
    buttons = [
        btn("✅ I have sent the payment", callback_data='check_binance_payment', style="success"),
        btn("❌ Cancel Order", callback_data='cancel_order', style="danger"),
    ]
    return build_menu(buttons, n_cols=1)


def wallet_payment_keyboard():
    buttons = [
        btn("💚 Confirm & Pay", callback_data='confirm_wallet_payment', style="success"),
        btn("❌ Cancel", callback_data='cancel_order', style="danger"),
    ]
    return build_menu(buttons, n_cols=1)


def insufficient_balance_keyboard():
    buttons = [
        btn("🔙 Back to Payment", callback_data='back_to_payment_method', style="danger"),
    ]
    return build_menu(buttons, n_cols=1)


def order_confirmed_keyboard():
    buttons = [
        btn("🔙 Back to Main Menu", callback_data='main_menu', style="primary"),
    ]
    return build_menu(buttons, n_cols=1)


def wallet_options_keyboard():
    buttons = [
        btn("💰 Deposit", callback_data='deposit_wallet', style="success"),
        btn("💸 Withdraw", callback_data='withdraw_wallet', style="danger"),
    ]
    return build_menu(buttons, n_cols=2, footer_buttons=[btn("🔙 Back", callback_data='main_menu', style="primary")])


def deposit_wallet_keyboard():
    buttons = [
        btn("✅ I have sent the payment", callback_data='check_deposit_payment', style="success"),
        btn("🔙 Back", callback_data='wallet', style="danger"),
    ]
    return build_menu(buttons, n_cols=1)


def support_keyboard():
    buttons = [
        btn("❓ FAQ", callback_data='faq', style="primary"),
        btn("💬 Contact Admin", callback_data='contact_admin', style="success"),
        btn("🔔 Announcements", url='https://t.me/your_channel', style="primary"),
        btn("🔙 Back", callback_data='main_menu', style="danger"),
    ]
    return build_menu(buttons, n_cols=1)


def admin_main_keyboard():
    buttons = [
        btn("➕ Add Product", callback_data='admin_add_product', style="success"),
        btn("➕ Bulk Products", callback_data='admin_bulk_add_products', style="success"),
        btn("📦 Add Stock/Items", callback_data='admin_add_items', style="primary"),
        btn("💲 Edit Price", callback_data='admin_edit_price', style="primary"),
        btn("🔢 Edit Stock", callback_data='admin_edit_stock', style="primary"),
        btn("💰 Add Balance", callback_data='admin_add_balance', style="success"),
        btn("✅ Approve Withdrawal", callback_data='admin_approve_withdrawal', style="success"),
        btn("📢 Broadcast", callback_data='admin_broadcast', style="danger"),
        btn("🗑️ Delete Product", callback_data='admin_delete_product', style="danger"),
        btn("📜 View Products", callback_data='admin_view_products', style="primary"),
        btn("📝 All Orders", callback_data='admin_view_all_orders', style="primary"),
        btn("🔎 Order Details", callback_data='admin_order_details', style="primary"),
        btn("💸 Withdrawals", callback_data='admin_withdraw_requests', style="danger"),
        btn("📊 Stats", callback_data='admin_view_stats', style="success"),
    ]
    return build_menu(buttons, n_cols=2)


def admin_back_keyboard():
    buttons = [
        btn("🔙 Back to Admin Panel", callback_data='admin_panel_back', style="primary"),
    ]
    return build_menu(buttons, n_cols=1)


def admin_cancel_keyboard():
    buttons = [
        btn("❌ Cancel", callback_data='admin_panel_back', style="danger"),
    ]
    return build_menu(buttons, n_cols=1)
