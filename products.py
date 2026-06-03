import database
from html import escape as html_escape


def tg(emoji_id, fallback):
    """Return a Telegram custom emoji tag.  ``emoji_id`` must be a
    ``str`` representing the custom emoji's ID.  ``fallback`` is the
    normal emoji that will be displayed if the client doesn't support
    custom emojis.  We always provide a fallback to keep messages
    readable for all clients."""
    return f'<tg-emoji emoji-id="{emoji_id}">{fallback}</tg-emoji>'


# Custom emoji IDs for product metadata.  These values map to
# Telegram custom emojis configured for the bot.  Only custom
# emojis are used to satisfy the user's requirement that no
# non‑custom emojis appear in the bot UI.
EMOJIS = {
    "product": "5231012545799666522",      # 📦
    "wallet": "5409048419211682843",       # 💰
    "date": "5413879192267805083",         # 📅
    "sticker": "5406745015365943482",      # 👇
    "confirm": "5206607081334906820",      # ✅
    "warning": "5210952531676504517",      # ❌
    "description": "5282843764451195532",  # 📖
}


def safe(value):
    """Escape a value for safe inclusion in HTML messages.  None values
    become an empty string."""
    return html_escape(str(value)) if value is not None else ""


def format_with_custom_emojis(text: str) -> str:
    """Replace [emoji_id] patterns with Telegram custom emoji tags.

    Admins can embed custom emoji IDs in descriptions or broadcast
    messages using square brackets, e.g. ``[981239791739]``.  This
    helper converts such patterns into the appropriate
    ``<tg-emoji>`` markup so that Telegram displays the custom emoji
    when ``parse_mode`` is set to ``HTML``.  If ``text`` is falsy,
    returns an empty string.

    A minimal fallback (a space) is used inside the tag to satisfy
    Telegram API requirements for fallback text.
    """
    if not text:
        return ""
    import re

    def repl(match):
        emoji_id = match.group(1)
        return f'<tg-emoji emoji-id="{emoji_id}"> </tg-emoji>'

    return re.sub(r'\[(\d+)\]', repl, str(text))


def get_product_icon(emoji_id):
    """Return the custom emoji tag for a product.  If the product has a
    custom ``emoji_id`` set in the database it is used, otherwise
    the default product emoji is returned."""
    if emoji_id and str(emoji_id).strip() and str(emoji_id).strip().lower() != "none":
        return tg(str(emoji_id).strip(), "📦")
    return tg(EMOJIS["product"], "📦")


def get_product_details_message(product_id):
    """Return a formatted message describing the details of a single
    product.  The message includes the name, duration, price, stock
    remaining, number sold, description, and note.  All values are
    HTML escaped to prevent injection and all emojis come from the
    custom emoji set defined above."""
    product = database.get_product(product_id)

    if not product:
        return f"{tg(EMOJIS['warning'], '❌')} <b>Product not found.</b>"

    # Database product tuple layout:
    # 0 id, 1 name, 2 duration, 3 price, 4 stock,
    # 5 rating, 6 description, 7 features_json, 8 note, 9 emoji_id
    if len(product) > 9:
        pid = product[0]
        name = product[1]
        duration = product[2]
        price = product[3]
        stock = product[4]
        description = product[6]
        note = product[8]
        emoji_id = product[9]
    else:
        pid, name, duration, price, stock, description, note, emoji_id = (
            product if len(product) >= 8 else (*product, "", "", "")
        )

    product_icon = get_product_icon(emoji_id)
    # Compute how many items have been sold for this product
    sold_count = database.get_sold_count(pid) if pid else 0

    # Build the message.  Freeform fields such as name, duration,
    # description and note may include Telegram formatting and custom
    # emoji IDs expressed as [1234567890].  Use
    # ``format_with_custom_emojis`` on those fields to convert the
    # bracket notation into proper custom emoji tags.  Numeric
    # fields (price, stock, sold count) remain escaped to prevent
    # injection.
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