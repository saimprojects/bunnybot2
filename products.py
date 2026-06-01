import database
from html import escape as html_escape


def tg(emoji_id, fallback):
    return f'<tg-emoji emoji-id="{emoji_id}">{fallback}</tg-emoji>'


# Custom emoji IDs
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
    return html_escape(str(value)) if value is not None else ""


def get_product_icon(emoji_id):
    """
    Product ka apna saved custom emoji ID use karega.
    Agar database mein empty/None hai to default product emoji use karega.
    """
    if emoji_id and str(emoji_id).strip() and str(emoji_id).strip().lower() != "none":
        return tg(str(emoji_id).strip(), "📦")
    return tg(EMOJIS["product"], "📦")


def get_product_details_message(product_id):
    product = database.get_product(product_id)

    if not product:
        return f"{tg(EMOJIS['warning'], '❌')} <b>Product not found.</b>"

    # Database product tuple:
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

    # Clean product details with custom emojis only
    message = (
        f"{product_icon} <b>Product Details</b>\n\n"
        f"{product_icon} <b>Name:</b> {safe(name)}\n"
        f"{tg(EMOJIS['date'], '📅')} <b>Duration:</b> {safe(duration)}\n"
        f"{tg(EMOJIS['wallet'], '💰')} <b>Price:</b> {safe(price)} USDT\n"
        f"{tg(EMOJIS['product'], '📦')} <b>Stock:</b> {safe(stock)}\n\n"
        f"{tg(EMOJIS['description'], '📖')} <b>Description:</b>\n"
        f"{safe(description)}\n\n"
        f"{tg(EMOJIS['warning'], '⚠️')} <b>Note:</b>\n"
        f"{safe(note)}\n\n"
        f"━━━━━━━━━━━━━━━━━━"
    )

    return message