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
    "info": "5427168083074628963",         # ℹ️ / 💎
    "box": "5231012545799666522",          # 📦
    "diamond": "5427168083074628963",      # 💎
    "stats": "5231200819986047254",        # 📊
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

    # Professional product details with custom emojis
    message = (
        f"{product_icon} <b>━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━</b> {product_icon}\n\n"
        f"{product_icon} <b>✨ PRODUCT DETAILS</b> {product_icon}\n\n"
        f"{product_icon} <b>┌── Name:</b> <code>{safe(name)}</code>\n"
        f"{tg(EMOJIS['date'], '📅')} <b>├── Duration:</b> <code>{safe(duration)}</code>\n"
        f"{tg(EMOJIS['wallet'], '💰')} <b>├── Price:</b> <code>{safe(price)} USDT</code>\n"
        f"{tg(EMOJIS['box'], '📦')} <b>└── Stock:</b> <code>{safe(stock)} left</code>\n\n"
        f"{tg(EMOJIS['description'], '📖')} <b>━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━</b> {tg(EMOJIS['description'], '📖')}\n"
        f"{tg(EMOJIS['description'], '📖')} <b>📝 Description</b>\n"
        f"{tg(EMOJIS['description'], '📖')} <b>━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━</b>\n"
        f"<i>{safe(description)}</i>\n\n"
        f"{tg(EMOJIS['warning'], '⚠️')} <b>━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━</b> {tg(EMOJIS['warning'], '⚠️')}\n"
        f"{tg(EMOJIS['warning'], '⚠️')} <b>❗ Important Note</b>\n"
        f"{tg(EMOJIS['warning'], '⚠️')} <b>━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━</b>\n"
        f"<i>{safe(note)}</i>\n\n"
        f"{tg(EMOJIS['confirm'], '✅')} <b>━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━</b> {tg(EMOJIS['confirm'], '✅')}\n"
        f"{tg(EMOJIS['sticker'], '👇')} <b>Click 'Order Now' to purchase this product</b>"
    )

    return message