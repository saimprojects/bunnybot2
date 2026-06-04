import logging
import datetime
import json
import re
from html import escape as html_escape
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, CallbackQueryHandler,
    MessageHandler, filters, ContextTypes, ConversationHandler
)

import config
import database
import admin
import utils
import payment

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

logger = logging.getLogger(__name__)


def tg(emoji_id: str, fallback: str) -> str:
    return f'<tg-emoji emoji-id="{emoji_id}">{fallback}</tg-emoji>'


CUSTOM_EMOJIS = {
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

    # wallet
    "diamond": ("5427168083074628963", "💎"),
    "stats": ("5231200819986047254", "📊"),

    # order details
    "order_details": ("5231012545799666522", "🔎"),

    # support
    "support_center": ("5395695537687123235", "🆘"),
    "faq": ("5282843764451195532", "📖"),
    "contact": ("5443038326535759644", "💬"),
    "announcement": ("5424818078833715060", "🔔"),
    "confirm": ("5206607081334906820", "✅"),
    "cancel": ("5210952531676504517", "❌"),
    "order": ("5406683434124859552", "🛒"),
}


def ce(name: str) -> str:
    emoji_id, fallback = CUSTOM_EMOJIS.get(name, ("", ""))
    if not emoji_id:
        return fallback
    return tg(emoji_id, fallback)


def product_purchase_keyboard(product, button_style="success"):
    return utils.product_update_purchase_keyboard(product, style=button_style)


def find_recent_product_by_name(product_name):
    products_list = database.get_all_products()
    for product in products_list:
        if str(product[1]).strip().lower() == str(product_name).strip().lower():
            return product
    return products_list[0] if products_list else None


def product_update_message(title, product, lines=None):
    product_name = html_escape(str(product[1])) if product else "Unknown"
    stock = product[4] if product and len(product) > 4 else "N/A"

    text = (
        f"{ce('announcement')} <b>{html_escape(title)}</b>\n\n"
        f"{ce('box')} Product: <b>{product_name}</b>\n"
        f"{ce('box')} Available Stock: <b>{stock}</b>\n"
    )

    if lines:
        for line in lines:
            text += line + "\n"

    text += f"\n{ce('choose_option')} Click below to buy this product."
    return text


async def notify_admins(context: ContextTypes.DEFAULT_TYPE, text: str, parse_mode: str = "HTML"):
    try:
        await context.bot.send_message(
            chat_id=config.ADMIN_ID,
            text=text,
            parse_mode=parse_mode
        )
    except Exception as e:
        logger.error(f"Failed to notify admin {config.ADMIN_ID}: {e}")


async def broadcast_to_all_users(context: ContextTypes.DEFAULT_TYPE, text: str, reply_markup=None, parse_mode: str = "HTML"):
    users = database.get_all_users()
    sent = 0
    
    # Process custom emoji format [emoji_id]
    pattern = r'\[(\d+)\]'
    def replace_emoji(match):
        emoji_id = match.group(1)
        return f'<tg-emoji emoji-id="{emoji_id}">✨</tg-emoji>'
    
    formatted_text = re.sub(pattern, replace_emoji, text)
    
    for user in users:
        try:
            await context.bot.send_message(
                chat_id=user[0],
                text=formatted_text,
                reply_markup=reply_markup,
                parse_mode=parse_mode
            )
            sent += 1
        except Exception:
            pass
    return sent, len(users)


(
    QUANTITY,
    WITHDRAW_AMOUNT,
    WITHDRAW_ADDRESS,
    CONTACT_ADMIN,
    BINANCE_ORDER_ID,
    ORDER_DETAILS,
    ADMIN_ORDER_DETAILS,
    ADMIN_ADD_PRODUCT,
    ADMIN_ADD_ITEMS,
    ADMIN_EDIT_PRICE,
    ADMIN_EDIT_STOCK,
    ADMIN_ADD_BALANCE,
    ADMIN_APPROVE_WITHDRAWAL,
    ADMIN_BROADCAST,
    ADMIN_DELETE_PRODUCT,
    ADMIN_BULK_ADD_PRODUCTS,
    ADMIN_SETUP_FREEBIES,
    ADMIN_TOGGLE_FREEBIE,
) = range(18)


# ══════════════════════════════════════════════════════════
#   START
# ══════════════════════════════════════════════════════════

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user

    db_user = database.get_user(user.id)
    if not db_user:
        database.create_user(user.id, user.username)

        if context.args and context.args[0].startswith('ref_'):
            try:
                referrer_id = int(context.args[0].split('_')[1])
                if referrer_id != user.id:
                    conn = database.get_connection()
                    cursor = conn.cursor()
                    cursor.execute(
                        "UPDATE users SET referrals = referrals + 1 WHERE id = %s",
                        (referrer_id,)
                    )
                    conn.commit()
                    conn.close()
            except (IndexError, ValueError):
                pass

    first_name = html_escape(user.first_name or "there")

    welcome_text = (
        f"{ce('welcome_star')} <b>Welcome to Bunny Tools!</b> {ce('welcome_star')}\n\n"
        f"Hey <b>{first_name}</b> 👋\n\n"
        f"We offer premium digital products at the best prices with fast, secure, "
        f"and fully automated delivery.\n\n"
        f"<blockquote>"
        f"{ce('products')} <b>Products</b> — Browse & buy products\n"
        f"{ce('wallet')} <b>Wallet</b> — Deposit funds and pay faster\n"
        f"{ce('profile')} <b>Profile</b> — Balance, orders and referrals\n"
        f"{ce('support_center')} <b>Support</b> — Get help anytime"
        f"</blockquote>\n\n"
        f"{ce('choose_option')} Choose an option below:"
    )

    if update.message:
        await update.message.reply_text(
            welcome_text,
            reply_markup=utils.main_menu_keyboard(),
            parse_mode='HTML'
        )
    elif update.callback_query:
        await context.bot.send_message(
            chat_id=user.id,
            text=welcome_text,
            reply_markup=utils.main_menu_keyboard(),
            parse_mode='HTML'
        )


# ══════════════════════════════════════════════════════════
#   USER MENU HELPERS
# ══════════════════════════════════════════════════════════

async def show_profile(update: Update, context: ContextTypes.DEFAULT_TYPE, edit=False):
    user_id = update.effective_user.id
    user = database.get_user(user_id)

    if not user:
        text = "Profile not found."
    else:
        bot_username = (await context.bot.get_me()).username
        username = html_escape(user[1] if user[1] else "Unknown")
        joined = html_escape(str(user[2]))

        text = (
            f"{ce('profile')} <b>My Profile</b>\n\n"
            f"{ce('id')} ID: <code>{user[0]}</code>\n"
            f"{ce('username')} Username: @{username}\n"
            f"{ce('date')} Joined: {joined}\n\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"{ce('wallet')} Wallet Balance: {user[3]} USDT\n"
            f"{ce('box')} Total Orders: {user[4]}\n"
            f"👥 Referrals: {user[5]}\n"
            f"{ce('gift')} Referral Earnings: {user[6]} USDT\n"
            f"━━━━━━━━━━━━━━━━━━\n\n"
            f"{ce('link')} <b>Your Referral Link:</b>\n"
            f"<code>t.me/{html_escape(bot_username)}?start=ref_{user[0]}</code>\n\n"
            f"👥 <b>Refer & Earn:</b> 10% commission"
        )

    if edit and update.callback_query:
        await update.callback_query.edit_message_text(
            text,
            reply_markup=utils.main_menu_keyboard(),
            parse_mode='HTML'
        )
    else:
        await update.message.reply_text(text, parse_mode='HTML')


async def show_purchase_history(update: Update, context: ContextTypes.DEFAULT_TYPE, edit=False):
    user_id = update.effective_user.id
    orders = database.get_user_orders(user_id)

    if not orders:
        text = (
            f"{ce('no_orders')} <b>No Orders Yet</b>\n\n"
            "You haven't made any purchases yet.\n\n"
            f"{ce('arrow')} Go to <b>Products</b> to buy something."
        )
    else:
        text = f"{ce('order_details')} <b>Purchase History</b>\n\n"
        for order in orders:
            product = database.get_product(order[2])
            product_name = html_escape(product[1] if product else "Unknown")
            text += (
                f"━━━━━━━━━━━━━━━━━━\n"
                f"<b>Order #{html_escape(str(order[0]))}</b>\n"
                f"{product_name}\n"
                f"Qty: {order[3]} | {order[4]} USDT | {html_escape(str(order[6]))}\n"
            )
        text += "━━━━━━━━━━━━━━━━━━"

    if edit and update.callback_query:
        await update.callback_query.edit_message_text(
            text,
            reply_markup=utils.main_menu_keyboard(),
            parse_mode='HTML'
        )
    else:
        await update.message.reply_text(text, parse_mode='HTML')


def build_wallet_message(user, transactions):
    msg = (
        f"{ce('wallet')} <b>My Wallet</b>\n\n"
        f"{ce('diamond')} Balance: <b>{user[3]} USDT</b>\n\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"{ce('stats')} <b>Recent Transactions:</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
    )

    if transactions:
        for tx in transactions[:5]:
            sign = "+" if tx[3] > 0 else ""
            msg += f"{sign}{tx[3]} USDT | {html_escape(str(tx[2]))} | {html_escape(str(tx[4]).split(' ')[0])}\n"
    else:
        msg += "No recent transactions.\n"

    msg += f"━━━━━━━━━━━━━━━━━━\n\n{ce('choose_option')} <b>Options:</b>"
    return msg


# ══════════════════════════════════════════════════════════
#   USER HANDLERS
# ══════════════════════════════════════════════════════════

async def reply_keyboard_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = update.message.text
    user_id = update.effective_user.id

    if text == "🛍️ Products":
        products_list = database.get_all_products()
        if not products_list:
            await update.message.reply_text("❌ No products available.")
            return
        await update.message.reply_text("📦 *All Products*:", reply_markup=utils.products_list_keyboard(products_list), parse_mode='Markdown')
    elif text == "👤 Profile":
        await show_profile(update, context)
    elif text == "📜 Purchase History":
        await show_purchase_history(update, context)
    elif text == "💰 Wallet":
        user = database.get_user(user_id)
        transactions = database.get_user_transactions(user_id)
        await update.message.reply_text(build_wallet_message(user, transactions), reply_markup=utils.wallet_options_keyboard(), parse_mode='HTML')


async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    data = query.data
    user_id = update.effective_user.id

    if data == 'main_menu':
        await start(update, context)
        return ConversationHandler.END
    elif data == 'products':
        products_list = database.get_all_products()
        await query.edit_message_text("📦 *All Products*:", reply_markup=utils.products_list_keyboard(products_list), parse_mode='Markdown')
        return ConversationHandler.END
    elif data == 'profile':
        await show_profile(update, context, edit=True)
        return ConversationHandler.END
    elif data == 'purchase_history':
        await show_purchase_history(update, context, edit=True)
        return ConversationHandler.END
    elif data == 'order_details':
        await context.bot.send_message(chat_id=user_id, text=f"{ce('order_details')} <b>Order Details</b>\n\nPlease send Order ID:", parse_mode='HTML')
        return ORDER_DETAILS
    elif data == 'freebies':
        config_data = database.get_freebies_config()
        if not config_data[3]:
            await query.edit_message_text("🎁 Freebies disabled.", reply_markup=utils.main_menu_keyboard())
            return ConversationHandler.END
        freebie_products = database.get_freebie_products()
        await query.edit_message_text("🎁 *Freebies Section*", reply_markup=utils.freebies_keyboard(freebie_products, config_data), parse_mode='Markdown')
        return ConversationHandler.END
    elif data.startswith('claim_freebie_'):
        product_id = int(data.split('_')[2])
        config_data = database.get_freebies_config()
        try:
            member = await context.bot.get_chat_member(chat_id=config_data[1], user_id=user_id)
            if member.status in ['left', 'kicked']:
                await query.answer("❌ Join our channel first!", show_alert=True)
                return ConversationHandler.END
        except:
            await query.answer("❌ Error checking channel.", show_alert=True)
            return ConversationHandler.END
        if database.has_user_received_freebie(user_id, product_id):
            await query.answer("❌ Already claimed!", show_alert=True)
            return ConversationHandler.END
        context.user_data['current_product_id'] = product_id
        context.user_data['quantity'] = 1
        context.user_data['total_amount'] = 0
        await deliver_product(update, context, 'Freebie')
        return ConversationHandler.END
    elif data.startswith('product_'):
        pid = int(data.split('_')[1])
        product = database.get_product(pid)
        context.user_data['current_product_id'] = pid
        text = f"🛍️ <b>{html_escape(product[1])}</b>\n\nPrice: <b>{product[3]} USDT</b>\nStock: <b>{product[4]}</b>\n\nDescription:\n{product[6]}\n\nNote: {product[8]}"
        await context.bot.send_message(chat_id=user_id, text=text, reply_markup=utils.product_details_keyboard(), parse_mode='HTML')
        return ConversationHandler.END
    elif data == 'order_now':
        return QUANTITY
    elif data == 'pay_binance':
        return ConversationHandler.END
    elif data == 'pay_wallet':
        return ConversationHandler.END
    return ConversationHandler.END


# ══════════════════════════════════════════════════════════
#   ADMIN HANDLERS
# ══════════════════════════════════════════════════════════

async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not admin.is_admin(update.effective_user.id): return
    await update.message.reply_text("👑 <b>Admin Panel</b>", reply_markup=utils.admin_main_keyboard(), parse_mode='HTML')


async def admin_button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    if not admin.is_admin(update.effective_user.id): return ConversationHandler.END
    await query.answer()
    data = query.data
    if data == 'admin_panel_back':
        await query.edit_message_text("👑 <b>Admin Panel</b>", reply_markup=utils.admin_main_keyboard(), parse_mode='HTML')
        return ConversationHandler.END
    elif data == 'admin_view_stats':
        await query.edit_message_text(admin.get_stats_admin(), reply_markup=utils.admin_back_keyboard(), parse_mode='Markdown')
        return ConversationHandler.END
    elif data == 'admin_broadcast':
        await query.edit_message_text("📢 <b>Broadcast</b>\n\nSend message (supports [emoji_id]):", reply_markup=utils.admin_back_keyboard(), parse_mode='HTML')
        return ADMIN_BROADCAST
    elif data == 'admin_freebies_settings':
        await query.edit_message_text(admin.get_freebies_settings_admin(), reply_markup=utils.admin_back_keyboard(), parse_mode='Markdown')
        return ADMIN_SETUP_FREEBIES
    elif data == 'admin_freebie_products':
        await query.edit_message_text(admin.get_freebie_products_admin(), reply_markup=utils.admin_back_keyboard(), parse_mode='Markdown')
        return ADMIN_TOGGLE_FREEBIE
    return ConversationHandler.END


async def handle_admin_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    sent, total = await broadcast_to_all_users(context, update.message.text)
    await update.message.reply_text(f"✅ Broadcast sent to {sent}/{total} users.", reply_markup=utils.admin_main_keyboard())
    return ConversationHandler.END


async def handle_admin_setup_freebies(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    try:
        data = update.message.text.split(' | ')
        database.update_freebies_config(int(data[1]), data[2], data[3].lower() == 'enable')
        await update.message.reply_text("✅ Updated!", reply_markup=utils.admin_main_keyboard())
    except:
        await update.message.reply_text("❌ Error.")
    return ConversationHandler.END


async def handle_admin_toggle_freebie(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    try:
        pid = int(update.message.text.split(' | ')[1])
        product = database.get_product(pid)
        database.toggle_product_freebie(pid, not product[10])
        await update.message.reply_text("✅ Toggled!", reply_markup=utils.admin_main_keyboard())
    except:
        await update.message.reply_text("❌ Error.")
    return ConversationHandler.END


# ══════════════════════════════════════════════════════════
#   DELIVERY & UTILS
# ══════════════════════════════════════════════════════════

def format_item_data_for_delivery(item_data):
    lines = []
    for k, v in item_data.items():
        lines.append(f"{k.replace('_',' ').title()}: <code>{v}</code>")
    return "\n".join(lines)


async def deliver_product(update: Update, context: ContextTypes.DEFAULT_TYPE, method: str):
    user_id = update.effective_user.id
    pid = context.user_data.get('current_product_id')
    qty = context.user_data.get('quantity')
    items = database.get_unsold_items(pid, qty)
    delivery_data = [item['data'] for item in items]
    order_id = utils.generate_order_id()
    database.create_order(order_id, user_id, pid, qty, context.user_data.get('total_amount'), method, 'Confirmed', delivery_data)
    database.mark_items_as_sold(pid, [item['id'] for item in items])
    database.update_product_stock(pid, -qty)
    product = database.get_product(pid)
    text = f"✅ <b>Delivery Successful!</b>\n\nOrder ID: <code>{order_id}</code>\n\n"
    for i, data in enumerate(delivery_data, 1):
        text += f"<b>Item #{i}:</b>\n{format_item_data_for_delivery(data)}\n\n"
    await context.bot.send_message(chat_id=user_id, text=text, parse_mode='HTML')
    await start(update, context)


# ══════════════════════════════════════════════════════════
#   MAIN
# ══════════════════════════════════════════════════════════

def main():
    database.init_db()
    app = ApplicationBuilder().token(config.TOKEN).build()
    
    conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler('start', start),
            CallbackQueryHandler(button_handler),
            CallbackQueryHandler(admin_button_handler),
            MessageHandler(filters.TEXT & ~filters.COMMAND, reply_keyboard_handler)
        ],
        states={
            QUANTITY: [MessageHandler(filters.TEXT & ~filters.COMMAND, lambda u, c: ConversationHandler.END)], # Placeholder
            ADMIN_BROADCAST: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_admin_broadcast)],
            ADMIN_SETUP_FREEBIES: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_admin_setup_freebies)],
            ADMIN_TOGGLE_FREEBIE: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_admin_toggle_freebie)],
        },
        fallbacks=[CommandHandler('start', start)],
    )
    
    app.add_handler(CommandHandler('admin', admin_panel))
    app.add_handler(conv_handler)
    
    print("Bot started...")
    app.run_polling()

if __name__ == '__main__':
    main()
