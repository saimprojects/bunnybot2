import logging
import datetime
import json
from html import escape as html_escape
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, CallbackQueryHandler,
    MessageHandler, filters, ContextTypes, ConversationHandler
)

import config
# Import updated modules from the updated_bot package.  These provide
# enhanced functionality such as sold counts, integrated purchase
# history and new admin actions.  Importing from updated_bot ensures
# that the correct versions are used even if similarly named modules
# exist in the project root.
from updated_bot import database, products, payment, admin, utils



logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

logger = logging.getLogger(__name__)


def tg(emoji_id: str, fallback: str) -> str:
    return f'<tg-emoji emoji-id="{emoji_id}">{fallback}</tg-emoji>'


CUSTOM_EMOJIS = {
    "products": ("5456140674028019486", "🛍️"),
    "purchase_history": ("5210956306952758910", "📜"),
    "welcome_star": ("5325547803936572038", "✨"),
    "choose_option": ("5406745015365943482", "👇"),
    "profile": ("5461117441612462242", "👤"),
    "id": ("5427168083074628963", "🆔"),
    "username": ("5260293700088511294", "📛"),
    "date": ("5413879192267805083", "📅"),
    "wallet": ("5409048419211682843", "💰"),
    "box": ("5231012545799666522", "📦"),
    "gift": ("5217822164362739968", "🎁"),
    "link": ("5305265301917549162", "🔗"),
    "no_orders": ("5406683434124859552", "📭"),
    "arrow": ("5416117059207572332", "👉"),
    "diamond": ("5427168083074628963", "💎"),
    "stats": ("5231200819986047254", "📊"),
    "order_details": ("5231012545799666522", "🔎"),
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


async def broadcast_stock_updates(context: ContextTypes.DEFAULT_TYPE, products_to_broadcast):
    """
    Jab admin stock add kare, ye function tamam users ko updated product ki notification bhejta hai.
    Ye sirf stock add par chalega.
    """
    if not products_to_broadcast:
        logger.info("[STOCK BROADCAST] No products to broadcast.")
        return 0, 0

    total_sent = 0
    total_users = 0

    for product_data in products_to_broadcast:
        product_id = product_data.get("product_id")
        added_count = product_data.get("added_count", 0)
        product_name = product_data.get("product_name", "Unknown")
        new_stock = product_data.get("new_stock", 0)

        product = database.get_product(product_id)

        if not product:
            logger.warning(f"[STOCK BROADCAST] Product not found: {product_id}")
            continue

        broadcast_text = (
            f"{ce('announcement')} <b>STOCK UPDATED!</b> {ce('announcement')}\n\n"
            f"{ce('box')} <b>Product:</b> {html_escape(str(product_name))}\n"
            f"{ce('confirm')} <b>New Stock Added:</b> {added_count}\n"
            f"{ce('box')} <b>Available Stock:</b> {new_stock}\n\n"
            f"{ce('order')} <b>Order now before stock runs out!</b>"
        )

        logger.info(f"[STOCK BROADCAST] Sending stock update for product {product_id}: {product_name}")

        sent, total = await broadcast_to_all_users(
            context,
            broadcast_text,
            reply_markup=product_purchase_keyboard(product, "success"),
            parse_mode="HTML"
        )

        total_sent += sent
        total_users = max(total_users, total)

    return total_sent, total_users



async def notify_admins(context: ContextTypes.DEFAULT_TYPE, text: str, parse_mode: str = "Markdown"):
    try:
        await context.bot.send_message(chat_id=config.ADMIN_ID, text=text, parse_mode=parse_mode)
    except Exception as e:
        logger.error(f"Failed to notify admin {config.ADMIN_ID}: {e}")


async def broadcast_to_all_users(context: ContextTypes.DEFAULT_TYPE, text: str, reply_markup=None, parse_mode: str = "Markdown"):
    users = database.get_all_users()
    sent = 0
    failed = 0

    logger.info(f"[BROADCAST] Starting broadcast to {len(users)} users")

    for user in users:
        try:
            chat_id = user[0]
            await context.bot.send_message(
                chat_id=chat_id,
                text=text,
                reply_markup=reply_markup,
                parse_mode=parse_mode
            )
            sent += 1
        except Exception as e:
            failed += 1
            logger.error(f"[BROADCAST] Failed for user {user[0]}: {e}")

    logger.info(f"[BROADCAST] Done. Sent={sent}, Failed={failed}, Total={len(users)}")
    return sent, len(users)



    (
        QUANTITY,
        WITHDRAW_AMOUNT,
        WITHDRAW_ADDRESS,
        CONTACT_ADMIN,
        BINANCE_ORDER_ID,
        WALLET_DEPOSIT_REF,
        WALLET_DEPOSIT_AMOUNT,
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
        ADMIN_EDIT_DETAILS,
        ADMIN_EDIT_CREDENTIALS,
        ADMIN_SET_FREEBIE,
    ) = range(21)


# ══════════════════════════════════════════════════════════
#   START - WELCOME MESSAGE
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
                    # Increment the referrer's referral count using the PostgreSQL connection
                    conn = database.get_connection()
                    cursor = conn.cursor()
                    cursor.execute(
                        "UPDATE users SET referrals = referrals + %s WHERE id = %s",
                        (1, referrer_id)
                    )
                    conn.commit()
                    cursor.close()
                    conn.close()
            except (IndexError, ValueError):
                pass

    first_name = html_escape(user.first_name or "there")
    
    welcome_text = (
        f"{ce('welcome_star')} <b> Bunny Tools Premium </b> {ce('welcome_star')}\n\n"
        f"{ce('diamond')} <b> Premium Digital Products with Instant Delivery</b> {ce('diamond')}\n"
        f"{ce('stats')} <b> Fast • Secure • Automated</b> {ce('stats')}\n\n"
        f"{ce('products')} <b> Products</b>\n"
        f"{ce('wallet')} <b> Wallet</b>\n"
        f"{ce('profile')} <b> Profile</b>\n"
        f"{ce('support_center')} <b> Support</b>\n\n"
        f"{ce('choose_option')} <b> Choose an option below</b>"
    )

    if update.message:
        await update.message.reply_text(welcome_text, reply_markup=utils.main_menu_keyboard(), parse_mode='HTML')
    elif update.callback_query:
        # Always send a new welcome message rather than editing the
        # existing one.  This prevents the original message from
        # disappearing and satisfies the requirement that each button
        # click produces a new chat message.
        await context.bot.send_message(
            chat_id=update.callback_query.message.chat_id,
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
        await update.callback_query.edit_message_text(text, reply_markup=utils.main_menu_keyboard(), parse_mode='HTML')
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
        await update.callback_query.edit_message_text(text, reply_markup=utils.main_menu_keyboard(), parse_mode='HTML')
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
            emoji = ce('confirm') if tx[3] > 0 else ce('cancel')
            msg += f"{emoji} {sign}{tx[3]} USDT | {html_escape(str(tx[2]))} | {html_escape(str(tx[4]).split(' ')[0])}\n"
    else:
        msg += "No recent transactions.\n"
    msg += f"━━━━━━━━━━━━━━━━━━\n\n{ce('choose_option')} <b>Options:</b>"
    return msg


# ══════════════════════════════════════════════════════════
#   REPLY TEXT HANDLER
# ══════════════════════════════════════════════════════════

async def reply_keyboard_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = update.message.text
    user_id = update.effective_user.id

    if text == "🛍️ Products":
        products_list = database.get_all_products()
        if not products_list:
            await update.message.reply_text("❌ No products available right now.", reply_markup=utils.main_menu_keyboard())
            return
        await update.message.reply_text("📦 *All Products* — choose one:", reply_markup=utils.products_list_keyboard(products_list), parse_mode='Markdown')

    elif text == "👤 Profile":
        await show_profile(update, context)

    elif text == "📜 Purchase History":
        await show_purchase_history(update, context)


    # The standalone "Order Details" text option has been removed from the
    # user menu.  Order details can now be accessed directly through
    # the purchase history which displays credentials for each order.

    elif text == "💰 Wallet":
        user = database.get_user(user_id)
        transactions = database.get_user_transactions(user_id)
        msg = build_wallet_message(user, transactions)
        await update.message.reply_text(msg, reply_markup=utils.wallet_options_keyboard(), parse_mode='HTML')

    elif text == "🆘 Support":
        msg = (
            f"{ce('support_center')} <b>Support Center</b>\n\n"
            f"{ce('faq')} <b>FAQ</b> — Common questions\n"
            f"{ce('contact')} <b>Contact Admin</b> — Message to owner\n"
            f"{ce('announcement')} <b>Announcements</b> — Join our channel\n\n"
            f"━━━━━━━━━━━━━━━━━━\n\n"
            f"{ce('choose_option')} Choose option:"
        )
        await update.message.reply_text(msg, reply_markup=utils.support_keyboard(), parse_mode='HTML')


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
            await query.edit_message_text("❌ No products available right now.", reply_markup=utils.main_menu_keyboard())
            return ConversationHandler.END
        await query.edit_message_text("📦 *All Products* — choose one:", reply_markup=utils.products_list_keyboard(products_list), parse_mode='Markdown')
        return ConversationHandler.END

    elif data == 'profile':
        await show_profile(update, context, edit=True)
        return ConversationHandler.END

    elif data == 'purchase_history':
        await show_purchase_history(update, context, edit=True)
        return ConversationHandler.END

    elif data == 'order_details':
        await query.edit_message_text(
            f"{ce('order_details')} <b>Order Details</b>\n\nPlease send your Order ID:",
            reply_markup=utils.main_menu_keyboard(),
            parse_mode='HTML'
        )
        return ORDER_DETAILS

    elif data.startswith('product_'):
        product_id = int(data.split('_')[1])
        context.user_data['current_product_id'] = product_id
        details_msg = products.get_product_details_message(product_id)
        # Fetch the product so that the keyboard can include the
        # "Claim Free" option when appropriate.  ``get_product``
        # returns a dict (RealDictRow) where keys can be accessed with
        # ``get``.  Pass the product directly to the keyboard
        # builder.
        product = database.get_product(product_id)
        await query.edit_message_text(
            details_msg,
            reply_markup=utils.product_details_keyboard(product),
            parse_mode='HTML'
        )
        return ConversationHandler.END

    elif data == 'order_now':
        product_id = context.user_data.get('current_product_id')
        if not product_id:
            await query.edit_message_text("❌ Product not selected.", reply_markup=utils.main_menu_keyboard())
            return ConversationHandler.END
        product = database.get_product(product_id)
        if not product or product[4] <= 0:
            await query.edit_message_text("❌ This product is out of stock.", reply_markup=utils.products_list_keyboard(database.get_all_products()))
            return ConversationHandler.END
        text = (
            f"🛍️ *{product[1]}*\n"
            f"💰 Price per item: {product[3]} USDT\n"
            f"📦 Available: {product[4]}\n\n"
            f"━━━━━━━━━━━━━━━━━━\n\n"
            f"*How many would you like to buy?*\n"
            f"_(Enter a number between 1 and {product[4]})_"
        )
        await query.edit_message_text(text, reply_markup=utils.quantity_selection_keyboard(), parse_mode='Markdown')
        return QUANTITY

    elif data == 'back_to_product_details':
        product_id = context.user_data.get('current_product_id')
        if product_id:
            product = database.get_product(product_id)
            await query.edit_message_text(
                products.get_product_details_message(product_id),
                reply_markup=utils.product_details_keyboard(product),
                parse_mode='HTML'
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
        await query.edit_message_text(text, reply_markup=utils.quantity_selection_keyboard(), parse_mode='Markdown')
        return QUANTITY

    elif data == 'claim_free':
        # User wants to claim a freebie.  Verify that the current
        # product is marked as free and that the user has joined the
        # specified channel before delivering the credentials.
        product_id = context.user_data.get('current_product_id')
        if not product_id:
            await context.bot.send_message(
                chat_id=query.message.chat_id,
                text="❌ No product selected.",
                reply_markup=utils.main_menu_keyboard(),
                parse_mode='HTML'
            )
            return ConversationHandler.END
        product = database.get_product(product_id)
        # ``product`` may be a dict (RealDictRow) or tuple.  Check the
        # is_free flag accordingly.
        is_free = False
        free_channel = None
        if product:
            if isinstance(product, dict):
                is_free = product.get('is_free')
                free_channel = product.get('free_channel')
            else:
                # Index 10 (is_free) and 11 (free_channel) if present
                try:
                    # product layout: id,name,duration,price,stock,rating,description,features,note,emoji_id,is_free,free_channel
                    is_free = product[10] if len(product) > 10 else False
                    free_channel = product[11] if len(product) > 11 else None
                except Exception:
                    is_free = False
                    free_channel = None
        if not product or not is_free:
            await context.bot.send_message(
                chat_id=query.message.chat_id,
                text="❌ This product is not available for free.",
                reply_markup=utils.main_menu_keyboard(),
                parse_mode='HTML'
            )
            return ConversationHandler.END
        if not free_channel:
            await context.bot.send_message(
                chat_id=query.message.chat_id,
                text="⚠️ Freebie channel is not configured. Please contact the admin.",
                reply_markup=utils.main_menu_keyboard(),
                parse_mode='HTML'
            )
            return ConversationHandler.END
        channel_username = str(free_channel).lstrip('@')
        # Check if the user has joined the channel.  Use a try/except
        # because get_chat_member will raise if the chat cannot be
        # resolved or the user is not a member.
        try:
            member = await context.bot.get_chat_member(chat_id=f"@{channel_username}", user_id=user_id)
            status = getattr(member, 'status', None)
            if status not in ('creator', 'administrator', 'member'):
                raise Exception('Not joined')
        except Exception:
            join_link = f"https://t.me/{channel_username}"
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("Join Channel", url=join_link)],
                [InlineKeyboardButton("I've Joined", callback_data='claim_free')],
            ])
            await context.bot.send_message(
                chat_id=query.message.chat_id,
                text=(
                    f"🎁 <b>Join our channel to claim this freebie!</b>\n\n"
                    f"You must be a member of @{channel_username} to access free products.\n"
                    "Tap the button below to join, then click 'I've Joined' once you have joined."
                ),
                reply_markup=keyboard,
                parse_mode='HTML'
            )
            return ConversationHandler.END
        # User has joined; deliver one item for free
        context.user_data['quantity'] = 1
        context.user_data['total_amount'] = 0
        # Ensure current_product_id remains set
        context.user_data['current_product_id'] = product_id
        await deliver_product(update, context, 'Free')
        # Prompt the user to start again
        await context.bot.send_message(
            chat_id=query.message.chat_id,
            text="✅ Use /start to go back to the main menu.",
            parse_mode='Markdown'
        )
        return ConversationHandler.END

    elif data == 'pay_binance':
        total_amount = context.user_data.get('total_amount')
        context.user_data['payment_method'] = 'Binance Pay ID'
        await query.edit_message_text(
            payment.get_binance_payment_details(total_amount),
            reply_markup=utils.binance_payment_keyboard(),
            parse_mode='HTML'
        )
        return ConversationHandler.END

    elif data == 'pay_wallet':
        total_amount = context.user_data.get('total_amount')
        user_id = update.effective_user.id
        user = database.get_user(user_id)
        current_balance = user[3] if user else 0
        
        if current_balance >= total_amount:
            await query.edit_message_text(
                payment.get_wallet_payment_summary(user_id, total_amount),
                reply_markup=utils.wallet_payment_keyboard(),
                parse_mode='HTML'
            )
            return ConversationHandler.END
        else:
            required = round(total_amount - current_balance, 4)
            await query.edit_message_text(
                f"{ce('cancel')} <b>Insufficient Balance</b>\n\n"
                f"Your Balance: <b>{current_balance} USDT</b>\n"
                f"Required: <b>{total_amount} USDT</b>\n"
                f"Short by: <b>{required} USDT</b>\n\n"
                f"Please deposit funds to your wallet first.",
                reply_markup=utils.insufficient_balance_keyboard(),
                parse_mode='HTML'
            )
            return ConversationHandler.END

    elif data == 'confirm_wallet_payment':
        product_id = context.user_data.get('current_product_id')
        quantity = context.user_data.get('quantity')
        total_amount = context.user_data.get('total_amount')
        
        success, msg = payment.process_wallet_payment(
            user_id,
            utils.generate_order_id(),
            product_id,
            quantity,
            total_amount
        )
        if success:
            await deliver_product(update, context, 'Wallet')
        else:
            await query.edit_message_text(msg, reply_markup=utils.payment_method_keyboard(), parse_mode='HTML')
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
            f"*Choose payment method:*"
        )
        await query.edit_message_text(text, reply_markup=utils.payment_method_keyboard(), parse_mode='Markdown')
        return ConversationHandler.END

    elif data == 'cancel_order':
        await query.edit_message_text("❌ Order cancelled.", reply_markup=utils.main_menu_keyboard())
        return ConversationHandler.END

    elif data == 'check_binance_payment':
        await query.edit_message_text(
            "✅ <b>Payment Sent?</b>\n\n"
            "Send your <b>Binance Order ID / off-chain transaction reference</b> here.\n\n"
            "Example: <code>M_P_71505104267788288</code>",
            reply_markup=utils.ask_order_id_keyboard(),
            parse_mode='HTML'
        )
        return BINANCE_ORDER_ID

    elif data == 'wallet':
        user = database.get_user(user_id)
        transactions = database.get_user_transactions(user_id)
        text = build_wallet_message(user, transactions)
        await query.edit_message_text(text, reply_markup=utils.wallet_options_keyboard(), parse_mode='HTML')
        return ConversationHandler.END

    elif data == 'deposit_wallet':
        await query.edit_message_text(
            f"{ce('wallet')} <b>Wallet Deposit</b>\n\n"
            "Enter amount to top up with Binance Pay ID.\n"
            "Example: <code>10.5</code>",
            reply_markup=utils.deposit_enter_amount_keyboard(),
            parse_mode='HTML'
        )
        return WALLET_DEPOSIT_AMOUNT

    elif data == 'check_deposit_payment':
        deposit_amount = context.user_data.get('wallet_deposit_amount')
        if not deposit_amount:
            await query.edit_message_text(
                f"{ce('wallet')} <b>Wallet Deposit</b>\n\n"
                "Please enter deposit amount first.\n"
                "Example: <code>10.5</code>",
                reply_markup=utils.deposit_enter_amount_keyboard(),
                parse_mode='HTML'
            )
            return WALLET_DEPOSIT_AMOUNT
        await query.edit_message_text(
            "✅ <b>Payment Sent?</b>\n\n"
            "Send your <b>Binance Order ID / off-chain transaction reference</b> here.\n\n"
            "Example: <code>M_P_71505104267788288</code>",
            reply_markup=utils.ask_deposit_ref_keyboard(),
            parse_mode='HTML'
        )
        return WALLET_DEPOSIT_REF

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
            "A: Contact admin with your Order ID for replacement within warranty.\n\n"
            "*Q: Can I share the account?*\n"
            "A: No, sharing violates our policy.",
            reply_markup=utils.support_keyboard(),
            parse_mode='Markdown'
        )
        return ConversationHandler.END

    elif data == 'contact_admin':
        await query.edit_message_text("✍️ Please type your message for the admin below:", reply_markup=utils.support_keyboard())
        return CONTACT_ADMIN

    return ConversationHandler.END


# ══════════════════════════════════════════════════════════
#   USER CONVERSATION HANDLERS
# ══════════════════════════════════════════════════════════

async def handle_wallet_deposit_amount(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    try:
        amount = float(update.message.text.strip())
        if amount <= 0:
            await update.message.reply_text(
                "❌ Please enter a valid amount greater than 0.",
                reply_markup=utils.deposit_enter_amount_keyboard()
            )
            return WALLET_DEPOSIT_AMOUNT

        context.user_data['wallet_deposit_amount'] = amount

        await update.message.reply_text(
            payment.get_binance_wallet_deposit_details(amount),
            reply_markup=utils.deposit_wallet_keyboard(),
            parse_mode='HTML'
        )
        return ConversationHandler.END

    except ValueError:
        await update.message.reply_text(
            "❌ Invalid amount. Example: 10.5",
            reply_markup=utils.deposit_enter_amount_keyboard()
        )
        return WALLET_DEPOSIT_AMOUNT


async def handle_wallet_deposit_ref(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_id = update.effective_user.id
    reference = update.message.text.strip()
    amount = context.user_data.get('wallet_deposit_amount')

    if not amount:
        await update.message.reply_text(
            "❌ Deposit amount missing. Please start deposit again.",
            reply_markup=utils.wallet_options_keyboard()
        )
        return ConversationHandler.END

    await update.message.reply_text("⏳ Checking Binance Pay history... Please wait.", parse_mode='HTML')

    success, msg = payment.process_wallet_deposit_binance(
        user_id=user_id,
        amount=amount,
        binance_order_id=reference
    )

    if success:
        context.user_data.pop('wallet_deposit_amount', None)

    await update.message.reply_text(msg, reply_markup=utils.wallet_options_keyboard(), parse_mode='HTML')
    return ConversationHandler.END


async def handle_binance_order_id(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    binance_order_id = update.message.text.strip()
    user_id = update.effective_user.id

    await update.message.reply_text("⏳ Verifying Binance payment... Please wait.", parse_mode='HTML')

    success, msg = payment.process_binance_payment(
        user_id,
        utils.generate_order_id(),
        context.user_data.get('current_product_id'),
        context.user_data.get('quantity'),
        context.user_data.get('total_amount'),
        binance_order_id=binance_order_id
    )

    if success:
        await deliver_product(update, context, 'Binance')
    else:
        await update.message.reply_text(msg, reply_markup=utils.payment_method_keyboard(), parse_mode='HTML')

    return ConversationHandler.END


async def handle_quantity(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    try:
        quantity = int(update.message.text)
        product_id = context.user_data.get('current_product_id')
        product = database.get_product(product_id)

        if not product:
            await update.message.reply_text("❌ Product not found.")
            return ConversationHandler.END

        if quantity < 1 or quantity > product[4]:
            await update.message.reply_text(f"⚠️ Enter a number between 1 and {product[4]}.", reply_markup=utils.quantity_selection_keyboard())
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
            f"*Choose payment method:*",
            reply_markup=utils.payment_method_keyboard(),
            parse_mode='Markdown'
        )
        return ConversationHandler.END

    except ValueError:
        await update.message.reply_text("⚠️ Please enter a valid number.", reply_markup=utils.quantity_selection_keyboard())
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
            await update.message.reply_text(f"⚠️ Insufficient balance: {user[3]} USDT. Enter again or /cancel:")
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
        f"💸 *New Withdrawal*\n\nUser: `{user_id}`\nAmount: {amount} USDT\nAddress: `{address}`",
        parse_mode='Markdown'
    )
    return ConversationHandler.END


async def handle_contact_admin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    msg_text = update.message.text
    user_id = update.effective_user.id
    username = update.effective_user.username or "Unknown"

    await notify_admins(
        context,
        f"📩 *Message from User*\n\nID: `{user_id}`\nUsername: @{username}\n\n{msg_text}",
        parse_mode='Markdown'
    )
    await update.message.reply_text("✅ Message sent to admin.", reply_markup=utils.main_menu_keyboard())
    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("❌ Operation cancelled.", reply_markup=utils.main_menu_keyboard())
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
    product = database.get_product(order[2])
    product_name = product[1] if product else "Unknown"

    try:
        delivery_details = json.loads(order[8]) if order[8] else []
    except Exception:
        delivery_details = []

    text = f"{ce('order_details')} <b>Order Details</b>\n\n━━━━━━━━━━━━━━━━━━\n"
    text += f"🧾 Order ID: <code>{html_escape(str(order[0]))}</code>\n"

    if is_admin:
        text += f"{ce('profile')} User ID: <code>{order[1]}</code>\n"

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
        await update.message.reply_text("❌ Order not found. Please check your Order ID.", reply_markup=utils.main_menu_keyboard())
        return ConversationHandler.END

    if str(order[1]) != str(user_id):
        await update.message.reply_text("⛔ This order does not belong to your account.", reply_markup=utils.main_menu_keyboard())
        return ConversationHandler.END

    await update.message.reply_text(build_order_details_message(order, is_admin=False), reply_markup=utils.main_menu_keyboard(), parse_mode='HTML')
    return ConversationHandler.END


async def handle_admin_order_details(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not admin.is_admin(update.effective_user.id):
        return ConversationHandler.END

    order_id = update.message.text.strip()
    order = database.get_order_by_id(order_id)

    if not order:
        await update.message.reply_text("❌ Order not found. Please check Order ID.", reply_markup=utils.admin_main_keyboard())
        return ConversationHandler.END

    await update.message.reply_text(build_order_details_message(order, is_admin=True), reply_markup=utils.admin_main_keyboard(), parse_mode='HTML')
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
            await update.callback_query.edit_message_text(msg, reply_markup=utils.main_menu_keyboard())
        else:
            await update.message.reply_text(msg, reply_markup=utils.main_menu_keyboard())
        return

    if isinstance(items[0], dict):
        item_ids = [item["id"] for item in items]
        delivery_details = [item["data"] for item in items]
        database.mark_items_as_sold(product_id, item_ids)
    else:
        delivery_details = [{"email": item[0], "password": item[1]} for item in items]
        database.mark_items_as_sold(product_id, [item[0] for item in items])

    database.update_product_stock(product_id, -quantity)

    # Update the user's total_orders count using PostgreSQL
    conn = database.get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE users SET total_orders = total_orders + %s WHERE id = %s",
        (1, user_id)
    )
    conn.commit()
    cursor.close()
    conn.close()

    database.create_order(order_id, user_id, product_id, quantity, total_amount, payment_method, "Confirmed", delivery_details)

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

    # Send the order confirmation and credentials as a new message rather than
    # editing the previous one.  Do not include any back buttons or
    # order detail buttons here; instead, instruct the user to start
    # over using /start after delivery.
    if update.callback_query:
        await context.bot.send_message(
            chat_id=update.callback_query.message.chat_id,
            text=text,
            parse_mode='Markdown'
        )
    else:
        await update.message.reply_text(
            text,
            parse_mode='Markdown'
        )
    # Prompt the user to return to the main menu
    try:
        chat_id = update.callback_query.message.chat_id if update.callback_query else update.message.chat_id
    except Exception:
        chat_id = update.effective_chat.id
    await context.bot.send_message(
        chat_id=chat_id,
        text="✅ Use /start to return to the main menu.",
        parse_mode='Markdown'
    )


# ══════════════════════════════════════════════════════════
#   ADMIN PANEL
# ══════════════════════════════════════════════════════════

async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not admin.is_admin(update.effective_user.id):
        await update.message.reply_text("⛔ Unauthorized.")
        return
    await update.message.reply_text("👑 *Admin Panel*\n\nSelect an action:", reply_markup=utils.admin_main_keyboard(), parse_mode='Markdown')


async def admin_button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    if not admin.is_admin(update.effective_user.id):
        await query.answer("⛔ Unauthorized", show_alert=True)
        return ConversationHandler.END

    await query.answer()
    data = query.data

    if data == 'admin_panel_back':
        await query.edit_message_text("👑 *Admin Panel*\n\nSelect an action:", reply_markup=utils.admin_main_keyboard(), parse_mode='Markdown')
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

    elif data == 'admin_view_stats':
        await query.edit_message_text(admin.get_stats_admin(), reply_markup=utils.admin_back_keyboard(), parse_mode='Markdown')
        return ConversationHandler.END

    elif data == 'admin_order_details':
        await query.edit_message_text("🔎 *Admin Order Details*\n\nSend Order ID:", reply_markup=utils.admin_cancel_keyboard(), parse_mode='Markdown')
        return ADMIN_ORDER_DETAILS

    elif data == 'admin_add_product':
        await query.edit_message_text(
            "➕ *Add Product*\n\nFormat:\n`Name | Duration | Price | Description | Note | Sticker Emoji ID`\n\nExample:\n`Netflix Premium | 1 Month | 3.5 | Premium account | No password change | 5456140674028019486`",
            reply_markup=utils.admin_cancel_keyboard(), parse_mode='Markdown'
        )
        return ADMIN_ADD_PRODUCT

    elif data == 'admin_bulk_add_products':
        await query.edit_message_text(
            "➕ *Bulk Add Products*\n\nFormat:\n`[Name | Duration | Price | Description | Note | Sticker Emoji ID] [Name2 | ...]`\n\nExample:\n`[Netflix | 1 Month | 3.5 | Premium | No password change | 5456140674028019486] [Spotify | 1 Month | 2 | Music | Warranty 7 days | 5409048419211682843]`",
            reply_markup=utils.admin_cancel_keyboard(), parse_mode='Markdown'
        )
        return ADMIN_BULK_ADD_PRODUCTS

    elif data == 'admin_add_items':
        await query.edit_message_text(
            "📦 *Add Stock/Items*\n\nFormat:\n`Product_ID[{field1:value1,field2:value2},{...}]`\n\n"
            "*Examples:*\n"
            "Email/Pass: `1[{email:a@gmail.com,password:123}]`\n"
            "Link: `2[{link:https://example.com/acc1}]`\n"
            "Key: `3[{key:XXXXX-XXXXX}]`\n\n"
            "Bulk: `1[{email:a@gmail.com,password:111}] 2[{link:https://x.com/1}]`\n\n"
            "⚠️ Spaces field ke andar avoid karo.",
            reply_markup=utils.admin_cancel_keyboard(), parse_mode='Markdown'
        )
        return ADMIN_ADD_ITEMS

    elif data == 'admin_edit_price':
        await query.edit_message_text("💲 *Edit Product Price*\n\nFormat: `product_id new_price`\nExample: `1 4.5`", reply_markup=utils.admin_cancel_keyboard(), parse_mode='Markdown')
        return ADMIN_EDIT_PRICE

    elif data == 'admin_edit_stock':
        await query.edit_message_text("🔢 *Edit Product Stock*\n\nFormat: `product_id new_stock`\nExample: `1 20`", reply_markup=utils.admin_cancel_keyboard(), parse_mode='Markdown')
        return ADMIN_EDIT_STOCK

    elif data == 'admin_add_balance':
        await query.edit_message_text("💰 *Add User Balance*\n\nFormat: `user_id amount`\nExample: `123456789 10`", reply_markup=utils.admin_cancel_keyboard(), parse_mode='Markdown')
        return ADMIN_ADD_BALANCE

    elif data == 'admin_approve_withdrawal':
        await query.edit_message_text("✅ *Approve Withdrawal*\n\nSend withdrawal ID:", reply_markup=utils.admin_cancel_keyboard(), parse_mode='Markdown')
        return ADMIN_APPROVE_WITHDRAWAL

    elif data == 'admin_broadcast':
        await query.edit_message_text("📢 *Broadcast Message*\n\nSend the message you want to broadcast:", reply_markup=utils.admin_cancel_keyboard(), parse_mode='Markdown')
        return ADMIN_BROADCAST

    elif data == 'admin_delete_product':
        await query.edit_message_text("🗑️ *Delete Product*\n\nSend product ID:", reply_markup=utils.admin_cancel_keyboard(), parse_mode='Markdown')
        return ADMIN_DELETE_PRODUCT

    elif data == 'admin_edit_details':
        # Prompt the admin for product detail edits.  Specify the format and
        # allowed fields.  The admin must provide the product ID, the
        # field name to update and the new value.  Example:
        #   "1 name Netflix Premium Plus"
        await query.edit_message_text(
            "✏️ *Edit Product Details*\n\n"
            "Format: `product_id field_name new_value`\n"
            "Allowed fields: name, duration, description, note, emoji_id\n\n"
            "Example: `1 name Netflix Premium Plus`",
            reply_markup=utils.admin_cancel_keyboard(),
            parse_mode='Markdown'
        )
        return ADMIN_EDIT_DETAILS

    elif data == 'admin_edit_credentials':
        # Prompt the admin to edit credentials of a single unsold stock item.
        # The admin must provide the item ID followed by key:value pairs
        # separated by spaces.  Example:
        #   "123 email:new@example.com password:newpass"
        await query.edit_message_text(
            "🔑 *Edit Stock Item Credentials*\n\n"
            "Format: `item_id key1:value1 key2:value2`\n\n"
            "Example: `123 email:new@example.com password:newpass`",
            reply_markup=utils.admin_cancel_keyboard(),
            parse_mode='Markdown'
        )
        return ADMIN_EDIT_CREDENTIALS

    elif data == 'admin_set_freebie':
        # Prompt the admin to manage freebies.  Admin should send
        # "product_id channel" to mark a product as free or
        # "product_id none" to remove the free status.  Channel
        # usernames should be provided without '@'.  Example:
        #   "1 mychannel" to set product 1 free for members of @mychannel
        #   "1 none" to unset the freebie.
        await query.edit_message_text(
            "🎁 *Freebie Management*\n\n"
            "Send `product_id channel` to mark a product as free.\n"
            "Send `product_id none` to remove the free status.\n\n"
            "Example: `2 mychannel` or `2 none`",
            reply_markup=utils.admin_cancel_keyboard(),
            parse_mode='Markdown'
        )
        return ADMIN_SET_FREEBIE

    return ConversationHandler.END


# ══════════════════════════════════════════════════════════
#   ADMIN INPUT HANDLERS
# ══════════════════════════════════════════════════════════

async def handle_admin_add_product(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not admin.is_admin(update.effective_user.id):
        return ConversationHandler.END
    try:
        data = update.message.text.split(' | ')
        if len(data) != 6:
            await update.message.reply_text("❌ Invalid format. Send 6 fields:\n`Name | Duration | Price | Description | Note | Sticker Emoji ID`", parse_mode='Markdown')
            return ADMIN_ADD_PRODUCT

        msg = admin.add_product_admin(data[0], data[1], float(data[2]), data[3], data[4], data[5])
        await update.message.reply_text(msg, reply_markup=utils.admin_main_keyboard(), parse_mode='Markdown')

        # Sirf admin ko message, users ko nahi bhejna
        # Broadcast removed - sirf stock add par hi jayega

    except Exception as e:
        await update.message.reply_text(f"❌ Error: {e}", reply_markup=utils.admin_main_keyboard())
    return ConversationHandler.END


async def handle_admin_bulk_add_products(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not admin.is_admin(update.effective_user.id):
        return ConversationHandler.END
    try:
        products_data = admin.parse_bulk_products_format(update.message.text)
        msg = admin.add_bulk_products_admin(products_data)
        await update.message.reply_text(msg, reply_markup=utils.admin_main_keyboard(), parse_mode='Markdown')

        # Sirf admin ko message, users ko nahi bhejna
        # Broadcast removed - sirf stock add par hi jayega

    except Exception as e:
        await update.message.reply_text(f"❌ Error: {e}", reply_markup=utils.admin_main_keyboard())
    return ConversationHandler.END


async def handle_admin_add_items(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not admin.is_admin(update.effective_user.id):
        return ConversationHandler.END

    try:
        stock_sections = admin.parse_stock_bulk_format(update.message.text)
        result = admin.add_stock_bulk_admin(stock_sections)

        if isinstance(result, tuple):
            msg, products_to_broadcast = result
        else:
            msg = result
            products_to_broadcast = []

        await update.message.reply_text(
            msg,
            reply_markup=utils.admin_main_keyboard(),
            parse_mode='Markdown'
        )

        sent, total = await broadcast_stock_updates(context, products_to_broadcast)

        if products_to_broadcast:
            await update.message.reply_text(
                f"📢 Stock update notification sent to {sent}/{total} users.",
                reply_markup=utils.admin_main_keyboard()
            )

    except Exception as e:
        logger.exception(f"[ADMIN ADD STOCK] Error: {e}")
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
        await update.message.reply_text(msg, reply_markup=utils.admin_main_keyboard(), parse_mode='Markdown')

        if msg.startswith("✅") and product_before:
            product = database.get_product(int(product_id))
            await broadcast_to_all_users(context, product_update_message("Price Updated!", product, [
                f"{ce('wallet')} New Price: <b>{html_escape(str(price))} USDT</b>",
            ]), reply_markup=product_purchase_keyboard(product, "success"), parse_mode='HTML')
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {e}", reply_markup=utils.admin_main_keyboard())
    return ConversationHandler.END


async def handle_admin_edit_stock(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not admin.is_admin(update.effective_user.id):
        return ConversationHandler.END
    try:
        product_id, stock = update.message.text.split()
        product_before = database.get_product(int(product_id))
        msg = admin.edit_product_stock(int(product_id), int(stock))
        await update.message.reply_text(msg, reply_markup=utils.admin_main_keyboard(), parse_mode='Markdown')

        if msg.startswith("✅") and product_before:
            product = database.get_product(int(product_id))
            await broadcast_to_all_users(context, product_update_message("Stock Updated!", product, [
                f"{ce('box')} Available Now: <b>{html_escape(str(stock))}</b>",
            ]), reply_markup=product_purchase_keyboard(product, "success"), parse_mode='HTML')
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {e}", reply_markup=utils.admin_main_keyboard())
    return ConversationHandler.END


async def handle_admin_add_balance(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not admin.is_admin(update.effective_user.id):
        return ConversationHandler.END
    try:
        user_id, amount = update.message.text.split()
        user_id = int(user_id)
        amount = float(amount)
        msg = admin.add_balance_admin(user_id, amount)
        await update.message.reply_text(msg, reply_markup=utils.admin_main_keyboard(), parse_mode='Markdown')
        await context.bot.send_message(chat_id=user_id, text=f"✅ Your wallet credited with *{amount} USDT*!", parse_mode='Markdown')
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {e}", reply_markup=utils.admin_main_keyboard())
    return ConversationHandler.END


async def handle_admin_approve_withdrawal(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not admin.is_admin(update.effective_user.id):
        return ConversationHandler.END
    try:
        withdrawal_id = int(update.message.text)
        withdrawal = database.get_withdrawal(withdrawal_id)
        msg = admin.approve_withdrawal_admin(withdrawal_id)
        await update.message.reply_text(msg, reply_markup=utils.admin_main_keyboard(), parse_mode='Markdown')

        if withdrawal:
            await context.bot.send_message(
                chat_id=withdrawal[1],
                text=f"✅ Your withdrawal request of *{withdrawal[2]} USDT* has been approved.",
                parse_mode='Markdown'
            )
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {e}", reply_markup=utils.admin_main_keyboard())
    return ConversationHandler.END


async def handle_admin_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not admin.is_admin(update.effective_user.id):
        return ConversationHandler.END
    # Allow admins to broadcast messages with custom emoji IDs and
    # formatting.  Replace [emoji_id] patterns with the proper
    # <tg-emoji> tags and send using HTML parse mode.  This lets
    # admins include custom Telegram Premium formatting or emojis in
    # their message.  See products.format_with_custom_emojis() for
    # details.
    msg_text = update.message.text
    # Convert bracketed custom emoji IDs to <tg-emoji> tags
    html_text = products.format_with_custom_emojis(msg_text)
    users = database.get_all_users()
    sent = 0
    for user in users:
        try:
            await context.bot.send_message(
                chat_id=user[0],
                text=html_text,
                parse_mode='HTML'
            )
            sent += 1
        except Exception:
            pass
    await update.message.reply_text(
        f"✅ Broadcast sent to {sent}/{len(users)} users.",
        reply_markup=utils.admin_main_keyboard(),
        parse_mode='Markdown'
    )
    return ConversationHandler.END


async def handle_admin_delete_product(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not admin.is_admin(update.effective_user.id):
        return ConversationHandler.END
    try:
        product_id = int(update.message.text)
        msg = admin.delete_product_admin(product_id)
        await update.message.reply_text(msg, reply_markup=utils.admin_main_keyboard(), parse_mode='Markdown')
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {e}", reply_markup=utils.admin_main_keyboard())
    return ConversationHandler.END


# -------------------------------------------------------------------
# New admin handlers for editing product details and item credentials
# -------------------------------------------------------------------

async def handle_admin_edit_details(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle admin input for editing a product's textual details.

    The expected format is: ``product_id field_name new_value``.
    The new value may contain spaces.  Allowed fields are name,
    duration, description, note, and emoji_id.  See ``admin.edit_product_details``
    for validation.
    """
    if not admin.is_admin(update.effective_user.id):
        return ConversationHandler.END
    try:
        parts = update.message.text.split()
        if len(parts) < 3:
            await update.message.reply_text(
                "❌ Invalid format. Use: `product_id field_name new_value`",
                reply_markup=utils.admin_main_keyboard(),
                parse_mode='Markdown'
            )
            return ConversationHandler.END
        product_id = int(parts[0])
        field_name = parts[1]
        new_value = " ".join(parts[2:])
        msg = admin.edit_product_details(product_id, field_name, new_value)
        await update.message.reply_text(msg, reply_markup=utils.admin_main_keyboard(), parse_mode='Markdown')
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {e}", reply_markup=utils.admin_main_keyboard())
    return ConversationHandler.END


async def handle_admin_edit_credentials(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle admin input for editing the credential fields of an unsold item.

    The expected format is: ``item_id key1:value1 key2:value2 ...``.
    Each key/value pair must be separated by spaces and use a colon.
    Keys and values may not contain spaces.  See ``admin.edit_unsold_item_credentials``
    for update logic.
    """
    if not admin.is_admin(update.effective_user.id):
        return ConversationHandler.END
    try:
        parts = update.message.text.split()
        if len(parts) < 2:
            await update.message.reply_text(
                "❌ Invalid format. Use: `item_id key:value ...`",
                reply_markup=utils.admin_main_keyboard(),
                parse_mode='Markdown'
            )
            return ConversationHandler.END
        item_id = int(parts[0])
        updates = {}
        for part in parts[1:]:
            if ':' not in part:
                await update.message.reply_text(
                    f"❌ Invalid field format: `{part}`. Use key:value pairs.",
                    reply_markup=utils.admin_main_keyboard(),
                    parse_mode='Markdown'
                )
                return ConversationHandler.END
            key, value = part.split(':', 1)
            updates[key.strip()] = value.strip()
        msg = admin.edit_unsold_item_credentials(item_id, updates)
        await update.message.reply_text(msg, reply_markup=utils.admin_main_keyboard(), parse_mode='Markdown')
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {e}", reply_markup=utils.admin_main_keyboard())
    return ConversationHandler.END


async def handle_admin_set_freebie(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle admin input for marking or unmarking a product as a freebie.

    The admin should send a message in the format ``product_id channel`` to
    mark the product as free for members of the specified channel or
    ``product_id none`` to remove the free status.  Channel names
    should not include the leading ``@``.  Responds with a success or
    error message and returns to the admin main menu.
    """
    if not admin.is_admin(update.effective_user.id):
        return ConversationHandler.END
    text = (update.message.text or '').strip()
    parts = text.split()
    if len(parts) != 2:
        await update.message.reply_text(
            "❌ Invalid format.  Use `product_id channel` or `product_id none`.",
            reply_markup=utils.admin_main_keyboard(),
            parse_mode='Markdown'
        )
        return ConversationHandler.END
    try:
        product_id = int(parts[0])
    except Exception:
        await update.message.reply_text(
            "❌ First part must be a valid product ID.",
            reply_markup=utils.admin_main_keyboard(),
            parse_mode='Markdown'
        )
        return ConversationHandler.END
    channel = parts[1]
    # Remove leading '@' if provided
    channel = channel.lstrip('@')
    if channel.lower() == 'none':
        msg = admin.unset_freebie(product_id)
    else:
        msg = admin.set_freebie(product_id, channel)
    await update.message.reply_text(
        msg,
        reply_markup=utils.admin_main_keyboard(),
        parse_mode='Markdown'
    )
    return ConversationHandler.END


async def handle_admin_set_freebie(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle admin input for managing freebies.

    The expected formats are:
      - ``<product_id> <channel_username>`` to mark a product as free and require users to join the specified channel.  The channel username
        may optionally start with ``@``; it will be stripped automatically.
      - ``off <product_id>`` to disable the free status for the given product.

    Any errors or invalid formats result in a usage message being sent.  After
    processing, the handler returns to the admin panel.
    """
    if not admin.is_admin(update.effective_user.id):
        return ConversationHandler.END
    text = (update.message.text or "").strip()
    if not text:
        await update.message.reply_text(
            "❌ Invalid format. Use: `<product_id> <channel_username>` or `off <product_id>`",
            reply_markup=utils.admin_main_keyboard(),
            parse_mode='Markdown'
        )
        return ConversationHandler.END
    parts = text.split()
    # Remove leading '@' from channel if present
    def clean_channel(ch):
        return ch.lstrip('@')
    if parts[0].lower() == 'off':
        # Off command to disable freebies
        if len(parts) < 2:
            await update.message.reply_text(
                "❌ Usage: off <product_id>",
                reply_markup=utils.admin_main_keyboard(),
                parse_mode='Markdown'
            )
            return ConversationHandler.END
        try:
            product_id = int(parts[1])
        except ValueError:
            await update.message.reply_text(
                "❌ Product ID must be a number.",
                reply_markup=utils.admin_main_keyboard(),
                parse_mode='Markdown'
            )
            return ConversationHandler.END
        msg = admin.unset_freebie(product_id)
        await update.message.reply_text(msg, reply_markup=utils.admin_main_keyboard(), parse_mode='Markdown')
        return ConversationHandler.END
    # Otherwise expect product_id and channel username
    if len(parts) < 2:
        await update.message.reply_text(
            "❌ Invalid format. Use: `<product_id> <channel_username>`",
            reply_markup=utils.admin_main_keyboard(),
            parse_mode='Markdown'
        )
        return ConversationHandler.END
    try:
        product_id = int(parts[0])
    except ValueError:
        await update.message.reply_text(
            "❌ Product ID must be a number.",
            reply_markup=utils.admin_main_keyboard(),
            parse_mode='Markdown'
        )
        return ConversationHandler.END
    channel = clean_channel(parts[1])
    msg = admin.set_freebie(product_id, channel)
    await update.message.reply_text(msg, reply_markup=utils.admin_main_keyboard(), parse_mode='Markdown')
    return ConversationHandler.END


# ══════════════════════════════════════════════════════════
#   OLD ADMIN COMMANDS
# ══════════════════════════════════════════════════════════

async def cmd_addproduct_data(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not admin.is_admin(update.effective_user.id):
        return
    try:
        data = update.message.text.replace('/addproduct_data ', '').split(' | ')
        if len(data) != 6:
            await update.message.reply_text("Usage: `/addproduct_data Name | Duration | Price | Description | Note | Sticker Emoji ID`", parse_mode='Markdown')
            return
        msg = admin.add_product_admin(data[0], data[1], float(data[2]), data[3], data[4], data[5])
        await update.message.reply_text(msg, parse_mode='Markdown')
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {e}")


async def cmd_additems(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not admin.is_admin(update.effective_user.id):
        return

    try:
        raw = update.message.text.replace('/additems ', '', 1)
        stock_sections = admin.parse_stock_bulk_format(raw)
        result = admin.add_stock_bulk_admin(stock_sections)

        if isinstance(result, tuple):
            msg, products_to_broadcast = result
        else:
            msg = result
            products_to_broadcast = []

        await update.message.reply_text(msg, parse_mode='Markdown')

        sent, total = await broadcast_stock_updates(context, products_to_broadcast)

        if products_to_broadcast:
            await update.message.reply_text(f"📢 Stock update notification sent to {sent}/{total} users.")

    except Exception as e:
        logger.exception(f"[CMD ADDITEMS] Error: {e}")
        await update.message.reply_text(f"❌ Error: {e}")


async def cmd_editprice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not admin.is_admin(update.effective_user.id):
        return
    try:
        msg = admin.edit_product_price(int(context.args[0]), float(context.args[1]))
        await update.message.reply_text(msg, parse_mode='Markdown')
    except Exception:
        await update.message.reply_text("Usage: `/editprice <id> <price>`", parse_mode='Markdown')


async def cmd_editstock(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not admin.is_admin(update.effective_user.id):
        return
    try:
        msg = admin.edit_product_stock(int(context.args[0]), int(context.args[1]))
        await update.message.reply_text(msg, parse_mode='Markdown')
    except Exception:
        await update.message.reply_text("Usage: `/editstock <id> <stock>`", parse_mode='Markdown')


async def cmd_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not admin.is_admin(update.effective_user.id):
        return
    msg_text = update.message.text.replace('/broadcast ', '', 1)
    users = database.get_all_users()
    sent = 0
    for user in users:
        try:
            await context.bot.send_message(chat_id=user[0], text=msg_text)
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
        await context.bot.send_message(chat_id=uid, text=f"✅ Your wallet credited with *{amount} USDT*!", parse_mode='Markdown')
    except Exception:
        await update.message.reply_text("Usage: `/addbalance <user_id> <amount>`", parse_mode='Markdown')


async def cmd_approve(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not admin.is_admin(update.effective_user.id):
        return
    try:
        msg = admin.approve_withdrawal_admin(int(context.args[0]))
        await update.message.reply_text(msg, parse_mode='Markdown')
    except Exception:
        await update.message.reply_text("Usage: `/approve <withdrawal_id>`", parse_mode='Markdown')


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

    # Define a reply filter that matches only the visible menu buttons.  The
    # "Order Details" option has been removed from the main menu, so it
    # is intentionally omitted here.
    reply_filter = (
        filters.TEXT & ~filters.COMMAND &
        filters.Regex(r'^(🛍️ Products|👤 Profile|📜 Purchase History|💰 Wallet|🆘 Support)$')
    )
    application.add_handler(MessageHandler(reply_filter, reply_keyboard_handler))

    conv_handler = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(admin_button_handler, pattern='^admin_'),
            CallbackQueryHandler(button_handler),
        ],
        states={
            QUANTITY: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_quantity)],
            WITHDRAW_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_withdraw_amount)],
            WITHDRAW_ADDRESS: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_withdraw_address)],
            CONTACT_ADMIN: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_contact_admin)],
            BINANCE_ORDER_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_binance_order_id)],
            WALLET_DEPOSIT_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_wallet_deposit_amount)],
            WALLET_DEPOSIT_REF: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_wallet_deposit_ref)],
            ORDER_DETAILS: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_order_details)],
            ADMIN_ORDER_DETAILS: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_admin_order_details)],
            ADMIN_ADD_PRODUCT: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_admin_add_product)],
            ADMIN_BULK_ADD_PRODUCTS: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_admin_bulk_add_products)],
            ADMIN_ADD_ITEMS: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_admin_add_items)],
            ADMIN_EDIT_PRICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_admin_edit_price)],
            ADMIN_EDIT_STOCK: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_admin_edit_stock)],
            ADMIN_ADD_BALANCE: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_admin_add_balance)],
            ADMIN_APPROVE_WITHDRAWAL: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_admin_approve_withdrawal)],
            ADMIN_BROADCAST: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_admin_broadcast)],
            ADMIN_DELETE_PRODUCT: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_admin_delete_product)],
            ADMIN_EDIT_DETAILS: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_admin_edit_details)],
            ADMIN_EDIT_CREDENTIALS: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_admin_edit_credentials)],
            ADMIN_SET_FREEBIE: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_admin_set_freebie)],
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