"""
Utility functions for building Telegram inline keyboards and order IDs.

This module centralizes how buttons are laid out and ensures that
custom emojis are applied consistently.  All emojis used here are
custom and require the corresponding emoji to exist on the bot's
account.  The keyboards defined here are used both for user flows
and admin flows.
"""

import uuid
from telegram import InlineKeyboardButton, InlineKeyboardMarkup


# Mapping from logical names to custom emoji IDs.  Only custom
# emojis are referenced here.  There are no fallback characters to
# honour the requirement that only custom emojis be used in the bot
# UI.
EMOJIS = {
    "products": "5456140674028019486",
    "purchase_history": "5210956306952758910",
    "profile": "5461117441612462242",
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
    "binance_pay": "6222208096257712941",
    "wallet_pay": "5409048419211682843",
    "edit_details": "5451882707875276247",
    "edit_credentials": "5451882707875276247",
    "freebie": "5217822164362739968",
}


def generate_order_id() -> str:
    """Generate a short unique order identifier."""
    return "ORD" + str(uuid.uuid4())[:8].upper()


def btn(text: str, callback_data: str = None, url: str = None, emoji_id: str = None) -> InlineKeyboardButton:
    """Create a Telegram inline button.

    Important:
    python-telegram-bot's InlineKeyboardButton does NOT support
    ``icon_custom_emoji_id``. Passing that argument crashes the bot with:
    ``TypeError: InlineKeyboardButton.__init__() got an unexpected keyword argument 'icon_custom_emoji_id'``.

    So ``emoji_id`` is accepted only for compatibility with the rest of the
    code, but it is intentionally not passed to Telegram. Custom emojis should
    be used inside message text via <tg-emoji> tags, not inside inline buttons.
    """
    if url:
        return InlineKeyboardButton(text=text, url=url)
    return InlineKeyboardButton(text=text, callback_data=callback_data)


def back_btn(text: str = "Back", callback_data: str = "main_menu") -> InlineKeyboardButton:
    return btn(text, callback_data=callback_data, emoji_id=EMOJIS["back"])


def build_menu(buttons, n_cols, header_buttons=None, footer_buttons=None) -> InlineKeyboardMarkup:
    menu = [buttons[i:i + n_cols] for i in range(0, len(buttons), n_cols)]
    if header_buttons:
        menu.insert(0, header_buttons)
    if footer_buttons:
        menu.append(footer_buttons)
    return InlineKeyboardMarkup(menu)


# ─── USER KEYBOARDS ────────────────────────────────────────────────


def main_menu_keyboard() -> InlineKeyboardMarkup:
    keyboard = [
        [btn("Products", callback_data='products', emoji_id=EMOJIS["products"])],
        [
            btn("Profile", callback_data='profile', emoji_id=EMOJIS["profile"]),
            btn("Purchase History", callback_data='purchase_history', emoji_id=EMOJIS["purchase_history"]),
        ],
        [
            btn("Wallet", callback_data='wallet', emoji_id=EMOJIS["wallet"]),
            btn("Support", callback_data='support', emoji_id=EMOJIS["support"]),
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
        buttons.append(btn(text, callback_data=f'product_{product_id}', emoji_id=product_emoji_id or EMOJIS["products"]))
    buttons.append(back_btn("Back to Main Menu", callback_data='main_menu'))
    return build_menu(buttons, n_cols=1)


def product_details_keyboard(product=None) -> InlineKeyboardMarkup:
    buttons = []
    is_free = False
    if product:
        # product tuple: id,name,duration,price,stock,rating,description,features,note,emoji_id,is_free,free_channel
        if isinstance(product, tuple) and len(product) > 10:
            is_free = bool(product[10])
        elif isinstance(product, dict):
            is_free = bool(product.get("is_free"))
    if is_free:
        buttons.append(btn("Claim Free", callback_data='claim_free', emoji_id=EMOJIS["freebie"]))
    else:
        buttons.append(btn("Order Now", callback_data='order_now', emoji_id=EMOJIS["order"]))
    buttons.append(back_btn("Back to Products", callback_data='products'))
    return build_menu(buttons, n_cols=1)


def quantity_selection_keyboard() -> InlineKeyboardMarkup:
    # For simplicity we provide a single back button.  Quantity is
    # entered via text message in the current design.
    return build_menu([back_btn("Back to Product", callback_data='back_to_product_details')], n_cols=1)


def payment_method_keyboard() -> InlineKeyboardMarkup:
    return build_menu([
        btn("Pay with Binance Pay ID", callback_data="pay_binance", emoji_id=EMOJIS["binance_pay"]),
        btn("Pay with Wallet", callback_data="pay_wallet", emoji_id=EMOJIS["wallet_pay"]),
        back_btn("Back to Quantity", callback_data='back_to_quantity'),
    ], n_cols=1)


def binance_payment_keyboard() -> InlineKeyboardMarkup:
    return build_menu([
        btn("I have sent payment", callback_data="check_binance_payment", emoji_id=EMOJIS["confirm"]),
        btn("Cancel Order", callback_data="cancel_order", emoji_id=EMOJIS["cancel"]),
    ], n_cols=1)


def ask_order_id_keyboard() -> InlineKeyboardMarkup:
    return build_menu([btn("Cancel Order", callback_data="cancel_order", emoji_id=EMOJIS["cancel"])], n_cols=1)


def deposit_enter_amount_keyboard() -> InlineKeyboardMarkup:
    return build_menu([back_btn("Back", callback_data="wallet")], n_cols=1)


def deposit_wallet_keyboard() -> InlineKeyboardMarkup:
    return build_menu([
        btn("I have sent payment", callback_data="check_deposit_payment", emoji_id=EMOJIS["confirm"]),
        back_btn("Back", callback_data="wallet"),
    ], n_cols=1)


def ask_deposit_ref_keyboard() -> InlineKeyboardMarkup:
    return build_menu([back_btn("Cancel", callback_data="wallet")], n_cols=1)


def wallet_payment_keyboard() -> InlineKeyboardMarkup:
    return build_menu([
        btn("Confirm & Pay", callback_data='confirm_wallet_payment', emoji_id=EMOJIS["confirm"]),
        btn("Cancel", callback_data='cancel_order', emoji_id=EMOJIS["cancel"]),
    ], n_cols=1)


def insufficient_balance_keyboard() -> InlineKeyboardMarkup:
    return build_menu([back_btn("Back to Payment", callback_data='back_to_payment_method')], n_cols=1)


def wallet_options_keyboard() -> InlineKeyboardMarkup:
    return build_menu([
        btn("Deposit with Binance Pay ID", callback_data="deposit_wallet", emoji_id=EMOJIS["deposit"]),
    ], n_cols=1, footer_buttons=[back_btn("Back", callback_data="main_menu")])


def support_keyboard() -> InlineKeyboardMarkup:
    return build_menu([
        btn("FAQ", callback_data='faq', emoji_id=EMOJIS["faq"]),
        btn("Contact Support", url="https://t.me/Bunnyhaccks", emoji_id=EMOJIS["support"]),
        btn("Announcements", url='https://t.me/bunnyhackss', emoji_id=EMOJIS["announcement"]),
        back_btn("Back", callback_data='main_menu'),
    ], n_cols=1)


def product_update_purchase_keyboard(product, style="success") -> InlineKeyboardMarkup:
    if not product:
        return None
    product_id = product[0]
    product_name = product[1]
    product_emoji_id = product[9] if len(product) > 9 and product[9] else None
    keyboard = [[btn(f"Buy {product_name}", callback_data=f"product_{product_id}", emoji_id=product_emoji_id or EMOJIS["products"] )]]
    return InlineKeyboardMarkup(keyboard)


# ─── ADMIN KEYBOARDS ───────────────────────────────────────────────


def admin_main_keyboard() -> InlineKeyboardMarkup:
    buttons = [
        btn("Add Product", callback_data='admin_add_product', emoji_id=EMOJIS["deposit"]),
        btn("Bulk Products", callback_data='admin_bulk_add_products', emoji_id=EMOJIS["deposit"]),
        btn("Add Stock/Items", callback_data='admin_add_items', emoji_id=EMOJIS["view_products"]),
        btn("Edit Price", callback_data='admin_edit_price', emoji_id=EMOJIS["wallet"]),
        btn("Edit Stock", callback_data='admin_edit_stock', emoji_id=EMOJIS["edit_stock"]),
        btn("Edit Details", callback_data='admin_edit_details', emoji_id=EMOJIS["edit_details"]),
        btn("Edit Credentials", callback_data='admin_edit_credentials', emoji_id=EMOJIS["edit_credentials"]),
        btn("Add Balance", callback_data='admin_add_balance', emoji_id=EMOJIS["deposit"]),
        btn("Approve Withdrawal", callback_data='admin_approve_withdrawal', emoji_id=EMOJIS["confirm"]),
        btn("Broadcast", callback_data='admin_broadcast', emoji_id=EMOJIS["broadcast"]),
        btn("Delete Product", callback_data='admin_delete_product', emoji_id=EMOJIS["delete"]),
        btn("Order Details", callback_data='admin_order_details', emoji_id=EMOJIS["order_details"]),
        btn("View Products", callback_data='admin_view_products', emoji_id=EMOJIS["view_products"]),
        btn("All Orders", callback_data='admin_view_all_orders', emoji_id=EMOJIS["order"]),
        btn("Withdrawals", callback_data='admin_withdraw_requests', emoji_id=EMOJIS["withdraw"]),
        btn("Stats", callback_data='admin_view_stats', emoji_id=EMOJIS["stats"]),
        btn("Freebies", callback_data='admin_set_freebie', emoji_id=EMOJIS["freebie"]),
    ]
    return build_menu(buttons, n_cols=2)


def admin_back_keyboard() -> InlineKeyboardMarkup:
    return build_menu([back_btn("Back to Admin Panel", callback_data='admin_panel_back')], n_cols=1)


def admin_cancel_keyboard() -> InlineKeyboardMarkup:
    return build_menu([back_btn("Cancel", callback_data='admin_panel_back')], n_cols=1)
