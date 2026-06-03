import uuid
from telegram import InlineKeyboardButton, InlineKeyboardMarkup


# Emoji mapping.  All entries must refer to custom emoji IDs; the
# fallback emoji characters in the second element of the tuple are
# intentionally omitted to honour the requirement that only custom
# emojis be used in the bot UI.
EMOJIS = {
    "products": "5456140674028019486",
    "purchase_history": "5210956306952758910",
    "profile": "5253742260054409879",
    "support": "5443038326535759644",
    "wallet": "5409048419211682843",
    "order_details": "5282843764451195532",
    "welcome_star": "5325547803936572038",
    "choose_option": "5406745015365943482",
    "deposit": "5397916757333654639",
    "withdraw": "5402186569006210455",
    "back": "5416117059207572332",
    "confirm": "5206607081334906820",
    "cancel": "5210952531676504517",
    "order": "5406683434124859552",
    "faq": "5314504236132747481",
    "announcement": "5395695537687123235",
    "edit_stock": "5451882707875276247",
    "delete": "5445267414562389170",
    "broadcast": "5424818078833715060",
    "stats": "5231200819986047254",
    "view_products": "5231012545799666522",
    "binance_pay": "6222208096257712941",  # Binance icon custom emoji
    "wallet_pay": "5409048419211682843",   # Wallet icon
    # Additional icons for new admin actions reuse existing IDs
    "edit_details": "5451882707875276247",  # reuse edit_stock icon
    "edit_credentials": "5451882707875276247",  # reuse edit_stock icon
}


def generate_order_id():
    """Generate a short unique order identifier."""
    return "ORD" + str(uuid.uuid4())[:8].upper()


def btn(text, callback_data=None, url=None, style="default", emoji_id=None):
    api_kwargs = {}
    if emoji_id:
        api_kwargs["icon_custom_emoji_id"] = str(emoji_id)
    if url:
        return InlineKeyboardButton(text=text, url=url, style=style, api_kwargs=api_kwargs)
    return InlineKeyboardButton(text=text, callback_data=callback_data, style=style, api_kwargs=api_kwargs)


def back_btn(text="Back", callback_data="main_menu", style="primary"):
    return btn(text, callback_data=callback_data, style=style, emoji_id=EMOJIS["back"])


def build_menu(buttons, n_cols, header_buttons=None, footer_buttons=None):
    menu = [buttons[i:i + n_cols] for i in range(0, len(buttons), n_cols)]
    if header_buttons:
        menu.insert(0, header_buttons)
    if footer_buttons:
        menu.append(footer_buttons)
    return InlineKeyboardMarkup(menu)


# ─── USER KEYBOARDS ───────────────────────────────────────


def main_menu_keyboard():
    """Return the main menu for users.  Order details has been
    removed; purchase history now includes full details."""
    keyboard = [
        [btn("Products", callback_data='products', style="success", emoji_id=EMOJIS["products"])],
        [
            btn("Profile", callback_data='profile', style="primary", emoji_id=EMOJIS["profile"]),
            btn("Purchase History", callback_data='purchase_history', style="danger", emoji_id=EMOJIS["purchase_history"]),
        ],
        [
            btn("Wallet", callback_data='wallet', style="success", emoji_id=EMOJIS["wallet"]),
            btn("Support", callback_data='support', style="danger", emoji_id=EMOJIS["support"]),
        ],
    ]
    return InlineKeyboardMarkup(keyboard)


def products_list_keyboard(products):
    buttons = []
    for p in products:
        product_id = p[0]
        product_name = p[1]
        price = p[3]
        stock = p[4]
        product_emoji_id = p[9] if len(p) > 9 and p[9] else None
        text = f"{product_name}  {price}$  ({stock})"
        style = "success" if stock and stock > 0 else "danger"
        buttons.append(btn(text, callback_data=f'product_{product_id}', style=style, emoji_id=product_emoji_id or EMOJIS["products"]))
    buttons.append(back_btn("Back to Main Menu", callback_data='main_menu'))
    return build_menu(buttons, n_cols=1)


def product_details_keyboard():
    buttons = [
        btn("Order Now", callback_data='order_now', style="success", emoji_id=EMOJIS["order"]),
        back_btn("Back to Products", callback_data='products', style="danger"),
    ]
    return build_menu(buttons, n_cols=1)


def quantity_selection_keyboard():
    buttons = [back_btn("Back to Product", callback_data='back_to_product_details', style="danger")]
    return build_menu(buttons, n_cols=1)


def payment_method_keyboard():
    """Two payment options: Binance Pay ID OR Wallet - with custom emojis"""
    return build_menu([
        btn("Pay with Binance Pay ID", callback_data="pay_binance", style="success", emoji_id=EMOJIS["binance_pay"]),
        btn("Pay with Wallet", callback_data="pay_wallet", style="primary", emoji_id=EMOJIS["wallet_pay"]),
        back_btn("Back to Quantity", callback_data="back_to_quantity", style="danger"),
    ], n_cols=1)


def binance_payment_keyboard():
    """Purchase: Payment details message. Buttons: I have sent payment + Cancel Order"""
    return build_menu([
        btn("I have sent payment", callback_data="check_binance_payment", style="success", emoji_id=EMOJIS["confirm"]),
        btn("Cancel Order", callback_data="cancel_order", style="danger", emoji_id=EMOJIS["cancel"]),
    ], n_cols=1)


def ask_order_id_keyboard():
    """Purchase: When the bot asks for an order ID.  Only Cancel button"""
    return build_menu([
        btn("Cancel Order", callback_data="cancel_order", style="danger", emoji_id=EMOJIS["cancel"]),
    ], n_cols=1)


def deposit_enter_amount_keyboard():
    """Deposit Step 1: ask for amount.  Only Back button"""
    return build_menu([
        back_btn("Back", callback_data="wallet", style="danger"),
    ], n_cols=1)


def deposit_wallet_keyboard():
    """Deposit Step 2: show Binance ID and amount.  Buttons: I have sent payment + Back"""
    return build_menu([
        btn("I have sent payment", callback_data="check_deposit_payment", style="success", emoji_id=EMOJIS["confirm"]),
        back_btn("Back", callback_data="wallet", style="danger"),
    ], n_cols=1)


def ask_deposit_ref_keyboard():
    """Deposit Step 3: ask for transaction reference.  Only Cancel button"""
    return build_menu([
        back_btn("Cancel", callback_data="wallet", style="danger"),
    ], n_cols=1)


def wallet_payment_keyboard():
    """Wallet payment confirmation keyboard"""
    buttons = [
        btn("Confirm & Pay", callback_data='confirm_wallet_payment', style="success", emoji_id=EMOJIS["confirm"]),
        btn("Cancel", callback_data='cancel_order', style="danger", emoji_id=EMOJIS["cancel"]),
    ]
    return build_menu(buttons, n_cols=1)


def insufficient_balance_keyboard():
    buttons = [back_btn("Back to Payment", callback_data='back_to_payment_method', style="danger")]
    return build_menu(buttons, n_cols=1)


def order_confirmed_keyboard():
    buttons = [
        btn("Order Details", callback_data='order_details', style="primary", emoji_id=EMOJIS["order_details"]),
        back_btn("Back to Main Menu", callback_data='main_menu'),
    ]
    return build_menu(buttons, n_cols=1)


def wallet_options_keyboard():
    return build_menu([
        btn("Deposit with Binance Pay ID", callback_data="deposit_wallet", style="success", emoji_id=EMOJIS["deposit"]),
    ], n_cols=1, footer_buttons=[
        back_btn("Back", callback_data="main_menu")
    ])


def support_keyboard():
    buttons = [
        btn("FAQ", callback_data='faq', style="primary", emoji_id=EMOJIS["faq"]),
        btn("Contact Support", url="https://t.me/Bunnyhaccks", style="success", emoji_id=EMOJIS["support"]),
        btn("Announcements", url='https://t.me/bunnyhackss', style="primary", emoji_id=EMOJIS["announcement"]),
        back_btn("Back", callback_data='main_menu', style="danger"),
    ]
    return build_menu(buttons, n_cols=1)


def product_update_purchase_keyboard(product, style="success"):
    if not product:
        return None
    product_id = product[0]
    product_name = product[1]
    product_emoji_id = product[9] if len(product) > 9 and product[9] else None
    keyboard = [[
        btn(f"Buy {product_name}", callback_data=f"product_{product_id}", style=style, emoji_id=product_emoji_id or EMOJIS["products"])
    ]]
    return InlineKeyboardMarkup(keyboard)


# ─── ADMIN KEYBOARDS ──────────────────────────────────────


def admin_main_keyboard():
    buttons = [
        btn("Add Product", callback_data='admin_add_product', style="success", emoji_id=EMOJIS["deposit"]),
        btn("Bulk Products", callback_data='admin_bulk_add_products', style="success", emoji_id=EMOJIS["deposit"]),
        btn("Add Stock/Items", callback_data='admin_add_items', style="primary", emoji_id=EMOJIS["view_products"]),
        btn("Edit Price", callback_data='admin_edit_price', style="primary", emoji_id=EMOJIS["wallet"]),
        btn("Edit Stock", callback_data='admin_edit_stock', style="primary", emoji_id=EMOJIS["edit_stock"]),
        btn("Edit Details", callback_data='admin_edit_details', style="primary", emoji_id=EMOJIS["edit_details"]),
        btn("Edit Credentials", callback_data='admin_edit_credentials', style="primary", emoji_id=EMOJIS["edit_credentials"]),
        btn("Add Balance", callback_data='admin_add_balance', style="success", emoji_id=EMOJIS["deposit"]),
        btn("Approve Withdrawal", callback_data='admin_approve_withdrawal', style="success", emoji_id=EMOJIS["confirm"]),
        btn("Broadcast", callback_data='admin_broadcast', style="danger", emoji_id=EMOJIS["broadcast"]),
        btn("Delete Product", callback_data='admin_delete_product', style="danger", emoji_id=EMOJIS["delete"]),
        btn("Order Details", callback_data='admin_order_details', style="primary", emoji_id=EMOJIS["order_details"]),
        btn("View Products", callback_data='admin_view_products', style="primary", emoji_id=EMOJIS["view_products"]),
        btn("All Orders", callback_data='admin_view_all_orders', style="primary", emoji_id=EMOJIS["order"]),
        btn("Withdrawals", callback_data='admin_withdraw_requests', style="danger", emoji_id=EMOJIS["withdraw"]),
        btn("Stats", callback_data='admin_view_stats', style="success", emoji_id=EMOJIS["stats"]),
    ]
    return build_menu(buttons, n_cols=2)


def admin_back_keyboard():
    buttons = [back_btn("Back to Admin Panel", callback_data='admin_panel_back')]
    return build_menu(buttons, n_cols=1)


def admin_cancel_keyboard():
    buttons = [back_btn("Cancel", callback_data='admin_panel_back', style="danger")]
    return build_menu(buttons, n_cols=1)