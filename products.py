import database
import json


def get_product_details_message(product_id):
    product = database.get_product(product_id)
    if not product:
        return "Product not found."

    (pid, name, duration, price, stock, rating, description, features_json, note, emoji_id) = (
        product if len(product) > 9 else (*product, "")
    )
    features = json.loads(features_json) if features_json else []
    features_text = "\n".join([f"✓ {f}" for f in features]) if features else "N/A"

    message = (
        f"📦 *Product Details*\n\n"
        f"🟢 *Name:* {name}\n"
        f"🧩 *Sticker ID:* `{emoji_id if emoji_id else 'None'}`\n"
        f"📅 *Duration:* {duration}\n"
        f"💰 *Price:* {price} USDT\n"
        f"📦 *Stock Available:* {stock}\n"
        f"⭐ *Rating:* {rating}/5\n\n"
        f"📝 *Description:*\n{description}\n\n"
        f"✅ *Features:*\n{features_text}\n\n"
        f"⚠️ *Note:*\n{note}\n\n"
        f"━━━━━━━━━━━━━━━━━━"
    )
    return message
