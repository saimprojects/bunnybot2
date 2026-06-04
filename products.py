"""
Product message formatting helpers.

This module provides functions to generate human friendly product
descriptions for Telegram.  It uses custom emojis exclusively and
supports embedding custom emoji IDs in free text fields using the
square bracket notation (e.g. ``[123456789]``).  When rendering
details the number of items sold for each product is included.
"""

import re
from html import escape as html_escape
import database


def tg(emoji_id: str, fallback: str) -> str:
    """Return a Telegram custom emoji tag.

    ``emoji_id`` must be a string.  ``fallback`` is ignored since the
    bot uses only custom emojis.  The fallback is still provided for
    completeness and to satisfy Telegram's API requirements.
    """
    return f'<tg-emoji emoji-id="{emoji_id}">{fallback}</tg-emoji>'


# Default custom emoji IDs for product metadata.  These values should
# match those configured on the bot's Telegram account.  Only custom
# emojis are used to satisfy the requirement of not using native
# emojis in the bot UI.
EMOJIS = {
    "product": "5231012545799666522",      # 📦
    "wallet": "5409048419211682843",       # 💰
    "date": "5413879192267805083",         # 📅
    "sticker": "5406745015365943482",       # 👇
    "confirm": "5206607081334906820",      # ✅
    "warning": "5210952531676504517",      # ❌
    "description": "5282843764451195532",  # 📖
}


def safe(value) -> str:
    """Escape a value for safe inclusion in HTML messages."""
    return html_escape(str(value)) if value is not None else ""


def format_with_custom_emojis(text: str) -> str:
    """Replace [emoji_id] patterns with Telegram custom emoji tags.

    Admins can embed custom emoji IDs in descriptions or broadcast
    messages using square brackets.  This helper converts such
    patterns into ``<tg-emoji>`` markup so that Telegram displays
    the custom emoji when ``parse_mode`` is ``HTML``.  If ``text``
    is falsy, returns an empty string.  A minimal fallback (a
    single space) is used inside the tag.
    """
    if not text:
        return ""

    def repl(match):
        emoji_id = match.group(1)
        return f'<tg-emoji emoji-id="{emoji_id}"> </tg-emoji>'

    return re.sub(r'\[(\d+)\]', repl, str(text))


def get_product_icon(emoji_id: str) -> str:
    """Return the custom emoji tag for a product icon."""
    if emoji_id and str(emoji_id).strip() and str(emoji_id).strip().lower() != "none":
        return tg(str(emoji_id).strip(), "📦")
    return tg(EMOJIS["product"], "📦")


def get_product_details_message(product_id: int) -> str:
    """Return a formatted HTML message describing a product.

    The message includes the name, duration, price, stock,
    number sold, description and note.  Custom emojis embedded via
    square bracket notation are converted appropriately.  If the
    product is not found a warning is returned.
    """
    product = database.get_product(product_id)
    if not product:
        return f"{tg(EMOJIS['warning'], '❌')} <b>Product not found.</b>"
    # Unpack product tuple.  Layout:
    # id,name,duration,price,stock,rating,description,features_json,note,emoji_id,is_free,free_channel
    pid = product[0]
    name = product[1]
    duration = product[2]
    price = product[3]
    stock = product[4]
    description = product[6] if len(product) > 6 else ""
    note = product[8] if len(product) > 8 else ""
    emoji_id = product[9] if len(product) > 9 else ""
    sold_count = database.get_sold_count(pid) if pid else 0
    product_icon = get_product_icon(emoji_id)
    message = (
        f"{product_icon} <b>Product Details</b>\n\n"
        f"{product_icon} <b>Name:</b> {format_with_custom_emojis(name)}\n"
        f"{tg(EMOJIS['date'], '📅')} <b>Duration:</b> {format_with_custom_emojis(duration)}\n"
        f"{tg(EMOJIS['wallet'], '💰')} <b>Price:</b> {safe(price)} USDT\n"
        f"{tg(EMOJIS['product'], '📦')} <b>Stock:</b> {safe(stock)}\n"
        f"{tg(EMOJIS['product'], '📦')} <b>Sold:</b> {safe(sold_count)}\n\n"
        f"{tg(EMOJIS['description'], '📖')} <b>Description:</b>\n"
        f"{format_with_custom_emojis(description)}\n\n"
        f"{tg(EMOJIS['warning'], '⚠️')} <b>Note:</b>\n"
        f"{format_with_custom_emojis(note)}\n\n"
        f"━━━━━━━━━━━━━━━━━━"
    )
    return message
