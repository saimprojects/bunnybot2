import database
import json
from html import escape as html_escape


def tg(emoji_id, fallback):
    return f'<tg-emoji emoji-id="{emoji_id}">{fallback}</tg-emoji>'


# Custom emoji IDs
EMOJIS = {
    "product": "5231012545799666522",      # 📦
    "wallet": "5409048419211682843",       # 💰
    "date": "5413879192267805083",         # 📅
    "sticker": "5406745015365943482",      # 🧩
    "confirm": "5206607081334906820",      # ✅
    "warning": "5210952531676504517",      # ⚠️ / ❌ style
    "stats": "5231200819986047254",        # ⭐ / stats style
    "name": "5461117441612462242",         # 👤 style fallback
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
        return "Product not found."

    (
        pid,
        name,
        duration,
        price,
        stock,
        rating,
        description,
        features_json,
        note,
        emoji_id
    ) = product if len(product) > 9 else (*product, "")

    try:
        features = json.loads(features_json) if features_json else []
    except Exception:
        features = []

    features_text = (
        "\n".join([f"{tg(EMOJIS['confirm'], '✅')} {safe(feature)}" for feature in features])
        if features
        else "N/A"
    )

    product_icon = get_product_icon(emoji_id)

    message = (
        f"{product_icon} <b>Product Details</b>\n\n"

        f"{product_icon} <b>Name:</b> {safe(name)}\n"
        f"{tg(EMOJIS['date'], '📅')} <b>Duration:</b> {safe(duration)}\n"
        f"{tg(EMOJIS['wallet'], '💰')} <b>Price:</b> {safe(price)} USDT\n"
        f"{tg(EMOJIS['product'], '📦')} <b>Stock Available:</b> {safe(stock)}\n"
        f"{tg(EMOJIS['stats'], '⭐')} <b>Rating:</b> {safe(rating)}/5\n\n"

        f"📝 <b>Description:</b>\n"
        f"{safe(description)}\n\n"

        f"{tg(EMOJIS['confirm'], '✅')} <b>Features:</b>\n"
        f"{features_text}\n\n"

        f"⚠️ <b>Note:</b>\n"
        f"{safe(note)}\n\n"

        f"━━━━━━━━━━━━━━━━━━"
    )

    return message
