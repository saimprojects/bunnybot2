import logging
import datetime
import json
from telegram import Update, InlineKeyboardButton
from telegram.ext import (
    ApplicationBuilder, CommandHandler, CallbackQueryHandler,
    MessageHandler, filters, ContextTypes, ConversationHandler
)

import config
import database
import products
import payment
import admin
import utils


logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

logger = logging.getLogger(__name__)



def ce(name, fallback=""):
    """Return a readable fallback emoji. Button custom emoji IDs are applied in utils.py."""
    return fallback


async def notify_admins(context: ContextTypes.DEFAULT_TYPE, text: str, parse_mode: str = "Markdown"):
    try:
        await context.bot.send_message(
            chat_id=config.ADMIN_ID,
            text=text,
            parse_mode=parse_mode
        )
    except Exception as e:
        logger.error(f"Failed to notify admin {config.ADMIN_ID}: {e}")


async def broadcast_to_all_users(context: ContextTypes.DEFAULT_TYPE, text: str, reply_markup=None, parse_mode: str = "Markdown"):
    users = database.get_all_users()
    sent = 0
    for user in users:
        try:
            await context.bot.send_message(
                chat_id=user[0],
                text=text,
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
) = range(15)


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
                    conn = database.sqlite3.connect(database.DATABASE_NAME)
                    cursor = conn.cursor()
                    cursor.execute(
                        "UPDATE users SET referrals = referrals + 1 WHERE id = ?",
                        (referrer_id,)
                    )
                    conn.commit()
                    conn.close()

            except (IndexError, ValueError):
                pass

    welcome_text = (
        f"{ce('welcome_star', '✨')} *Bunny Tools* {ce('welcome_star', '✨')}\n\n"
        f"Welcome! Choose an option below {ce('choose_option', '👇')}"
    )

    if update.message:
        await update.message.reply_text(
            welcome_text,
            reply_markup=utils.main_menu_keyboard(),
            parse_mode='Markdown'
        )

    elif update.callback_query:
        await update.callback_query.edit_message_text(
            welcome_text,
            reply_markup=utils.main_menu_keyboard(),
            parse_mode='Markdown'
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
        text = (
            f"{ce('profile_text', '👤')} *My Profile*\n\n"
            f"{ce('id', '🆔')} ID: `{user[0]}`\n"
            f"{ce('username', '📛')} Username: @{user[1] if user[1] else 'Unknown'}\n"
            f"{ce('date', '📅')} Joined: {user[2]}\n\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"{ce('wallet', '💰')} Wallet Balance: {user[3]} USDT\n"
            f"{ce('view_products', '📦')} Total Orders: {user[4]}\n"
            f"👥 Referrals: {user[5]}\n"
            f"{ce('gift', '🎁')} Referral Earnings: {user[6]} USDT\n"
            f"━━━━━━━━━━━━━━━━━━\n\n"
            f"{ce('link', '🔗')} *Your Referral Link:*\n"
            f"`t.me/{bot_username}?start=ref_{user[0]}`\n\n"
            f"👥 *Refer & Earn:* 10% commission"
        )

    if edit and update.callback_query:
        await update.callback_query.edit_message_text(
            text,
            reply_markup=utils.main_menu_keyboard(),
            parse_mode='Markdown'
        )
    else:
        await update.message.reply_text(text, parse_mode='Markdown')


async def show_purchase_history(update: Update, context: ContextTypes.DEFAULT_TYPE, edit=False):
    user_id = update.effective_user.id
    orders = database.get_user_orders(user_id)

    if not orders:
        text = (
            "📭 *No Orders Yet*\n\n"
            "You haven't made any purchases yet.\n\n"
            f"{ce('back', '👉')} Go to *Products* to buy something."
        )
    else:
        text = "📜 *Purchase History*\n\n"

        for order in orders:
            product = database.get_product(order[2])
            product_name = product[1] if product else "Unknown"

            text += (
                f"━━━━━━━━━━━━━━━━━━\n"
                f"*Order #{order[0]}*\n"
                f"{product_name}\n"
                f"Qty: {order[3]} | {order[4]} USDT | ✅ {order[6]}\n"
            )

        text += "━━━━━━━━━━━━━━━━━━"

    if edit and update.callback_query:
        await update.callback_query.edit_message_text(
            text,
            reply_markup=utils.main_menu_keyboard(),
            parse_mode='Markdown'
        )
    else:
        await update.message.reply_text(text, parse_mode='Markdown')


# ══════════════════════════════════════════════════════════
#   REPLY TEXT HANDLER
# ══════════════════════════════════════════════════════════

async def reply_keyboard_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = update.message.text
    user_id = update.effective_user.id

    if text == "🛍️ Products":
        products_list = database.get_all_products()

        if not products_list:
            await update.message.reply_text(
                "❌ No products available right now.",
                reply_markup=utils.main_menu_keyboard()
            )
            return

        await update.message.reply_text(
            "📦 *All Products* — choose one:",
            reply_markup=utils.products_list_keyboard(products_list),
            parse_mode='Markdown'
        )

    elif text == "👤 Profile":
        await show_profile(update, context)

    elif text == "📜 Purchase History":
        await show_purchase_history(update, context)

    elif text == "🔎 Order Details":
        await update.message.reply_text(
            f"{ce('view_products', '🔎')} *Order Details*\n\nPlease send your Order ID:",
            parse_mode='Markdown'
        )
        context.user_data['waiting_for_order_details'] = True

    elif text == "💰 Wallet":
        user = database.get_user(user_id)
        transactions = database.get_user_transactions(user_id)

        msg = (
            f"{ce('wallet', '💰')} *My Wallet*\n\n"
            f"{ce('id', '💎')} Balance: *{user[3]} USDT*\n\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"{ce('stats', '📊')} *Recent Transactions:*\n"
            f"━━━━━━━━━━━━━━━━━━\n"
        )

        if transactions:
            for tx in transactions[:5]:
                sign = "+" if tx[3] > 0 else ""
                msg += f"{sign}{tx[3]} USDT | {tx[2]} | {tx[4].split(' ')[0]}\n"
        else:
            msg += "No recent transactions.\n"

        msg += f"━━━━━━━━━━━━━━━━━━\n\n{ce('choose_option', '👇')} *Options:*"

        await update.message.reply_text(
            msg,
            reply_markup=utils.wallet_options_keyboard(),
            parse_mode='Markdown'
        )

    elif text == "🆘 Support":
        msg = (
            f"{ce('announcement', '🆘')} *Support Center*\n\n"
            f"{ce('faq', '📖')} *FAQ* — Common questions\n"
            f"{ce('support', '💬')} *Contact Admin* — Message to owner\n"
            f"{ce('broadcast', '🔔')} *Announcements* — Join our channel\n\n"
            f"━━━━━━━━━━━━━━━━━━\n\n"
            f"{ce('choose_option', '👇')} Choose option:"
        )

        await update.message.reply_text(
            msg,
            reply_markup=utils.support_keyboard(),
            parse_mode='Markdown'
        )


# ══════════════════════════════════════════════════════════
#   USER INLINE BUTTON HANDLER
# ══════════════════════════════════════════════════════════

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

        if not products_list:
            await query.edit_message_text(
                "❌ No products available right now.",
                reply_markup=utils.main_menu_keyboard()
            )
            return ConversationHandler.END

        await query.edit_message_text(
            "📦 *All Products* — choose one:",
            reply_markup=utils.products_list_keyboard(products_list),
            parse_mode='Markdown'
        )
        return ConversationHandler.END

    elif data == 'profile':
        await show_profile(update, context, edit=True)
        return ConversationHandler.END

    elif data == 'purchase_history':
        await show_purchase_history(update, context, edit=True)
        return ConversationHandler.END

    elif data == 'order_details':
        await query.edit_message_text(
            f"{ce('view_products', '🔎')} *Order Details*\n\nPlease send your Order ID:",
            reply_markup=utils.main_menu_keyboard(),
            parse_mode='Markdown'
        )
        return ORDER_DETAILS

    elif data.startswith('product_'):
        product_id = int(data.split('_')[1])
        context.user_data['current_product_id'] = product_id

        details_msg = products.get_product_details_message(product_id)

        await query.edit_message_text(
            details_msg,
            reply_markup=utils.product_details_keyboard(),
            parse_mode='Markdown'
        )
        return ConversationHandler.END

    elif data == 'order_now':
        product_id = context.user_data.get('current_product_id')

        if not product_id:
            await query.edit_message_text(
                "❌ Product not selected.",
                reply_markup=utils.main_menu_keyboard()
            )
            return ConversationHandler.END

        product = database.get_product(product_id)

        if not product or product[4] <= 0:
            await query.edit_message_text(
                "❌ This product is out of stock.",
                reply_markup=utils.products_list_keyboard(database.get_all_products())
            )
            return ConversationHandler.END

        text = (
            f"🛍️ *{product[1]}*\n"
            f"💰 Price per item: {product[3]} USDT\n"
            f"📦 Available: {product[4]}\n\n"
            f"━━━━━━━━━━━━━━━━━━\n\n"
            f"*How many would you like to buy?*\n"
            f"_(Enter a number between 1 and {product[4]})_"
        )

        await query.edit_message_text(
            text,
            reply_markup=utils.quantity_selection_keyboard(),
            parse_mode='Markdown'
        )
        return QUANTITY

    elif data == 'back_to_product_details':
        product_id = context.user_data.get('current_product_id')

        if product_id:
            await query.edit_message_text(
                products.get_product_details_message(product_id),
                reply_markup=utils.product_details_keyboard(),
                parse_mode='Markdown'
            )
        else:
            await start(update, context)

        return ConversationHandler.END

    elif data == 'back_to_quantity':
        product_id = context.user_data.get('current_product_id')
        product = database.get_product(product_id)

        text = (
            f"🛍️ *{product[1]}*\n"
            f"💰 Price per item: {product[3]} USDT\n"
            f"📦 Available: {product[4]}\n\n"
            f"━━━━━━━━━━━━━━━━━━\n\n"
            f"*How many would you like to buy?*\n"
            f"_(Enter a number between 1 and {product[4]})_"
        )

        await query.edit_message_text(
            text,
            reply_markup=utils.quantity_selection_keyboard(),
            parse_mode='Markdown'
        )
        return QUANTITY

    elif data == 'pay_binance':
        total_amount = context.user_data.get('total_amount')
        context.user_data['payment_method'] = 'Binance'

        await query.edit_message_text(
            payment.get_binance_payment_details(total_amount),
            reply_markup=utils.binance_payment_keyboard(),
            parse_mode='Markdown'
        )
        return ConversationHandler.END

    elif data == 'pay_wallet':
        total_amount = context.user_data.get('total_amount')
        context.user_data['payment_method'] = 'Wallet'

        text = payment.get_wallet_payment_summary(user_id, total_amount)
        user = database.get_user(user_id)

        if user and user[3] >= total_amount:
            reply_markup = utils.wallet_payment_keyboard()
        else:
            text += "\n\n👉 Please deposit first using *Wallet → Deposit*\n👉 Or select *Pay with Binance*"
            reply_markup = utils.insufficient_balance_keyboard()

        await query.edit_message_text(
            text,
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
        return ConversationHandler.END

    elif data == 'back_to_payment_method':
        product_id = context.user_data.get('current_product_id')
        quantity = context.user_data.get('quantity')
        total_amount = context.user_data.get('total_amount')
        product = database.get_product(product_id)

        text = (
            f"✅ *Order Summary*\n\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"📦 Product: {product[1]}\n"
            f"📅 Duration: {product[2]}\n"
            f"💰 Price/item: {product[3]} USDT\n"
            f"🔢 Quantity: {quantity}\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"💵 *Total: {total_amount} USDT*\n"
            f"━━━━━━━━━━━━━━━━━━\n\n"
            f"*Select Payment Method:*"
        )

        await query.edit_message_text(
            text,
            reply_markup=utils.payment_method_keyboard(),
            parse_mode='Markdown'
        )
        return ConversationHandler.END

    elif data == 'cancel_order':
        await query.edit_message_text(
            "❌ Order cancelled.",
            reply_markup=utils.main_menu_keyboard()
        )
        return ConversationHandler.END

    elif data == 'check_binance_payment':
        await query.edit_message_text("⏳ Checking payment... Please wait.")

        success, msg = payment.process_binance_payment(
            user_id,
            utils.generate_order_id(),
            context.user_data.get('current_product_id'),
            context.user_data.get('quantity'),
            context.user_data.get('total_amount')
        )

        if success:
            await deliver_product(update, context, 'Binance')
        else:
            await query.edit_message_text(
                msg,
                reply_markup=utils.payment_method_keyboard()
            )

        return ConversationHandler.END

    elif data == 'confirm_wallet_payment':
        success, msg = payment.process_wallet_payment(
            user_id,
            utils.generate_order_id(),
            context.user_data.get('current_product_id'),
            context.user_data.get('quantity'),
            context.user_data.get('total_amount')
        )

        if success:
            await deliver_product(update, context, 'Wallet')
        else:
            await query.edit_message_text(
                msg,
                reply_markup=utils.payment_method_keyboard(),
                parse_mode='Markdown'
            )

        return ConversationHandler.END

    elif data == 'wallet':
        user = database.get_user(user_id)
        transactions = database.get_user_transactions(user_id)

        text = (
            f"{ce('wallet', '💰')} *My Wallet*\n\n"
            f"{ce('id', '💎')} Balance: *{user[3]} USDT*\n\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"{ce('stats', '📊')} *Recent Transactions:*\n"
            f"━━━━━━━━━━━━━━━━━━\n"
        )

        if transactions:
            for tx in transactions[:5]:
                sign = "+" if tx[3] > 0 else ""
                text += f"{sign}{tx[3]} USDT | {tx[2]} | {tx[4].split(' ')[0]}\n"
        else:
            text += "No recent transactions.\n"

        text += f"━━━━━━━━━━━━━━━━━━\n\n{ce('choose_option', '👇')} *Options:*"

        await query.edit_message_text(
            text,
            reply_markup=utils.wallet_options_keyboard(),
            parse_mode='Markdown'
        )
        return ConversationHandler.END

    elif data == 'deposit_wallet':
        text = (
            f"💰 *Deposit Funds*\n\n"
            f"Send USDT to this address:\n\n"
            f"📍 `{config.BINANCE_WALLET_ADDRESS}`\n\n"
            f"🔁 Network: {config.BINANCE_NETWORK} \\(USDT\\)\n"
            f"💵 Minimum: 10 USDT\n\n"
            f"━━━━━━━━━━━━━━━━━━"
        )

        await query.edit_message_text(
            text,
            reply_markup=utils.deposit_wallet_keyboard(),
            parse_mode='Markdown'
        )
        return ConversationHandler.END

    elif data == 'check_deposit_payment':
        await query.edit_message_text(
            "✅ Deposit request sent to admin.\nBalance will be updated once confirmed.",
            reply_markup=utils.wallet_options_keyboard()
        )

        await notify_admins(
            context,
            f"⚠️ User `{user_id}` claims deposit.\nUse: `/addbalance {user_id} <amount>`",
            parse_mode='Markdown'
        )
        return ConversationHandler.END

    elif data == 'withdraw_wallet':
        user = database.get_user(user_id)

        await query.edit_message_text(
            f"💸 *Withdraw Funds*\n\n"
            f"Your Balance: {user[3]} USDT\n"
            f"Minimum: 20 USDT | Fee: 1 USDT\n\n"
            f"*Enter amount to withdraw:*",
            reply_markup=utils.wallet_options_keyboard(),
            parse_mode='Markdown'
        )
        return WITHDRAW_AMOUNT

    elif data == 'support':
        await query.edit_message_text(
            f"{ce('announcement', '🆘')} *Support Center*\n\n"
            f"{ce('faq', '📖')} *FAQ* — Common questions\n"
            f"{ce('support', '💬')} *Contact Admin* — Message to owner\n"
            f"{ce('broadcast', '🔔')} *Announcements* — Join our channel\n\n"
            "━━━━━━━━━━━━━━━━━━\n\n"
            f"{ce('choose_option', '👇')} Choose option:",
            reply_markup=utils.support_keyboard(),
            parse_mode='Markdown'
        )
        return ConversationHandler.END

    elif data == 'faq':
        await query.edit_message_text(
            "❓ *FAQ*\n\n"
            "*Q: How long does delivery take?*\n"
            "A: Delivery is instant after payment confirmation.\n\n"
            "*Q: What if my account stops working?*\n"
            "A: Contact admin with your Order ID for replacement within warranty.\n\n"
            "*Q: Can I share the account?*\n"
            "A: No, sharing violates our policy.",
            reply_markup=utils.support_keyboard(),
            parse_mode='Markdown'
        )
        return ConversationHandler.END

    elif data == 'contact_admin':
        await query.edit_message_text(
            "✍️ Please type your message for the admin below:",
            reply_markup=utils.support_keyboard()
        )
        return CONTACT_ADMIN

    return ConversationHandler.END


# ══════════════════════════════════════════════════════════
#   USER CONVERSATION HANDLERS
# ══════════════════════════════════════════════════════════

async def handle_quantity(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    try:
        quantity = int(update.message.text)
        product_id = context.user_data.get('current_product_id')
        product = database.get_product(product_id)

        if not product:
            await update.message.reply_text("❌ Product not found.")
            return ConversationHandler.END

        if quantity < 1 or quantity > product[4]:
            await update.message.reply_text(
                f"⚠️ Enter a number between 1 and {product[4]}.",
                reply_markup=utils.quantity_selection_keyboard()
            )
            return QUANTITY

        total_amount = round(quantity * product[3], 4)

        context.user_data['quantity'] = quantity
        context.user_data['total_amount'] = total_amount

        await update.message.reply_text(
            f"✅ *Order Summary*\n\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"📦 Product: {product[1]}\n"
            f"📅 Duration: {product[2]}\n"
            f"💰 Price/item: {product[3]} USDT\n"
            f"🔢 Quantity: {quantity}\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"💵 *Total: {total_amount} USDT*\n"
            f"━━━━━━━━━━━━━━━━━━\n\n"
            f"*Select Payment Method:*",
            reply_markup=utils.payment_method_keyboard(),
            parse_mode='Markdown'
        )
        return ConversationHandler.END

    except ValueError:
        await update.message.reply_text(
            "⚠️ Please enter a valid number.",
            reply_markup=utils.quantity_selection_keyboard()
        )
        return QUANTITY


async def handle_withdraw_amount(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    try:
        amount = float(update.message.text)
        user_id = update.effective_user.id
        user = database.get_user(user_id)

        if amount < 20:
            await update.message.reply_text("⚠️ Minimum is 20 USDT. Enter again or /cancel:")
            return WITHDRAW_AMOUNT

        if amount > user[3]:
            await update.message.reply_text(
                f"⚠️ Insufficient balance: {user[3]} USDT. Enter again or /cancel:"
            )
            return WITHDRAW_AMOUNT

        context.user_data['withdraw_amount'] = amount

        await update.message.reply_text("📍 Enter your USDT \\(BEP\\-20\\) wallet address:", parse_mode='MarkdownV2')
        return WITHDRAW_ADDRESS

    except ValueError:
        await update.message.reply_text("⚠️ Please enter a valid number.")
        return WITHDRAW_AMOUNT


async def handle_withdraw_address(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    address = update.message.text
    amount = context.user_data.get('withdraw_amount')
    user_id = update.effective_user.id

    database.update_user_wallet(user_id, -amount)
    database.add_transaction(user_id, "Withdrawal Request", -amount)
    database.create_withdrawal_request(user_id, amount, address)

    await update.message.reply_text(
        f"✅ Withdrawal of {amount} USDT submitted. Admin will process it soon.",
        reply_markup=utils.main_menu_keyboard()
    )

    await notify_admins(
        context,
        (
            f"💸 *New Withdrawal*\n\n"
            f"User: `{user_id}`\n"
            f"Amount: {amount} USDT\n"
            f"Address: `{address}`"
        ),
        parse_mode='Markdown'
    )

    return ConversationHandler.END


async def handle_contact_admin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    msg_text = update.message.text
    user_id = update.effective_user.id
    username = update.effective_user.username or "Unknown"

    await notify_admins(
        context,
        (
            f"📩 *Message from User*\n\n"
            f"ID: `{user_id}`\n"
            f"Username: @{username}\n\n"
            f"{msg_text}"
        ),
        parse_mode='Markdown'
    )

    await update.message.reply_text(
        "✅ Message sent to admin.",
        reply_markup=utils.main_menu_keyboard()
    )

    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text(
        "❌ Operation cancelled.",
        reply_markup=utils.main_menu_keyboard()
    )
    return ConversationHandler.END


# ══════════════════════════════════════════════════════════
#   PRODUCT DELIVERY
# ══════════════════════════════════════════════════════════

def format_item_data_for_delivery(item_data):
    lines = []

    for key, value in item_data.items():
        label = key.replace("_", " ").title()
        lines.append(f"{label}: `{value}`")

    return "\n".join(lines)


def build_order_details_message(order, is_admin=False):
    """
    orders table columns:
    0 id, 1 user_id, 2 product_id, 3 quantity, 4 total_amount,
    5 payment_method, 6 status, 7 order_date, 8 delivery_details
    """
    product = database.get_product(order[2])
    product_name = product[1] if product else "Unknown"

    try:
        delivery_details = json.loads(order[8]) if order[8] else []
    except Exception:
        delivery_details = []

    text = "🔎 *Order Details*\n\n━━━━━━━━━━━━━━━━━━\n"
    text += f"🧾 Order ID: `{order[0]}`\n"

    if is_admin:
        text += f"👤 User ID: `{order[1]}`\n"

    text += (
        f"📅 Date: {order[7]}\n"
        f"📦 Product: {product_name}\n"
        f"🔢 Quantity: {order[3]}\n"
        f"💰 Paid: {order[4]} USDT\n"
        f"💳 Method: {order[5]}\n"
        f"✅ Status: {order[6]}\n"
        f"━━━━━━━━━━━━━━━━━━\n\n"
        f"🔑 *Credentials:*\n"
        f"━━━━━━━━━━━━━━━━━━\n\n"
    )

    if not delivery_details:
        text += "No credentials saved for this order."
        return text

    if isinstance(delivery_details, dict):
        delivery_details = [delivery_details]

    for i, item_data in enumerate(delivery_details, start=1):
        if len(delivery_details) > 1:
            text += f"*Item {i}/{len(delivery_details)}*\n"

        if isinstance(item_data, dict):
            text += format_item_data_for_delivery(item_data) + "\n\n"
        else:
            text += f"`{item_data}`\n\n"

    text += "━━━━━━━━━━━━━━━━━━"
    return text


async def handle_order_details(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    order_id = update.message.text.strip()
    user_id = update.effective_user.id

    order = database.get_order_by_id(order_id)

    if not order:
        await update.message.reply_text(
            "❌ Order not found. Please check your Order ID.",
            reply_markup=utils.main_menu_keyboard()
        )
        return ConversationHandler.END

    if str(order[1]) != str(user_id):
        await update.message.reply_text(
            "⛔ This order does not belong to your account.",
            reply_markup=utils.main_menu_keyboard()
        )
        return ConversationHandler.END

    await update.message.reply_text(
        build_order_details_message(order, is_admin=False),
        reply_markup=utils.main_menu_keyboard(),
        parse_mode='Markdown'
    )
    return ConversationHandler.END


async def handle_admin_order_details(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not admin.is_admin(update.effective_user.id):
        return ConversationHandler.END

    order_id = update.message.text.strip()
    order = database.get_order_by_id(order_id)

    if not order:
        await update.message.reply_text(
            "❌ Order not found. Please check Order ID.",
            reply_markup=utils.admin_main_keyboard()
        )
        return ConversationHandler.END

    await update.message.reply_text(
        build_order_details_message(order, is_admin=True),
        reply_markup=utils.admin_main_keyboard(),
        parse_mode='Markdown'
    )
    return ConversationHandler.END


async def deliver_product(update: Update, context: ContextTypes.DEFAULT_TYPE, payment_method: str):
    user_id = update.effective_user.id

    product_id = context.user_data.get('current_product_id')
    quantity = context.user_data.get('quantity')
    total_amount = context.user_data.get('total_amount')

    product = database.get_product(product_id)
    order_id = utils.generate_order_id()
    items = database.get_unsold_items(product_id, quantity)

    if len(items) < quantity:
        if payment_method == 'Wallet':
            database.update_user_wallet(user_id, total_amount)
            database.add_transaction(user_id, "Refund (Out of Stock)", total_amount)

        msg = "❌ Out of stock during purchase. "
        msg += "Wallet refunded." if payment_method == 'Wallet' else "Contact admin for refund."

        if update.callback_query:
            await update.callback_query.edit_message_text(
                msg,
                reply_markup=utils.main_menu_keyboard()
            )
        else:
            await update.message.reply_text(
                msg,
                reply_markup=utils.main_menu_keyboard()
            )

        return

    # New flexible database format:
    # items = [{"id": 1, "data": {"email": "...", "password": "..."}}]
    #
    # Fallback support for old tuple format:
    # items = [("email", "password")]
    if isinstance(items[0], dict):
        item_ids = [item["id"] for item in items]
        delivery_details = [item["data"] for item in items]
        database.mark_items_as_sold(product_id, item_ids)
    else:
        emails = [item[0] for item in items]
        delivery_details = [
            {
                "email": item[0],
                "password": item[1]
            }
            for item in items
        ]
        database.mark_items_as_sold(product_id, emails)

    database.update_product_stock(product_id, -quantity)

    conn = database.sqlite3.connect(database.DATABASE_NAME)
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE users SET total_orders = total_orders + 1 WHERE id = ?",
        (user_id,)
    )
    conn.commit()
    conn.close()

    database.create_order(
        order_id,
        user_id,
        product_id,
        quantity,
        total_amount,
        payment_method,
        "Confirmed",
        delivery_details
    )

    date_str = datetime.datetime.now().strftime('%d %b %Y')

    text = (
        f"✅ *ORDER CONFIRMED!*\n\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"🧾 Order ID: `{order_id}`\n"
        f"📅 Date: {date_str}\n"
        f"━━━━━━━━━━━━━━━━━━\n\n"
        f"📦 Product: {product[1]}\n"
        f"🔢 Quantity: {quantity}\n"
        f"💰 Paid: {total_amount} USDT via {payment_method}\n\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"🔑 *Login Details:*\n"
        f"━━━━━━━━━━━━━━━━━━\n\n"
    )

    if quantity == 1:
        text += format_item_data_for_delivery(delivery_details[0]) + "\n\n"
    else:
        for i, item_data in enumerate(delivery_details):
            text += f"*Item {i + 1}/{quantity}*\n"
            text += format_item_data_for_delivery(item_data) + "\n\n"

    text += (
        "━━━━━━━━━━━━━━━━━━\n\n"
        "⚠️ *Important:*\n"
        "• Do not change the password\n"
        "• Do not share with others\n"
        "• Use on 1 device only"
    )

    if update.callback_query:
        await update.callback_query.edit_message_text(
            text,
            reply_markup=utils.order_confirmed_keyboard(),
            parse_mode='Markdown'
        )
    else:
        await update.message.reply_text(
            text,
            reply_markup=utils.order_confirmed_keyboard(),
            parse_mode='Markdown'
        )


# ══════════════════════════════════════════════════════════
#   ADMIN PANEL
# ══════════════════════════════════════════════════════════

async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not admin.is_admin(update.effective_user.id):
        await update.message.reply_text("⛔ Unauthorized.")
        return

    await update.message.reply_text(
        "👑 *Admin Panel*\n\nSelect an action:",
        reply_markup=utils.admin_main_keyboard(),
        parse_mode='Markdown'
    )


async def admin_button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query

    if not admin.is_admin(update.effective_user.id):
        await query.answer("⛔ Unauthorized", show_alert=True)
        return ConversationHandler.END

    await query.answer()

    data = query.data

    if data == 'admin_panel_back':
        await query.edit_message_text(
            "👑 *Admin Panel*\n\nSelect an action:",
            reply_markup=utils.admin_main_keyboard(),
            parse_mode='Markdown'
        )
        return ConversationHandler.END

    elif data == 'admin_view_products':
        await query.edit_message_text(
            admin.get_all_products_admin(),
            reply_markup=utils.admin_back_keyboard(),
            parse_mode='Markdown'
        )
        return ConversationHandler.END

    elif data == 'admin_view_all_orders':
        await query.edit_message_text(
            admin.get_all_orders_admin(),
            reply_markup=utils.admin_back_keyboard(),
            parse_mode='Markdown'
        )
        return ConversationHandler.END

    elif data == 'admin_withdraw_requests':
        await query.edit_message_text(
            admin.get_withdrawal_requests_admin(),
            reply_markup=utils.admin_back_keyboard(),
            parse_mode='Markdown'
        )
        return ConversationHandler.END

    elif data == 'admin_view_stats':
        await query.edit_message_text(
            admin.get_stats_admin(),
            reply_markup=utils.admin_back_keyboard(),
            parse_mode='Markdown'
        )
        return ConversationHandler.END

    elif data == 'admin_order_details':
        await query.edit_message_text(
            "🔎 *Admin Order Details*\n\nSend Order ID:",
            reply_markup=utils.admin_cancel_keyboard(),
            parse_mode='Markdown'
        )
        return ADMIN_ORDER_DETAILS

    elif data == 'admin_add_product':
        await query.edit_message_text(
            "➕ *Add Product*\n\n"
            "Stock field nahi dena. Stock auto `0` se start hoga.\n\n"
            "Format:\n"
            "`Name | Duration | Price | Rating | Description | feature1, feature2 | Note | Sticker Emoji ID`\n\n"
            "Example:\n"
            "`Netflix Premium | 1 Month | 3.5 | 4.8 | Premium account | 4K, Private | No password change | 5456140674028019486`",
            reply_markup=utils.admin_cancel_keyboard(),
            parse_mode='Markdown'
        )
        return ADMIN_ADD_PRODUCT

    elif data == 'admin_bulk_add_products':
        await query.edit_message_text(
            "➕ *Bulk Add Products*\n\n"
            "Stock field nahi dena. Har product stock `0` se start hoga.\n\n"
            "Format:\n"
            "`[Name | Duration | Price | Rating | Description | feature1, feature2 | Note | Sticker Emoji ID] [Name2 | Duration | Price | Rating | Description | feature1, feature2 | Note | Sticker Emoji ID]`\n\n"
            "Example:\n"
            "`[Netflix | 1 Month | 3.5 | 4.8 | Premium account | 4K, Private | No password change | 5456140674028019486] [Spotify | 1 Month | 2 | 4.7 | Music premium | No ads, HQ | Warranty 7 days | 5409048419211682843]`",
            reply_markup=utils.admin_cancel_keyboard(),
            parse_mode='Markdown'
        )
        return ADMIN_BULK_ADD_PRODUCTS

    elif data == 'admin_add_items':
        await query.edit_message_text(
            "📦 *Add Stock/Items*\n\n"
            "Flexible format. Jitne records add karo ge stock auto utna increase ho ga.\n\n"
            "Single product:\n"
            "`1[{email:saimpkf@gmail.com,password:123},{email:test@gmail.com,password:456}]`\n\n"
            "Different fields:\n"
            "`2[{link:https://example.com/account1},{link:https://example.com/account2}]`\n\n"
            "Bulk stock:\n"
            "`1[{email:a@gmail.com,password:111},{email:b@gmail.com,password:222}] 2[{link:https://x.com/1},{link:https://x.com/2}]`",
            reply_markup=utils.admin_cancel_keyboard(),
            parse_mode='Markdown'
        )
        return ADMIN_ADD_ITEMS

    elif data == 'admin_edit_price':
        await query.edit_message_text(
            "💲 *Edit Product Price*\n\n"
            "Send like this:\n\n"
            "`product_id new_price`\n\n"
            "Example: `1 4.5`",
            reply_markup=utils.admin_cancel_keyboard(),
            parse_mode='Markdown'
        )
        return ADMIN_EDIT_PRICE

    elif data == 'admin_edit_stock':
        await query.edit_message_text(
            "🔢 *Edit Product Stock*\n\n"
            "Send like this:\n\n"
            "`product_id new_stock`\n\n"
            "Example: `1 20`",
            reply_markup=utils.admin_cancel_keyboard(),
            parse_mode='Markdown'
        )
        return ADMIN_EDIT_STOCK

    elif data == 'admin_add_balance':
        await query.edit_message_text(
            "💰 *Add User Balance*\n\n"
            "Send like this:\n\n"
            "`user_id amount`\n\n"
            "Example: `123456789 10`",
            reply_markup=utils.admin_cancel_keyboard(),
            parse_mode='Markdown'
        )
        return ADMIN_ADD_BALANCE

    elif data == 'admin_approve_withdrawal':
        await query.edit_message_text(
            "✅ *Approve Withdrawal*\n\n"
            "Send withdrawal ID:",
            reply_markup=utils.admin_cancel_keyboard(),
            parse_mode='Markdown'
        )
        return ADMIN_APPROVE_WITHDRAWAL

    elif data == 'admin_broadcast':
        await query.edit_message_text(
            "📢 *Broadcast Message*\n\n"
            "Send the message you want to broadcast:",
            reply_markup=utils.admin_cancel_keyboard(),
            parse_mode='Markdown'
        )
        return ADMIN_BROADCAST

    elif data == 'admin_delete_product':
        await query.edit_message_text(
            "🗑️ *Delete Product*\n\n"
            "Send product ID:",
            reply_markup=utils.admin_cancel_keyboard(),
            parse_mode='Markdown'
        )
        return ADMIN_DELETE_PRODUCT

    return ConversationHandler.END


# ══════════════════════════════════════════════════════════
#   ADMIN INPUT HANDLERS
# ══════════════════════════════════════════════════════════

async def handle_admin_add_product(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not admin.is_admin(update.effective_user.id):
        return ConversationHandler.END

    try:
        data = update.message.text.split(' | ')

        if len(data) != 8:
            await update.message.reply_text(
                "❌ Invalid format. Send 8 fields:\n"
                "`Name | Duration | Price | Rating | Description | features | Note | Sticker Emoji ID`",
                parse_mode='Markdown'
            )
            return ADMIN_ADD_PRODUCT

        msg = admin.add_product_admin(
            data[0],
            data[1],
            float(data[2]),
            float(data[3]),
            data[4],
            data[5],
            data[6],
            data[7]
        )

        await update.message.reply_text(
            msg,
            reply_markup=utils.admin_main_keyboard(),
            parse_mode='Markdown'
        )

        if msg.startswith("✅"):
            await broadcast_to_all_users(
                context,
                (
                    f"📢 *New Product Added!*\n\n"
                    f"📦 Product: *{data[0]}*\n"
                    f"💰 Price: *{data[2]} USDT*\n"
                    f"📦 Stock: *0*\n\n"
                    f"👇 Check it now!"
                ),
                reply_markup=utils.products_list_keyboard(database.get_all_products()),
                parse_mode='Markdown'
            )

    except Exception as e:
        await update.message.reply_text(
            f"❌ Error: {e}",
            reply_markup=utils.admin_main_keyboard()
        )

    return ConversationHandler.END


async def handle_admin_bulk_add_products(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not admin.is_admin(update.effective_user.id):
        return ConversationHandler.END

    try:
        products_data = admin.parse_bulk_products_format(update.message.text)
        msg = admin.add_bulk_products_admin(products_data)

        await update.message.reply_text(
            msg,
            reply_markup=utils.admin_main_keyboard(),
            parse_mode='Markdown'
        )

        if msg.startswith("✅"):
            await broadcast_to_all_users(
                context,
                "📢 *New Products Added!*\n\n👇 Check products now!",
                reply_markup=utils.products_list_keyboard(database.get_all_products()),
                parse_mode='Markdown'
            )

    except Exception as e:
        await update.message.reply_text(
            f"❌ Error: {e}",
            reply_markup=utils.admin_main_keyboard()
        )

    return ConversationHandler.END


async def handle_admin_add_items(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not admin.is_admin(update.effective_user.id):
        return ConversationHandler.END

    try:
        stock_sections = admin.parse_stock_bulk_format(update.message.text)
        msg = admin.add_stock_bulk_admin(stock_sections)

        await update.message.reply_text(
            msg,
            reply_markup=utils.admin_main_keyboard(),
            parse_mode='Markdown'
        )

        if msg.startswith("📦"):
            for product_id, items_data in stock_sections:
                product = database.get_product(product_id)
                if product:
                    await broadcast_to_all_users(
                        context,
                        (
                            f"📢 *Stock Updated!*\n\n"
                            f"📦 Product: *{product[1]}*\n"
                            f"✅ New Stock Added: *{len(items_data)}*\n"
                            f"📦 Available Now: *{product[4]}*\n\n"
                            f"👇 Buy now!"
                        ),
                        reply_markup=utils.products_list_keyboard(database.get_all_products()),
                        parse_mode='Markdown'
                    )

    except Exception as e:
        await update.message.reply_text(
            f"❌ Error: {e}",
            reply_markup=utils.admin_main_keyboard()
        )

    return ConversationHandler.END


async def handle_admin_edit_price(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not admin.is_admin(update.effective_user.id):
        return ConversationHandler.END

    try:
        product_id, price = update.message.text.split()
        product_before = database.get_product(int(product_id))
        msg = admin.edit_product_price(int(product_id), float(price))

        await update.message.reply_text(
            msg,
            reply_markup=utils.admin_main_keyboard(),
            parse_mode='Markdown'
        )

        if msg.startswith("✅") and product_before:
            await broadcast_to_all_users(
                context,
                (
                    f"📢 *Price Updated!*\n\n"
                    f"📦 Product: *{product_before[1]}*\n"
                    f"💰 New Price: *{price} USDT*\n\n"
                    f"👇 Check it now!"
                ),
                reply_markup=utils.products_list_keyboard(database.get_all_products()),
                parse_mode='Markdown'
            )

    except Exception as e:
        await update.message.reply_text(
            f"❌ Error: {e}",
            reply_markup=utils.admin_main_keyboard()
        )

    return ConversationHandler.END


async def handle_admin_edit_stock(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not admin.is_admin(update.effective_user.id):
        return ConversationHandler.END

    try:
        product_id, stock = update.message.text.split()
        product_before = database.get_product(int(product_id))
        msg = admin.edit_product_stock(int(product_id), int(stock))

        await update.message.reply_text(
            msg,
            reply_markup=utils.admin_main_keyboard(),
            parse_mode='Markdown'
        )

        if msg.startswith("✅") and product_before:
            await broadcast_to_all_users(
                context,
                (
                    f"📢 *Stock Updated!*\n\n"
                    f"📦 Product: *{product_before[1]}*\n"
                    f"📦 Available Now: *{stock}*\n\n"
                    f"👇 Buy now!"
                ),
                reply_markup=utils.products_list_keyboard(database.get_all_products()),
                parse_mode='Markdown'
            )

    except Exception as e:
        await update.message.reply_text(
            f"❌ Error: {e}",
            reply_markup=utils.admin_main_keyboard()
        )

    return ConversationHandler.END


async def handle_admin_add_balance(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not admin.is_admin(update.effective_user.id):
        return ConversationHandler.END

    try:
        user_id, amount = update.message.text.split()
        user_id = int(user_id)
        amount = float(amount)

        msg = admin.add_balance_admin(user_id, amount)

        await update.message.reply_text(
            msg,
            reply_markup=utils.admin_main_keyboard(),
            parse_mode='Markdown'
        )

        await context.bot.send_message(
            chat_id=user_id,
            text=f"✅ Your wallet credited with *{amount} USDT*!",
            parse_mode='Markdown'
        )

    except Exception as e:
        await update.message.reply_text(
            f"❌ Error: {e}",
            reply_markup=utils.admin_main_keyboard()
        )

    return ConversationHandler.END


async def handle_admin_approve_withdrawal(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not admin.is_admin(update.effective_user.id):
        return ConversationHandler.END

    try:
        withdrawal_id = int(update.message.text)
        withdrawal = database.get_withdrawal(withdrawal_id)

        msg = admin.approve_withdrawal_admin(withdrawal_id)

        await update.message.reply_text(
            msg,
            reply_markup=utils.admin_main_keyboard(),
            parse_mode='Markdown'
        )

        if withdrawal:
            user_id = withdrawal[1]
            amount = withdrawal[2]

            await context.bot.send_message(
                chat_id=user_id,
                text=f"✅ Your withdrawal request of *{amount} USDT* has been approved.",
                parse_mode='Markdown'
            )

    except Exception as e:
        await update.message.reply_text(
            f"❌ Error: {e}",
            reply_markup=utils.admin_main_keyboard()
        )

    return ConversationHandler.END


async def handle_admin_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not admin.is_admin(update.effective_user.id):
        return ConversationHandler.END

    msg_text = update.message.text
    users = database.get_all_users()

    sent = 0

    for user in users:
        try:
            await context.bot.send_message(
                chat_id=user[0],
                text=msg_text
            )
            sent += 1
        except Exception:
            pass

    await update.message.reply_text(
        f"✅ Broadcast sent to {sent}/{len(users)} users.",
        reply_markup=utils.admin_main_keyboard()
    )

    return ConversationHandler.END


async def handle_admin_delete_product(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not admin.is_admin(update.effective_user.id):
        return ConversationHandler.END

    try:
        product_id = int(update.message.text)
        msg = admin.delete_product_admin(product_id)

        await update.message.reply_text(
            msg,
            reply_markup=utils.admin_main_keyboard(),
            parse_mode='Markdown'
        )

    except Exception as e:
        await update.message.reply_text(
            f"❌ Error: {e}",
            reply_markup=utils.admin_main_keyboard()
        )

    return ConversationHandler.END


# ══════════════════════════════════════════════════════════
#   OLD ADMIN COMMANDS
# ══════════════════════════════════════════════════════════

async def cmd_addproduct_data(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not admin.is_admin(update.effective_user.id):
        return

    try:
        data = update.message.text.replace('/addproduct_data ', '').split(' | ')

        if len(data) != 8:
            await update.message.reply_text(
                "Usage: `/addproduct_data Name | Duration | Price | Rating | Description | features | Note | Sticker Emoji ID`",
                parse_mode='Markdown'
            )
            return

        msg = admin.add_product_admin(
            data[0],
            data[1],
            float(data[2]),
            float(data[3]),
            data[4],
            data[5],
            data[6],
            data[7]
        )

        await update.message.reply_text(msg, parse_mode='Markdown')

    except Exception as e:
        await update.message.reply_text(f"❌ Error: {e}")


async def cmd_additems(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not admin.is_admin(update.effective_user.id):
        return

    try:
        raw = update.message.text.replace('/additems ', '', 1)
        stock_sections = admin.parse_stock_bulk_format(raw)

        msg = admin.add_stock_bulk_admin(stock_sections)

        await update.message.reply_text(msg, parse_mode='Markdown')

    except Exception as e:
        await update.message.reply_text(f"❌ Error: {e}")


async def cmd_editprice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not admin.is_admin(update.effective_user.id):
        return

    try:
        msg = admin.edit_product_price(
            int(context.args[0]),
            float(context.args[1])
        )

        await update.message.reply_text(msg, parse_mode='Markdown')

    except Exception:
        await update.message.reply_text(
            "Usage: `/editprice <id> <price>`",
            parse_mode='Markdown'
        )


async def cmd_editstock(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not admin.is_admin(update.effective_user.id):
        return

    try:
        msg = admin.edit_product_stock(
            int(context.args[0]),
            int(context.args[1])
        )

        await update.message.reply_text(msg, parse_mode='Markdown')

    except Exception:
        await update.message.reply_text(
            "Usage: `/editstock <id> <stock>`",
            parse_mode='Markdown'
        )


async def cmd_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not admin.is_admin(update.effective_user.id):
        return

    msg_text = update.message.text.replace('/broadcast ', '', 1)
    users = database.get_all_users()

    sent = 0

    for user in users:
        try:
            await context.bot.send_message(
                chat_id=user[0],
                text=msg_text
            )
            sent += 1
        except Exception:
            pass

    await update.message.reply_text(f"✅ Broadcast sent to {sent}/{len(users)} users.")


async def cmd_addbalance(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not admin.is_admin(update.effective_user.id):
        return

    try:
        uid = int(context.args[0])
        amount = float(context.args[1])

        msg = admin.add_balance_admin(uid, amount)

        await update.message.reply_text(msg, parse_mode='Markdown')

        await context.bot.send_message(
            chat_id=uid,
            text=f"✅ Your wallet credited with *{amount} USDT*!",
            parse_mode='Markdown'
        )

    except Exception:
        await update.message.reply_text(
            "Usage: `/addbalance <user_id> <amount>`",
            parse_mode='Markdown'
        )


async def cmd_approve(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not admin.is_admin(update.effective_user.id):
        return

    try:
        msg = admin.approve_withdrawal_admin(int(context.args[0]))

        await update.message.reply_text(msg, parse_mode='Markdown')

    except Exception:
        await update.message.reply_text(
            "Usage: `/approve <withdrawal_id>`",
            parse_mode='Markdown'
        )


# ══════════════════════════════════════════════════════════
#   MAIN
# ══════════════════════════════════════════════════════════

def main() -> None:
    application = ApplicationBuilder().token(config.TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("admin", admin_panel))

    application.add_handler(CommandHandler("addproduct_data", cmd_addproduct_data))
    application.add_handler(CommandHandler("additems", cmd_additems))
    application.add_handler(CommandHandler("editprice", cmd_editprice))
    application.add_handler(CommandHandler("editstock", cmd_editstock))
    application.add_handler(CommandHandler("broadcast", cmd_broadcast))
    application.add_handler(CommandHandler("addbalance", cmd_addbalance))
    application.add_handler(CommandHandler("approve", cmd_approve))

    reply_filter = (
        filters.TEXT & ~filters.COMMAND &
        filters.Regex(r'^(🛍️ Products|👤 Profile|📜 Purchase History|🔎 Order Details|💰 Wallet|🆘 Support)$')
    )

    application.add_handler(MessageHandler(reply_filter, reply_keyboard_handler))

    conv_handler = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(admin_button_handler, pattern='^admin_'),
            CallbackQueryHandler(button_handler),
        ],
        states={
            QUANTITY: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_quantity)
            ],
            WITHDRAW_AMOUNT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_withdraw_amount)
            ],
            WITHDRAW_ADDRESS: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_withdraw_address)
            ],
            CONTACT_ADMIN: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_contact_admin)
            ],
            ORDER_DETAILS: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_order_details)
            ],
            ADMIN_ORDER_DETAILS: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_admin_order_details)
            ],
            ADMIN_ADD_PRODUCT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_admin_add_product)
            ],
            ADMIN_BULK_ADD_PRODUCTS: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_admin_bulk_add_products)
            ],
            ADMIN_ADD_ITEMS: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_admin_add_items)
            ],
            ADMIN_EDIT_PRICE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_admin_edit_price)
            ],
            ADMIN_EDIT_STOCK: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_admin_edit_stock)
            ],
            ADMIN_ADD_BALANCE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_admin_add_balance)
            ],
            ADMIN_APPROVE_WITHDRAWAL: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_admin_approve_withdrawal)
            ],
            ADMIN_BROADCAST: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_admin_broadcast)
            ],
            ADMIN_DELETE_PRODUCT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_admin_delete_product)
            ],
        },
        fallbacks=[
            CommandHandler('cancel', cancel),
            CallbackQueryHandler(admin_button_handler, pattern='^admin_'),
            CallbackQueryHandler(button_handler),
        ],
        per_message=False,
        allow_reentry=True,
    )

    application.add_handler(conv_handler)

    print("🤖 Bunny Tools Bot starting...")
    application.run_polling(drop_pending_updates=True)


if __name__ == '__main__':
    main()