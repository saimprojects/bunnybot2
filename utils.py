import uuid
import re
from html import escape as html_escape
from telegram import InlineKeyboardButton, InlineKeyboardMarkup


EMOJIS = {
    # start
    "products": ("5456140674028019486", "🛍️"),
    "purchase_history": ("5210956306952758910", "📜"),
    "welcome_star": ("5325547803936572038", "✨"),
    "choose_option": ("5406745015365943482", "👇"),

    # profile
    "profile": ("5461117441612462242", "👤"),
    "id": ("5427168083074628963", "🆔"),
    "username": ("5260293700088511294", "📛"),
    "date": ("5413879192267805083", "📅"),
    "wallet": ("5409048419211682843", "💰"),
    "box": ("5231012545799666522", "📦"),
    "gift": ("5217822164362739968", "🎁"),
    "link": ("5305265301917549162", "🔗"),

    # purchase history
    "no_orders": ("5406683434124859552", "📭"),
    "arrow": ("5416117059207572332", "👉"),
    "back": ("5416117059207572332", "🔙"),

    # wallet
    "diamond": ("5427168083074628963", "💎"),
    "stats": ("5231200819986047254", "📊"),
    "deposit": ("5397916757333654639", "💳"),
    "withdraw": ("5402186569006210455", "💸"),

    # order details
    "order_details": ("5231012545799666522", "🔎"),

    # support
    "support_center": ("5395695537687123235", "🆘"),
    "support": ("5443038326535759644", "💬"),
    "faq": ("5282843764451195532", "📖"),
    "contact": ("5443038326535759644", "💬"),
    "announcement": ("5424818078833715060", "🔔"),
    "confirm": ("5206607081334906820", "✅"),
    "cancel": ("5210952531676504517", "❌"),
    "order": ("5406683434124859552", "🛒"),
    "edit_stock": ("5451882707875276247", "📝"),
    "delete": ("5445267414562389170", "🗑️"),
    "broadcast": ("5424818078833715060", "📢"),
    "view_products": ("5231012545799666522", "📦"),
    "users": ("5461117441612462242", "👥"),
    "question": ("5282843764451195532", "❓"),
    "quantity": ("5231200819986047254", "🔢"),
    "warning": ("5210952531676504517", "⚠️"),
    "admin": ("5427168083074628963", "👑"),
    "wallet_purse": ("5409048419211682843", "👛"),
    "receipt": ("5406683434124859552", "🧾"),
    "clipboard": ("5451882707875276247", "📋"),
    "pin": ("5305265301917549162", "📍"),
    "hourglass": ("5231200819986047254", "⏳"),
    "puzzle": ("5231012545799666522", "🧩"),
}

DIVIDER = "━━━━━━━━━━━━━━━━━━"


def tg(emoji_id, fallback="."):
    emoji_id = str(emoji_id or "").strip()
    fallback = "." if fallback is None else str(fallback)

    if not emoji_id or emoji_id.lower() == "none":
        return html_escape(fallback)

    return f'<tg-emoji emoji-id="{html_escape(emoji_id, quote=True)}">{html_escape(fallback)}</tg-emoji>'


def ce(name, fallback=None):
    emoji_data = EMOJIS.get(name)
    if not emoji_data:
        return html_escape(str(fallback or ""))

    emoji_id, default_fallback = emoji_data
    return tg(emoji_id, default_fallback if fallback is None else fallback)


def generate_order_id():
    return "ORD" + str(uuid.uuid4())[:8].upper()


def btn(text, callback_data=None, url=None, style="default", emoji_id=None):
    api_kwargs = {}

    if emoji_id:
        api_kwargs["icon_custom_emoji_id"] = str(emoji_id)

    if url:
        return InlineKeyboardButton(
            text=text,
            url=url,
            style=style,
            api_kwargs=api_kwargs
        )

    return InlineKeyboardButton(
        text=text,
        callback_data=callback_data,
        style=style,
        api_kwargs=api_kwargs
    )


def back_btn(text="Back", callback_data="main_menu", style="primary"):
    return btn(
        text,
        callback_data=callback_data,
        style=style,
        emoji_id=EMOJIS["back"][0]
    )


def build_menu(buttons, n_cols, header_buttons=None, footer_buttons=None):
    menu = [buttons[i:i + n_cols] for i in range(0, len(buttons), n_cols)]

    if header_buttons:
        menu.insert(0, header_buttons)

    if footer_buttons:
        menu.append(footer_buttons)

    return InlineKeyboardMarkup(menu)


# ─── USER KEYBOARDS ───────────────────────────────────────

def render_custom_emoji_placeholders(text):
    """
    Broadcast helper: turns {[custom_emoji_id]} into Telegram HTML custom emoji.
    Normal message text is escaped so admin can send plain text safely.
    """
    pattern = re.compile(r"\{\[(\d+)\]\}")
    source = text or ""
    rendered = []
    last_index = 0

    for match in pattern.finditer(source):
        rendered.append(html_escape(source[last_index:match.start()]))
        rendered.append(tg(match.group(1), "."))
        last_index = match.end()

    rendered.append(html_escape(source[last_index:]))
    return "".join(rendered)


def main_menu_keyboard():
    keyboard = [
        [
            btn(
                "Products",
                callback_data='products',
                style="success",
                emoji_id=EMOJIS["products"][0]
            ),
            btn(
                "Freebies",
                callback_data='freebies',
                style="success",
                emoji_id=EMOJIS["welcome_star"][0]
            )
        ],
        [
            btn(
                "Profile",
                callback_data='profile',
                style="primary",
                emoji_id=EMOJIS["profile"][0]
            ),
            btn(
                "Purchase History",
                callback_data='purchase_history',
                style="danger",
                emoji_id=EMOJIS["purchase_history"][0]
            ),
        ],
        [
            btn(
                "Wallet",
                callback_data='wallet',
                style="success",
                emoji_id=EMOJIS["wallet"][0]
            ),
            btn(
                "Support",
                callback_data='support',
                style="danger",
                emoji_id=EMOJIS["support"][0]
            ),
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

        # Format: Sticker icon + title + price$ + stock in brackets
        # Sticker icon comes from icon_custom_emoji_id, not text.
        text = f"{product_name}  {price}$  ({stock})"
        style = "success" if stock and stock > 0 else "danger"

        buttons.append(
            btn(
                text,
                callback_data=f'product_{product_id}',
                style=style,
                emoji_id=product_emoji_id or EMOJIS["products"][0]
            )
        )

    buttons.append(back_btn("Back to Main Menu", callback_data='main_menu'))
    return build_menu(buttons, n_cols=1)

def product_details_keyboard():
    buttons = [
        btn("Order Now", callback_data='order_now', style="success", emoji_id=EMOJIS["order"][0]),
        back_btn("Back to Products", callback_data='products', style="danger"),
    ]
    return build_menu(buttons, n_cols=1)


def quantity_selection_keyboard():
    buttons = [back_btn("Back to Product", callback_data='back_to_product_details', style="danger")]
    return build_menu(buttons, n_cols=1)


def payment_method_keyboard():
    buttons = [
        btn("Pay with Binance", callback_data='pay_binance', style="primary", emoji_id=EMOJIS["deposit"][0]),
        btn("Pay with Wallet", callback_data='pay_wallet', style="success", emoji_id=EMOJIS["wallet"][0]),
        back_btn("Back to Quantity", callback_data='back_to_quantity', style="danger"),
    ]
    return build_menu(buttons, n_cols=1)


def binance_payment_keyboard():
    buttons = [
        btn("I have sent the payment", callback_data='check_binance_payment', style="success", emoji_id=EMOJIS["confirm"][0]),
        btn("Cancel Order", callback_data='cancel_order', style="danger", emoji_id=EMOJIS["cancel"][0]),
    ]
    return build_menu(buttons, n_cols=1)


def wallet_payment_keyboard():
    buttons = [
        btn("Confirm & Pay", callback_data='confirm_wallet_payment', style="success", emoji_id=EMOJIS["confirm"][0]),
        btn("Cancel", callback_data='cancel_order', style="danger", emoji_id=EMOJIS["cancel"][0]),
    ]
    return build_menu(buttons, n_cols=1)


def insufficient_balance_keyboard():
    buttons = [back_btn("Back to Payment", callback_data='back_to_payment_method', style="danger")]
    return build_menu(buttons, n_cols=1)


def order_confirmed_keyboard():
    buttons = [
        btn("Order Details", callback_data='order_details', style="primary", emoji_id=EMOJIS["order_details"][0]),
        back_btn("Back to Main Menu", callback_data='main_menu'),
    ]
    return build_menu(buttons, n_cols=1)


def wallet_options_keyboard():
    buttons = [
        btn("Deposit", callback_data='deposit_wallet', style="success", emoji_id=EMOJIS["deposit"][0]),
    ]
    return build_menu(buttons, n_cols=2, footer_buttons=[back_btn("Back", callback_data='main_menu')])


def wallet_deposit_amount_keyboard():
    buttons = [back_btn("Back", callback_data='wallet', style="danger")]
    return build_menu(buttons, n_cols=1)


def deposit_wallet_keyboard():
    buttons = [
        btn("I have sent the payment", callback_data='check_deposit_payment', style="success", emoji_id=EMOJIS["confirm"][0]),
        back_btn("Back", callback_data='wallet', style="danger"),
    ]
    return build_menu(buttons, n_cols=1)


def support_keyboard():
    buttons = [
        btn("FAQ", callback_data='faq', style="primary", emoji_id=EMOJIS["faq"][0]),
        btn(
    "Contact Support",
    url="https://t.me/Bunnyhaccks",
    style="success",
    emoji_id=EMOJIS["support"][0]
),
        btn("Announcements", url='https://t.me/bunnyhackss', style="primary", emoji_id=EMOJIS["announcement"][0]),
        back_btn("Back", callback_data='main_menu', style="danger"),
    ]
    return build_menu(buttons, n_cols=1)



def product_update_purchase_keyboard(product, style="success"):
    """
    Auto announcement/update message ke liye sirf specific product ka single colored button.
    """
    if not product:
        return None

    product_id = product[0]
    product_name = product[1]
    product_emoji_id = product[9] if len(product) > 9 and product[9] else None

    keyboard = [
        [
            btn(
                f"Buy {product_name}",
                callback_data=f"product_{product_id}",
                style=style,
                emoji_id=product_emoji_id or EMOJIS["products"][0]
            )
        ]
    ]

    return InlineKeyboardMarkup(keyboard)


# ─── ADMIN KEYBOARDS ──────────────────────────────────────

def admin_main_keyboard():
    buttons = [
        btn("Add Product", callback_data='admin_add_product', style="success", emoji_id=EMOJIS["deposit"][0]),
        btn("Bulk Products", callback_data='admin_bulk_add_products', style="success", emoji_id=EMOJIS["deposit"][0]),
        btn("Add Stock/Items", callback_data='admin_add_items', style="primary", emoji_id=EMOJIS["view_products"][0]),
        btn("Edit Product Details", callback_data='admin_edit_product_details', style="primary", emoji_id=EMOJIS["view_products"][0]),
        btn("Edit Stock Details", callback_data='admin_edit_stock_details', style="primary", emoji_id=EMOJIS["edit_stock"][0]),
        btn("Edit Price", callback_data='admin_edit_price', style="primary", emoji_id=EMOJIS["wallet"][0]),
        btn("Edit Stock", callback_data='admin_edit_stock', style="primary", emoji_id=EMOJIS["edit_stock"][0]),
        btn("Add Balance", callback_data='admin_add_balance', style="success", emoji_id=EMOJIS["deposit"][0]),
        btn("Approve Withdrawal", callback_data='admin_approve_withdrawal', style="success", emoji_id=EMOJIS["confirm"][0]),
        btn("Broadcast", callback_data='admin_broadcast', style="danger", emoji_id=EMOJIS["broadcast"][0]),
        btn("Delete Product", callback_data='admin_delete_product', style="danger", emoji_id=EMOJIS["delete"][0]),
        btn("Order Details", callback_data='admin_order_details', style="primary", emoji_id=EMOJIS["order_details"][0]),
        btn("View Products", callback_data='admin_view_products', style="primary", emoji_id=EMOJIS["view_products"][0]),
        btn("All Orders", callback_data='admin_view_all_orders', style="primary", emoji_id=EMOJIS["order"][0]),
        btn("Withdrawals", callback_data='admin_withdraw_requests', style="danger", emoji_id=EMOJIS["withdraw"][0]),
        btn("Freebie Products", callback_data='admin_freebie_products', style="success", emoji_id=EMOJIS["products"][0]),
        btn("Freebie Stock", callback_data='admin_freebie_stock', style="success", emoji_id=EMOJIS["view_products"][0]),
        btn("Stats", callback_data='admin_view_stats', style="success", emoji_id=EMOJIS["stats"][0]),
    ]
    return build_menu(buttons, n_cols=2)

def freebies_keyboard(products, config_data):
    buttons = []
    
    # Add join channel button if link is provided
    if config_data[2]:
        buttons.append(btn("Join Channel", url=config_data[2], style="success", emoji_id=EMOJIS["announcement"][0]))
        
    for p in products:
        product_id = p[0]
        product_name = p[1]
        stock = p[4]
        product_emoji_id = p[9] if len(p) > 9 and p[9] else None
        
        text = f"Claim {product_name} ({stock})"
        style = "success" if stock > 0 else "danger"
        
        buttons.append(
            btn(
                text,
                callback_data=f'claim_freebie_{product_id}',
                style=style,
                emoji_id=product_emoji_id or EMOJIS["products"][0]
            )
        )
        
    buttons.append(back_btn("Back", callback_data='main_menu'))
    return build_menu(buttons, n_cols=1)

def freebies_admin_keyboard():
    buttons = [
        btn("Setup Channel", callback_data='admin_setup_freebies', style="primary", emoji_id=EMOJIS["announcement"][0]),
        btn("Manage Products", callback_data='admin_manage_freebies', style="primary", emoji_id=EMOJIS["products"][0]),
        back_btn("Back", callback_data='admin_panel_back', style="danger")
    ]
    return build_menu(buttons, n_cols=1)


def admin_back_keyboard():
    buttons = [back_btn("Back to Admin Panel", callback_data='admin_panel_back')]
    return build_menu(buttons, n_cols=1)


def admin_cancel_keyboard():
    buttons = [back_btn("Cancel", callback_data='admin_panel_back', style="danger")]
    return build_menu(buttons, n_cols=1)
