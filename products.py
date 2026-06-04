import database
from html import escape as html_escape
import utils


def tg(emoji_id, fallback):
    return f'<tg-emoji emoji-id="{emoji_id}">{fallback}</tg-emoji>'


def ce(name):
    emoji_data = utils.EMOJIS.get(name)
    if not emoji_data: return ""
    eid, fb = emoji_data
    return tg(eid, fb) if eid else fb


def safe(value):
    return html_escape(str(value)) if value is not None else ""


def get_product_icon(emoji_id):
    """
    Product ka apna saved custom emoji ID use karega.
    Agar database mein empty/None hai to default product emoji use karega.
    """
    if emoji_id and str(emoji_id).strip() and str(emoji_id).strip().lower() != "none":
        return tg(str(emoji_id).strip(), "📦")

    return ce('box')


def get_product_details_message(product_id):
    product = database.get_product(product_id)

    if not product:
        return "Product not found."

    # Current database product tuple (PostgreSQL):
    # 0 id, 1 name, 2 duration, 3 price, 4 stock,
    # 5 rating, 6 description, 7 features_json, 8 note, 9 emoji_id, 10 is_freebie
    
    pid = product[0]
    name = product[1]
    duration = product[2]
    price = product[3]
    stock = product[4]
    description = product[6]
    note = product[8]
    emoji_id = product[9]
    is_freebie = product[10] if len(product) > 10 else False

    product_icon = get_product_icon(emoji_id)

    message = (
        f"{product_icon} <b>Product Details</b>\n\n"

        f"{product_icon} <b>Name:</b> {safe(name)}\n"
        f"{ce('date')} <b>Duration:</b> {safe(duration)}\n"
        f"{ce('wallet')} <b>Price:</b> {safe(price)} USDT\n"
        f"{ce('box')} <b>Stock Available:</b> {safe(stock)}\n\n"

        f"{ce('faq')} <b>Description:</b>\n"
        f"{safe(description)}\n\n"

        f"⚠️ <b>Note:</b>\n"
        f"{safe(note)}\n\n"

        f"━━━━━━━━━━━━━━━━━━"
    )

    return message
