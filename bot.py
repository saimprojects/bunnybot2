"""
Main module for the Telegram shop bot.

This script wires together the database, utils, products and admin
modules with the python‑telegram‑bot library to create a functional
shop bot.  It supports browsing products, claiming freebies, basic
wallet information and a minimal admin panel.  Broadcasts and
freebie management are implemented via a simple conversation with
the admin.

To run the bot locally set the ``TOKEN`` and optionally ``ADMIN_ID``
environment variables then execute:

```
python3 -m final_bot_final.bot
```

The bot will create a ``shop.db`` database file in the working
directory unless ``SHOP_DB_PATH`` is set.
"""

import logging
import json
from html import escape as html_escape
from telegram import Update, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
    ContextTypes,
    ConversationHandler,
)

import config
import database
import admin as admin_module
import utils
import products as product_module


# Initialize logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)



def ce(name: str, fallback: str = " ") -> str:
    """Return Telegram custom emoji tag for a key from utils.EMOJIS."""
    emoji_id = getattr(utils, "EMOJIS", {}).get(name, "")
    if not emoji_id:
        return fallback
    return f'<tg-emoji emoji-id="{emoji_id}">{fallback}</tg-emoji>'


# Conversation state for admin input
ADMIN_AWAITING_INPUT = 1


def init_environment():
    """Initialize the database and log configuration values."""
    database.init_db()
    logger.info("Database initialized at %s", database.DATABASE_NAME)
    if config.ADMIN_ID:
        logger.info("Admin ID set to %s", config.ADMIN_ID)
    else:
        logger.warning("ADMIN_ID not set; admin functions disabled")


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the /start command or start callback to show the main menu."""
    user = update.effective_user
    # Create user in DB if not exist
    if user:
        database.create_user(user.id, user.username or "")
    welcome = (
        f"{ce('welcome_star')} <b>Welcome {html_escape(user.first_name if user else '')}!</b>\n\n"
        f"{ce('choose_option')} Please choose an option from the menu below."
    )
    # Use send_message instead of edit to avoid message not modified errors
    if update.message:
        await update.message.reply_html(welcome, reply_markup=utils.main_menu_keyboard())
    elif update.callback_query:
        await update.callback_query.message.reply_html(welcome, reply_markup=utils.main_menu_keyboard())


async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Dispatch callback queries to the appropriate handler."""
    query = update.callback_query
    await query.answer()
    data = query.data
    user_id = query.from_user.id
    logger.info("Callback data: %s from user %s", data, user_id)

    # Main menu items
    if data == 'main_menu':
        await query.message.reply_html("Returning to main menu.", reply_markup=utils.main_menu_keyboard())
        return
    if data == 'products':
        products_list = database.get_all_products()
        if products_list:
            await query.message.reply_html(
                f"{ce('products')} <b>Available Products:</b>",
                reply_markup=utils.products_list_keyboard(products_list)
            )
        else:
            await query.message.reply_html(
                f"{ce('cancel')} No products available right now.",
                reply_markup=utils.main_menu_keyboard()
            )
        return
    if data.startswith('product_'):
        try:
            pid = int(data.split('_')[1])
        except Exception:
            await query.message.reply_html(
                f"{ce('cancel')} Invalid product ID.",
                reply_markup=utils.main_menu_keyboard()
            )
            return
        product = database.get_product(pid)
        if not product:
            await query.message.reply_html(
                f"{ce('cancel')} Product not found.",
                reply_markup=utils.main_menu_keyboard()
            )
            return
        # Store current product for this user for subsequent actions
        context.user_data['current_product_id'] = pid
        details = product_module.get_product_details_message(pid)
        kb = utils.product_details_keyboard(product)
        await query.message.reply_html(details, reply_markup=kb)
        return
    if data == 'order_now':
        # For simplicity we allow only quantity 1 orders.  In a full
        # implementation you would ask the user for quantity and
        # payment method.  Here we show a message that ordering is
        # disabled for now and return to main menu.
        await query.message.reply_html(
            f"{ce('cancel')} Ordering is currently disabled in this demo.",
            reply_markup=utils.main_menu_keyboard()
        )
        return
    if data == 'claim_free':
        pid = context.user_data.get('current_product_id')
        if not pid:
            await query.message.reply_html(
                f"{ce('cancel')} No product selected.",
                reply_markup=utils.main_menu_keyboard()
            )
            return
        product = database.get_product(pid)
        if not product or (len(product) <= 10 or not product[10]):
            await query.message.reply_html(
                f"{ce('cancel')} This product is not free.",
                reply_markup=utils.main_menu_keyboard()
            )
            return
        # If free_channel is set, verify membership
        free_channel = None
        if len(product) > 11:
            free_channel = product[11]
        if free_channel:
            try:
                member = await context.bot.get_chat_member(f"@{free_channel}", user_id)
                if member.status not in ('member', 'creator', 'administrator'):
                    # not a member
                    join_link = f"https://t.me/{free_channel}"
                    # Provide a button for user to re‑try after joining
                    join_kb = utils.build_menu([
                        utils.btn("I have joined", callback_data='claim_free', emoji_id=utils.EMOJIS['confirm'])
                    ], n_cols=1)
                    await query.message.reply_html(
                        f"{ce('warning')} Please join our channel first: <a href='{join_link}'>Join here</a>",
                        reply_markup=join_kb
                    )
                    return
            except Exception as e:
                logger.warning("Error checking channel membership: %s", e)
                # If we cannot verify membership we still proceed to deliver
                pass
        # Deliver free item
        items = database.get_unsold_items(pid, limit=1)
        if not items:
            await query.message.reply_html(
                f"{ce('cancel')} Sorry, this free product is out of stock.",
                reply_markup=utils.main_menu_keyboard()
            )
            return
        item = items[0]
        item_id = item[0]
        item_json = item[4]
        creds = {}
        try:
            creds = json.loads(item_json) if item_json else {}
        except Exception:
            creds = {}
        # Mark item as sold and create a zero price order
        database.mark_item_sold(item_id)
        order_id = utils.generate_order_id()
        database.create_order(order_id, user_id, pid, 1, 0.0, 'Freebie', 'Delivered', creds)
        database.increment_user_orders(user_id)
        # Build credentials message
        if isinstance(creds, dict) and creds:
            details_lines = [f"<b>{html_escape(k)}</b>: {html_escape(v)}" for k, v in creds.items()]
            details_msg = "\n".join(details_lines)
        else:
            details_msg = html_escape(str(item_json))
        await query.message.reply_html(
            f"{ce('confirm')} <b>Your free product has been delivered!</b>\n\n{details_msg}"
        )
        # Send a new start prompt
        await query.message.reply_html("Use /start to return to the main menu.")
        return
    if data == 'purchase_history':
        orders = database.get_user_orders(user_id)
        if not orders:
            await query.message.reply_html(
                f"{ce('cancel')} You have no purchase history.",
                reply_markup=utils.main_menu_keyboard()
            )
            return
        lines = [f"{ce('order')} <b>Your Purchase History:</b>", ""]
        for o in orders:
            oid, uid, pid, qty, total, method, status, date_str, delivery_json = o
            product = database.get_product(pid)
            product_name = product[1] if product else "Unknown"
            lines.append(
                f"Order <code>{oid}</code>: *{product_name}* x{qty} – {total} USDT – {status} – {date_str}"
            )
        await query.message.reply_html("\n".join(lines), reply_markup=utils.main_menu_keyboard())
        return
    if data == 'profile':
        user = database.get_user(user_id)
        if not user:
            await query.message.reply_html(
                f"{ce('cancel')} User not found.",
                reply_markup=utils.main_menu_keyboard()
            )
            return
        _, username, joined_date, wallet_balance, total_orders, referrals, referral_earnings = user
        msg = (
            f"{ce('profile')} <b>Your Profile</b>\n\n"
            f"{ce('id')} <b>ID:</b> {user_id}\n"
            f"{ce('username')} <b>Username:</b> @{html_escape(username) if username else 'N/A'}\n"
            f"{ce('date')} <b>Joined:</b> {joined_date}\n"
            f"{ce('wallet')} <b>Balance:</b> {wallet_balance} USDT\n"
            f"{ce('order')} <b>Total Orders:</b> {total_orders}\n"
            f"🎁 <b>Referrals:</b> {referrals}\n"
            f"💰 <b>Referral Earnings:</b> {referral_earnings} USDT"
        )
        await query.message.reply_html(msg, reply_markup=utils.main_menu_keyboard())
        return
    if data == 'wallet':
        user = database.get_user(user_id)
        if not user:
            await query.message.reply_html(
                f"{ce('cancel')} User not found.",
                reply_markup=utils.main_menu_keyboard()
            )
            return
        _, _, _, balance, total_orders, referrals, referral_earnings = user
        msg = (
            f"{ce('wallet')} <b>Your Wallet</b>\n\n"
            f"Balance: {balance} USDT\n"
            f"Referral Earnings: {referral_earnings} USDT\n\n"
            "Deposits and withdrawals are not implemented in this demo."
        )
        await query.message.reply_html(msg, reply_markup=utils.main_menu_keyboard())
        return
    if data == 'support':
        await query.message.reply_html("Support options:", reply_markup=utils.support_keyboard())
        return

    # Admin panel entry
    if data == 'admin_panel_back':
        await query.message.reply_html("Admin panel:", reply_markup=utils.admin_main_keyboard())
        return
    if data.startswith('admin'):
        # Ensure user is admin
        if not admin_module.is_admin(user_id):
            await query.message.reply_html("❌ You are not authorized to access admin functions.")
            return
        if data == 'admin_view_products':
            msg = admin_module.get_all_products_admin()
            await query.message.reply_markdown(msg, reply_markup=utils.admin_main_keyboard())
            return
        if data == 'admin_view_all_orders':
            msg = admin_module.get_all_orders_admin(50)
            await query.message.reply_markdown(msg, reply_markup=utils.admin_main_keyboard())
            return
        if data == 'admin_view_stats':
            msg = admin_module.get_stats_admin()
            await query.message.reply_markdown(msg, reply_markup=utils.admin_main_keyboard())
            return
        if data == 'admin_set_freebie':
            context.user_data['awaiting_admin_input'] = True
            context.user_data['admin_action'] = 'set_freebie'
            await query.message.reply_html(
                "Send the product ID and channel (without @) separated by space.\n"
                "For example: <code>12 mychannel</code> or <code>12 none</code> to remove channel and mark free without channel.\n"
                "Send just the product ID to unset the freebie.",
                reply_markup=utils.admin_cancel_keyboard()
            )
            return
        if data == 'admin_broadcast':
            context.user_data['awaiting_admin_input'] = True
            context.user_data['admin_action'] = 'broadcast'
            await query.message.reply_html(
                "Send the broadcast message you wish to send to all users.\n"
                "You can embed custom emojis using [emoji_id] notation.",
                reply_markup=utils.admin_cancel_keyboard()
            )
            return
        # Unknown admin action
        await query.message.reply_html("Unknown admin action.", reply_markup=utils.admin_main_keyboard())
        return

    # Fallback: unhandled callback
    await query.message.reply_html("Unknown action.")


async def handle_admin_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle text input from admin when awaiting input for an admin action."""
    user_id = update.effective_user.id
    if not admin_module.is_admin(user_id):
        return ConversationHandler.END
    if not context.user_data.get('awaiting_admin_input'):
        return ConversationHandler.END
    action = context.user_data.get('admin_action')
    text = update.message.text.strip()
    if action == 'set_freebie':
        parts = text.split()
        if not parts:
            await update.message.reply_html("Please provide product ID and channel or 'none'.", reply_markup=utils.admin_main_keyboard())
            context.user_data['awaiting_admin_input'] = False
            return ConversationHandler.END
        try:
            pid = int(parts[0])
        except Exception:
            await update.message.reply_html("Invalid product ID.", reply_markup=utils.admin_main_keyboard())
            context.user_data['awaiting_admin_input'] = False
            return ConversationHandler.END
        channel = None
        if len(parts) > 1:
            ch = parts[1]
            if ch.lower() != 'none':
                channel = ch.lstrip('@')
        # If only product ID provided and no channel specified -> unset freebie
        if len(parts) == 1:
            result = admin_module.unset_freebie(pid)
        else:
            result = admin_module.set_freebie(pid, channel)
        await update.message.reply_html(result, reply_markup=utils.admin_main_keyboard())
        context.user_data['awaiting_admin_input'] = False
        return ConversationHandler.END
    if action == 'broadcast':
        # Parse custom emoji markup
        raw_msg = text
        msg = product_module.format_with_custom_emojis(raw_msg)
        users = database.get_all_users()
        sent = 0
        for u in users:
            chat_id = u[0]
            try:
                await context.bot.send_message(chat_id=chat_id, text=msg)
                sent += 1
            except Exception as e:
                logger.error("Broadcast failed for %s: %s", chat_id, e)
        await update.message.reply_html(
            f"✅ Broadcast sent to {sent} users.",
            reply_markup=utils.admin_main_keyboard()
        )
        context.user_data['awaiting_admin_input'] = False
        return ConversationHandler.END
    # Unknown admin action
    context.user_data['awaiting_admin_input'] = False
    return ConversationHandler.END


async def admin_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancel admin input."""
    context.user_data['awaiting_admin_input'] = False
    await update.message.reply_html("Admin action cancelled.", reply_markup=utils.admin_main_keyboard())
    return ConversationHandler.END


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Log errors without crashing the bot."""
    logger.exception("Exception while handling an update:", exc_info=context.error)
    try:
        if update and getattr(update, "effective_chat", None):
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text="Something went wrong. Please try /start again."
            )
    except Exception:
        pass



def main() -> None:
    init_environment()
    if not config.TOKEN:
        raise RuntimeError("TOKEN is not set in environment")
    application = ApplicationBuilder().token(config.TOKEN).build()

    # Start command
    application.add_handler(CommandHandler('start', start))
    # Callback queries
    application.add_handler(CallbackQueryHandler(handle_callback))

    # Admin text input handler.
    # Admin check is inside handle_admin_input(), so no filters.USER() is needed.
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_admin_input))
    application.add_error_handler(error_handler)

    logger.info("Starting bot...")
    application.run_polling()


if __name__ == '__main__':
    main()
