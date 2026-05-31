import database
import json


def tg(emoji_id, fallback):
    return f'<tg-emoji emoji-id="{emoji_id}">{fallback}</tg-emoji>'


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

    features = json.loads(features_json) if features_json else []

    features_text = (
        "\n".join([f"✓ {feature}" for feature in features])
        if features
        else "N/A"
    )

    box_emoji = tg("5231012545799666522", "📦")
    wallet_emoji = tg("5409048419211682843", "💰")
    date_emoji = tg("5413879192267805083", "📅")
    choose_emoji = tg("5406745015365943482", "🧩")

    message = (
        f"{box_emoji} <b>Product Details</b>\n\n"

        f"🟢 <b>Name:</b> {name}\n"

        f"{choose_emoji} <b>Sticker ID:</b> "
        f"<code>{emoji_id if emoji_id else 'None'}</code>\n"

        f"{date_emoji} <b>Duration:</b> {duration}\n"

        f"{wallet_emoji} <b>Price:</b> {price} USDT\n"

        f"{box_emoji} <b>Stock Available:</b> {stock}\n"

        f"⭐ <b>Rating:</b> {rating}/5\n\n"

        f"📝 <b>Description:</b>\n"
        f"{description}\n\n"

        f"✅ <b>Features:</b>\n"
        f"{features_text}\n\n"

        f"⚠️ <b>Note:</b>\n"
        f"{note}\n\n"

        f"━━━━━━━━━━━━━━━━━━"
    )

    return message