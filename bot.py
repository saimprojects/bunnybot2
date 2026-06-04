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
        await update.callback_query.edit_message_text(
            welcome_text,
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
        await update.message.reply_text(text, parse_mode='HTML', reply_markup=utils.main_menu_keyboard())


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
        await update.message.reply_text(text, parse_mode='HTML', reply_markup=utils.main_menu_keyboard())


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
    elif data == 'wallet':
        user = database.get_user(user_id)
        transactions = database.get_user_transactions(user_id)
        await query.edit_message_text(build_wallet_message(user, transactions), reply_markup=utils.wallet_options_keyboard(), parse_mode='HTML')
        return ConversationHandler.END
    elif data == 'support':
        await query.edit_message_text(
            (
                f"{ce('support_center')} <b>Support Center</b>\n\n"
                f"{ce('faq')} <b>FAQ</b> — Common questions\n"
                f"{ce('contact')} <b>Contact Admin</b> — Message to owner\n"
                f"{ce('announcement')} <b>Announcements</b> — Join our channel\n\n"
                f"━━━━━━━━━━━━━━━━━━\n\n"
                f"{ce('choose_option')} Choose option:"
            ),
            reply_markup=utils.support_keyboard(),
            parse_mode='HTML'
        )
        return ConversationHandler.END
    elif data == 'faq':
        await query.edit_message_text(
            "❓ *FAQ*\n\n"
            "*Q: How long does delivery take?*\n"
            "A: Delivery is instant after payment confirmation.\n\n"
            "*Q: What if my account stops working?*\n"
            "A: Contact our support with your Order ID for assistance.\n\n"
            "*Q: How to deposit?*\n"
            "A: Go to Wallet -> Deposit and follow the instructions.",
            reply_markup=utils.support_keyboard(),
            parse_mode='Markdown'
        )
        return ConversationHandler.END
    elif data == 'deposit_wallet':
        await query.edit_message_text(
            f"💰 *Deposit Funds*\n\n"
            f"Send USDT to this address:\n\n"
            f"📍 `{config.BINANCE_WALLET_ADDRESS}`\n\n"
            f"🔁 Network: {config.BINANCE_NETWORK} (USDT)\n"
            f"💵 Minimum: 10 USDT\n\n"
            f"━━━━━━━━━━━━━━━━━━\n\n"
            f"After sending, click 'I have sent the payment' and send your Transaction ID.",
            reply_markup=utils.deposit_wallet_keyboard(),
            parse_mode='Markdown'
        )
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
        await query.edit_message_text(text=text, reply_markup=utils.product_details_keyboard(), parse_mode='HTML')
        return ConversationHandler.END
    elif data == 'order_now':
        await query.edit_message_text("🔢 Please send the quantity you want to buy:", reply_markup=utils.quantity_selection_keyboard())
        return QUANTITY
    elif data == 'pay_binance':
        pid = context.user_data.get('current_product_id')
        qty = context.user_data.get('quantity')
        product = database.get_product(pid)
        total = product[3] * qty
        context.user_data['total_amount'] = total
        await query.edit_message_text(payment.get_binance_payment_details(total), reply_markup=utils.binance_payment_keyboard(), parse_mode='HTML')
        return BINANCE_ORDER_ID
    elif data == 'pay_wallet':
        pid = context.user_data.get('current_product_id')
        qty = context.user_data.get('quantity')
        product = database.get_product(pid)
        total = product[3] * qty
        context.user_data['total_amount'] = total
        await query.edit_message_text(payment.get_wallet_payment_summary(user_id, total), reply_markup=utils.wallet_payment_keyboard(), parse_mode='HTML')
        return ConversationHandler.END
    elif data == 'confirm_wallet_payment':
        pid = context.user_data.get('current_product_id')
        qty = context.user_data.get('quantity')
        total = context.user_data.get('total_amount')
        success, msg = payment.process_wallet_payment(user_id, None, pid, qty, total)
        if success:
            await deliver_product(update, context, 'Wallet')
        else:
            await query.edit_message_text(msg, reply_markup=utils.insufficient_balance_keyboard(), parse_mode='HTML')
        return ConversationHandler.END
    elif data == 'cancel_order':
        await start(update, context)
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
    elif data == 'admin_view_products':
        await query.edit_message_text(admin.get_all_products_admin(), reply_markup=utils.admin_back_keyboard(), parse_mode='Markdown')
        return ConversationHandler.END
    elif data == 'admin_view_all_orders':
        await query.edit_message_text(admin.get_all_orders_admin(), reply_markup=utils.admin_back_keyboard(), parse_mode='Markdown')
        return ConversationHandler.END
    elif data == 'admin_withdraw_requests':
        await query.edit_message_text(admin.get_withdrawal_requests_admin(), reply_markup=utils.admin_back_keyboard(), parse_mode='Markdown')
        return ConversationHandler.END
    elif data == 'admin_order_details':
        await query.edit_message_text("🔎 <b>Admin Order Details</b>\n\nSend Order ID:", reply_markup=utils.admin_cancel_keyboard(), parse_mode='HTML')
        return ADMIN_ORDER_DETAILS
    elif data == 'admin_add_product':
        await query.edit_message_text(
            "➕ <b>Add Product</b>\n\nFormat:\n`Name | Duration | Price | Description | Note | Sticker Emoji ID`",
            reply_markup=utils.admin_cancel_keyboard(),
            parse_mode='HTML'
        )
        return ADMIN_ADD_PRODUCT
    elif data == 'admin_bulk_add_products':
        await query.edit_message_text(
            "➕ <b>Bulk Add Products</b>\n\nFormat:\n`[Name | Duration | Price | Description | Note | Sticker Emoji ID] [...]`",
            reply_markup=utils.admin_cancel_keyboard(),
            parse_mode='HTML'
        )
        return ADMIN_BULK_ADD_PRODUCTS
    elif data == 'admin_add_items':
        await query.edit_message_text(
            "📦 <b>Add Stock/Items</b>\n\nFormat:\n`Product_ID[{field:value},{field:value}]`",
            reply_markup=utils.admin_cancel_keyboard(),
            parse_mode='HTML'
        )
        return ADMIN_ADD_ITEMS
    elif data == 'admin_edit_price':
        await query.edit_message_text("💰 <b>Edit Price</b>\n\nSend: `Product_ID | New_Price`", reply_markup=utils.admin_cancel_keyboard(), parse_mode='HTML')
        return ADMIN_EDIT_PRICE
    elif data == 'admin_edit_stock':
        await query.edit_message_text("📦 <b>Edit Stock</b>\n\nSend: `Product_ID | New_Stock`", reply_markup=utils.admin_cancel_keyboard(), parse_mode='HTML')
        return ADMIN_EDIT_STOCK
    elif data == 'admin_add_balance':
        await query.edit_message_text("💰 <b>Add Balance</b>\n\nSend: `User_ID | Amount`", reply_markup=utils.admin_cancel_keyboard(), parse_mode='HTML')
        return ADMIN_ADD_BALANCE
    elif data == 'admin_approve_withdrawal':
        await query.edit_message_text("💸 <b>Approve Withdrawal</b>\n\nSend Withdrawal ID:", reply_markup=utils.admin_cancel_keyboard(), parse_mode='HTML')
        return ADMIN_APPROVE_WITHDRAWAL
    elif data == 'admin_broadcast':
        await query.edit_message_text("📢 <b>Broadcast</b>\n\nSend message (supports [emoji_id]):", reply_markup=utils.admin_back_keyboard(), parse_mode='HTML')
        return ADMIN_BROADCAST
    elif data == 'admin_delete_product':
        await query.edit_message_text("❌ <b>Delete Product</b>\n\nSend Product ID:", reply_markup=utils.admin_cancel_keyboard(), parse_mode='HTML')
        return ADMIN_DELETE_PRODUCT
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


async def handle_quantity(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    try:
        qty = int(update.message.text)
        pid = context.user_data.get('current_product_id')
        product = database.get_product(pid)
        
        if qty <= 0:
            await update.message.reply_text("❌ Quantity must be greater than 0.")
            return QUANTITY
        
        if qty > product[4]:
            await update.message.reply_text(f"❌ Not enough stock. Available: {product[4]}")
            return QUANTITY
            
        context.user_data['quantity'] = qty
        await update.message.reply_text(
            f"✅ Quantity: {qty}\n\nSelect Payment Method:",
            reply_markup=utils.payment_method_keyboard()
        )
        return ConversationHandler.END
    except ValueError:
        await update.message.reply_text("❌ Please send a valid number.")
        return QUANTITY


async def handle_order_details(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    order_id = update.message.text
    order = database.get_order_by_id(order_id)
    if not order:
        await update.message.reply_text("❌ Order not found.")
        return ConversationHandler.END
    
    product = database.get_product(order[2])
    product_name = product[1] if product else "Unknown"
    text = (
        f"🔎 <b>Order Details</b>\n\n"
        f"Order ID: <code>{order[0]}</code>\n"
        f"Product: {product_name}\n"
        f"Quantity: {order[3]}\n"
        f"Amount: {order[4]} USDT\n"
        f"Status: {order[6]}\n"
        f"Date: {order[7]}\n\n"
        f"<b>Delivery Data:</b>\n"
    )
    delivery_data = json.loads(order[8])
    for i, data in enumerate(delivery_data, 1):
        text += f"\n<b>Item #{i}:</b>\n{format_item_data_for_delivery(data)}\n"
        
    await update.message.reply_text(text, parse_mode='HTML', reply_markup=utils.main_menu_keyboard())
    return ConversationHandler.END


async def handle_binance_id(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    binance_id = update.message.text
    pid = context.user_data.get('current_product_id')
    qty = context.user_data.get('quantity')
    total = context.user_data.get('total_amount')
    
    success, msg = payment.process_binance_payment(update.effective_user.id, None, pid, qty, total, binance_id)
    if success:
        await deliver_product(update, context, 'Binance')
    else:
        await update.message.reply_text(msg, parse_mode='HTML')
    return ConversationHandler.END


async def handle_admin_order_details(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    order_id = update.message.text
    order = database.get_order_by_id(order_id)
    if not order:
        await update.message.reply_text("❌ Order not found.")
        return ConversationHandler.END
    
    product = database.get_product(order[2])
    product_name = product[1] if product else "Unknown"
    text = (
        f"🔎 <b>Admin Order Details</b>\n\n"
        f"Order ID: <code>{order[0]}</code>\n"
        f"User ID: <code>{order[1]}</code>\n"
        f"Product: {product_name}\n"
        f"Quantity: {order[3]}\n"
        f"Amount: {order[4]} USDT\n"
        f"Status: {order[6]}\n"
        f"Date: {order[7]}\n"
    )
    await update.message.reply_text(text, parse_mode='HTML', reply_markup=utils.admin_main_keyboard())
    return ConversationHandler.END


async def handle_admin_add_product(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    try:
        f = update.message.text.split(' | ')
        res = admin.add_product_admin(f[0], f[1], float(f[2]), f[3], f[4], f[5])
        await update.message.reply_text(res, parse_mode='Markdown', reply_markup=utils.admin_main_keyboard())
    except:
        await update.message.reply_text("❌ Invalid format.")
    return ConversationHandler.END


async def handle_admin_add_items(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    try:
        sections = admin.parse_stock_bulk_format(update.message.text)
        res = admin.add_stock_bulk_admin(sections)
        await update.message.reply_text(res, parse_mode='Markdown', reply_markup=utils.admin_main_keyboard())
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {e}")
    return ConversationHandler.END


async def handle_admin_edit_price(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    try:
        f = update.message.text.split(' | ')
        res = admin.edit_product_price(int(f[0]), float(f[1]))
        await update.message.reply_text(res, reply_markup=utils.admin_main_keyboard())
    except:
        await update.message.reply_text("❌ Invalid format.")
    return ConversationHandler.END


async def handle_admin_edit_stock(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    try:
        f = update.message.text.split(' | ')
        res = admin.edit_product_stock(int(f[0]), int(f[1]))
        await update.message.reply_text(res, reply_markup=utils.admin_main_keyboard())
    except:
        await update.message.reply_text("❌ Invalid format.")
    return ConversationHandler.END


async def handle_admin_add_balance(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    try:
        f = update.message.text.split(' | ')
        res = admin.add_balance_admin(int(f[0]), float(f[1]))
        await update.message.reply_text(res, reply_markup=utils.admin_main_keyboard())
    except:
        await update.message.reply_text("❌ Invalid format.")
    return ConversationHandler.END


async def handle_admin_approve_withdrawal(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    try:
        res = admin.approve_withdrawal_admin(int(update.message.text))
        await update.message.reply_text(res, reply_markup=utils.admin_main_keyboard())
    except:
        await update.message.reply_text("❌ Error.")
    return ConversationHandler.END


async def handle_admin_delete_product(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    try:
        res = admin.delete_product_admin(int(update.message.text))
        await update.message.reply_text(res, reply_markup=utils.admin_main_keyboard())
    except:
        await update.message.reply_text("❌ Error.")
    return ConversationHandler.END


async def handle_admin_bulk_add_products(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    try:
        products = admin.parse_bulk_products_format(update.message.text)
        res = admin.add_bulk_products_admin(products)
        await update.message.reply_text(res, parse_mode='Markdown', reply_markup=utils.admin_main_keyboard())
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {e}")
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
    
    if update.callback_query:
        await update.callback_query.message.reply_text(text, parse_mode='HTML')
    else:
        await update.message.reply_text(text, parse_mode='HTML')
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
            CallbackQueryHandler(admin_button_handler, pattern='^admin_'),
            CallbackQueryHandler(button_handler),
            MessageHandler(filters.TEXT & ~filters.COMMAND, reply_keyboard_handler)
        ],
        states={
            QUANTITY: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_quantity)],
            ORDER_DETAILS: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_order_details)],
            BINANCE_ORDER_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_binance_id)],
            ADMIN_ORDER_DETAILS: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_admin_order_details)],
            ADMIN_ADD_PRODUCT: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_admin_add_product)],
            ADMIN_ADD_ITEMS: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_admin_add_items)],
            ADMIN_EDIT_PRICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_admin_edit_price)],
            ADMIN_EDIT_STOCK: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_admin_edit_stock)],
            ADMIN_ADD_BALANCE: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_admin_add_balance)],
            ADMIN_APPROVE_WITHDRAWAL: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_admin_approve_withdrawal)],
            ADMIN_BROADCAST: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_admin_broadcast)],
            ADMIN_DELETE_PRODUCT: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_admin_delete_product)],
            ADMIN_BULK_ADD_PRODUCTS: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_admin_bulk_add_products)],
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
