import logging
import datetime
import json
import re
from html import escape as html_escape
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram.ext import (
    ApplicationBuilder, CommandHandler, CallbackQueryHandler,
    MessageHandler, filters, ContextTypes, ConversationHandler
)

import config
import database
import admin
import utils
import payment
import products as products_helper

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# States
(
    QUANTITY,
    BINANCE_ORDER_ID,
    DEPOSIT_TX_ID,
    WALLET_DEPOSIT_AMOUNT,
    ORDER_DETAILS,
    ADMIN_ORDER_DETAILS,
    ADMIN_ADD_PRODUCT,
    ADMIN_BULK_ADD_PRODUCTS,
    ADMIN_ADD_ITEMS,
    ADMIN_EDIT_PRICE,
    ADMIN_EDIT_STOCK,
    ADMIN_EDIT_PRODUCT_DETAILS_ID,
    ADMIN_EDIT_PRODUCT_DETAILS_APPLY,
    ADMIN_EDIT_STOCK_DETAILS_ID,
    ADMIN_EDIT_STOCK_DETAILS_APPLY,
    ADMIN_ADD_BALANCE,
    ADMIN_APPROVE_WITHDRAWAL,
    ADMIN_BROADCAST,
    ADMIN_DELETE_PRODUCT,
    ADMIN_SETUP_FREEBIES,
    ADMIN_TOGGLE_FREEBIE,
    ADMIN_FREEBIE_STOCK,
) = range(22)


def ce(name: str, fallback: str = None) -> str:
    return utils.ce(name, fallback)


def build_start_message() -> str:
    star = ce('welcome_star')
    diamond = ce('diamond')
    stats = ce('stats')
    products = ce('products')
    wallet = ce('wallet')
    profile = ce('profile')
    support = ce('support')
    choose = ce('choose_option')
    return (
        f"{star} <b>Bunny Tools Premium</b> {star}\n\n"
        f"{diamond} <b>Premium Digital Products with Instant Delivery</b> {diamond}\n"
        f"{stats} <b>Fast - Secure - Automated</b> {stats}\n\n"
        f"{products} <b>Products</b>\n"
        f"{wallet} <b>Wallet</b>\n"
        f"{profile} <b>Profile</b>\n"
        f"{support} <b>Support</b>\n\n"
        f"{choose} <b>Choose an option below</b>"
    )


def parse_positive_amount(text):
    amount = float(str(text).strip())
    if amount <= 0:
        raise ValueError("Amount must be greater than 0.")
    return amount


def wallet_deposit_amount_prompt():
    return (
        f"{ce('wallet')} <b>Wallet Deposit</b>\n\n"
        "Send the USDT amount you want to add.\n\n"
        "<b>Example:</b>\n"
        "<code>4</code>"
    )


def html_code_lines(data):
    return "\n".join(
        f"{html_escape(str(k))}: <code>{html_escape(str(v))}</code>"
        for k, v in data.items()
    )


def get_freebies_channel_target():
    raw_target = str(getattr(config, "FREEBIES_CHANNEL_ID", "") or "").strip()
    if raw_target:
        if raw_target.lstrip("-").isdigit():
            return int(raw_target)
        return raw_target

    cfg = database.get_freebies_config()
    if cfg and cfg[1]:
        return int(cfg[1])

    link = str(getattr(config, "FREEBIES_CHANNEL_LINK", "") or (cfg[2] if cfg else "") or "").strip()
    if "t.me/" in link and "+" not in link and "joinchat" not in link:
        username = link.rstrip("/").split("/")[-1]
        if username:
            return f"@{username}" if not username.startswith("@") else username

    return None


async def has_joined_freebies_channel(context: ContextTypes.DEFAULT_TYPE, user_id: int) -> bool:
    target = get_freebies_channel_target()
    if not target:
        return True

    try:
        member = await context.bot.get_chat_member(chat_id=target, user_id=user_id)
        return member.status in ("member", "administrator", "creator")
    except Exception:
        return False


def build_stock_update_message(product, added_count, title="Stock Update"):
    product_icon = products_helper.get_product_icon(product[9] if len(product) > 9 else None)
    sold_count = database.get_product_sold_count(product[0])
    return (
        f"{product_icon} <b>{html_escape(title)}</b>\n\n"
        f"{product_icon} <b>Product:</b> {html_escape(str(product[1]))}\n"
        f"{ce('wallet')} <b>Price:</b> {html_escape(str(product[3]))} USDT\n"
        f"{ce('box')} <b>Stock Available:</b> {html_escape(str(product[4]))}\n"
        f"{ce('stats')} <b>Sold:</b> {html_escape(str(sold_count))} accounts\n"
        f"{ce('confirm')} <b>Added Now:</b> {html_escape(str(added_count))}"
    )


async def notify_stock_updates(context: ContextTypes.DEFAULT_TYPE, stock_sections, require_freebie=False):
    users = database.get_all_users()
    sent = 0
    attempts = 0

    for product_id, items_data in stock_sections:
        added_count = len(items_data)
        if added_count <= 0:
            continue

        product = database.get_product(product_id)
        if not product:
            continue

        is_freebie = product[10] if len(product) > 10 else False
        if require_freebie and not is_freebie:
            continue

        title = "Freebie Stock Update" if is_freebie else "Stock Update"
        text = build_stock_update_message(product, added_count, title=title)
        markup = utils.product_update_purchase_keyboard(product)

        for user in users:
            attempts += 1
            try:
                await context.bot.send_message(user[0], text, reply_markup=markup, parse_mode='HTML')
                sent += 1
            except Exception:
                pass

    return f"Stock notifications sent to {sent}/{attempts} users."


# =============================================================================
#   START & MENU
# =============================================================================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = update.effective_user
    db_user = database.get_user(user.id)
    if not db_user:
        database.create_user(user.id, user.username)
        if context.args and context.args[0].startswith('ref_'):
            try:
                ref_id = int(context.args[0].split('_')[1])
                if ref_id != user.id:
                    database.add_referral(ref_id)
            except Exception:
                pass

    text = build_start_message()
    markup = utils.main_menu_keyboard()
    if update.callback_query:
        await update.callback_query.edit_message_text(text, reply_markup=markup, parse_mode='HTML')
    else:
        await update.message.reply_text(text, reply_markup=markup, parse_mode='HTML')
    return ConversationHandler.END


async def show_profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = database.get_user(update.effective_user.id)
    bot = (await context.bot.get_me()).username
    text = (
        f"{ce('profile')} <b>My Profile</b>\n\n"
        f"{ce('id')} ID: <code>{user[0]}</code>\n"
        f"{ce('username')} User: @{html_escape(user[1] or 'N/A')}\n"
        f"{ce('date')} Joined: {html_escape(str(user[2]))}\n\n"
        f"{ce('wallet')} Balance: <b>{html_escape(str(user[3]))} USDT</b>\n"
        f"{ce('box')} Orders: {html_escape(str(user[4]))}\n"
        f"{ce('users')} Referrals: {html_escape(str(user[5]))} ({html_escape(str(user[6]))} USDT earned)\n\n"
        f"{ce('link')} <b>Referral Link:</b>\n<code>t.me/{html_escape(str(bot))}?start=ref_{user[0]}</code>"
    )
    await update.callback_query.edit_message_text(text, reply_markup=utils.main_menu_keyboard(), parse_mode='HTML')


async def show_history(update: Update, context: ContextTypes.DEFAULT_TYPE):
    orders = database.get_user_orders(update.effective_user.id)
    if not orders:
        text = f"{ce('no_orders')} You have no orders yet."
    else:
        text = f"{ce('order_details')} <b>Purchase History</b>\n\n"
        for o in orders[:10]:
            p = database.get_product(o[2])
            text += (
                f"<b>Order #{o[0]}</b>\n"
                f"{html_escape(p[1] if p else 'N/A')}\n"
                f"{o[3]} qty | {o[4]} USDT | {o[6]}\n"
                f"{utils.DIVIDER}\n"
            )
    await update.callback_query.edit_message_text(text, reply_markup=utils.main_menu_keyboard(), parse_mode='HTML')


async def emoji_test(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not admin.is_admin(update.effective_user.id):
        return

    lines = ["<b>Custom Emoji Test</b>", ""]
    for name, (emoji_id, _) in utils.EMOJIS.items():
        lines.append(f"{ce(name)} <code>{html_escape(name)}</code> - <code>{html_escape(str(emoji_id))}</code>")

    await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.HTML)


# =============================================================================
#   CALLBACK HANDLER
# =============================================================================

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    data = query.data
    uid = update.effective_user.id
    await query.answer()

    if data == 'main_menu':
        return await start(update, context)
    if data == 'profile':
        await show_profile(update, context)
        return ConversationHandler.END
    if data == 'purchase_history':
        await show_history(update, context)
        return ConversationHandler.END

    if data == 'products':
        ps = database.get_all_products()
        await query.edit_message_text(f"{ce('products')} <b>Available Products:</b>", reply_markup=utils.products_list_keyboard(ps), parse_mode=ParseMode.HTML)
        return ConversationHandler.END

    if data == 'wallet':
        user = database.get_user(uid)
        txs = database.get_user_transactions(uid)
        msg = f"{ce('wallet')} <b>My Wallet</b>\n\nBalance: <b>{user[3]} USDT</b>\n\n<b>Recent Transactions:</b>\n"
        if not txs:
            msg += "No transactions found.\n"
        else:
            for t in txs[:5]:
                msg += f"{'+' if t[3] > 0 else ''}{t[3]} USDT | {t[2]} | {str(t[4]).split(' ')[0]}\n"
        await query.edit_message_text(msg, reply_markup=utils.wallet_options_keyboard(), parse_mode='HTML')
        return ConversationHandler.END

    if data == 'support':
        text = f"{ce('support_center')} <b>Support Center</b>\n\nContact: @Bunnyhaccks\nChannel: @bunnyhackss"
        await query.edit_message_text(text, reply_markup=utils.support_keyboard(), parse_mode='HTML')
        return ConversationHandler.END

    if data == 'faq':
        await query.edit_message_text(f"{ce('question')} <b>FAQ</b>\n\nInstant delivery after payment. For help, contact @Bunnyhaccks.", reply_markup=utils.support_keyboard(), parse_mode=ParseMode.HTML)
        return ConversationHandler.END

    if data == 'deposit_wallet':
        context.user_data.pop('wallet_deposit_amount', None)
        await query.edit_message_text(wallet_deposit_amount_prompt(), reply_markup=utils.wallet_deposit_amount_keyboard(), parse_mode='HTML')
        return WALLET_DEPOSIT_AMOUNT

    if data == 'check_deposit_payment':
        await query.edit_message_text("Send your <b>Transaction ID / Reference ID</b>:", parse_mode='HTML')
        return DEPOSIT_TX_ID

    if data == 'order_details':
        await query.edit_message_text(f"{ce('order_details')} Send your <b>Order ID</b>:", parse_mode=ParseMode.HTML)
        return ORDER_DETAILS

    if data == 'freebies':
        cfg = database.get_freebies_config()
        if not cfg[3]:
            await query.answer("Disabled.", show_alert=True)
            return ConversationHandler.END
        await query.edit_message_text(f"{ce('gift')} <b>Freebies</b>", reply_markup=utils.freebies_keyboard(database.get_freebie_products(), cfg), parse_mode=ParseMode.HTML)
        return ConversationHandler.END

    if data.startswith('claim_freebie_'):
        pid = int(data.split('_')[2])
        if not await has_joined_freebies_channel(context, uid):
            await query.answer("Join the channel first.", show_alert=True)
            return ConversationHandler.END
        if database.has_user_received_freebie(uid, pid):
            await query.answer("Already claimed!", show_alert=True)
            return ConversationHandler.END
        context.user_data.update({'current_product_id': pid, 'quantity': 1, 'total_amount': 0})
        await deliver_product(update, context, 'Freebie')
        return ConversationHandler.END

    if data.startswith('product_'):
        pid = int(data.split('_')[1])
        context.user_data['current_product_id'] = pid
        await query.edit_message_text(products_helper.get_product_details_message(pid), reply_markup=utils.product_details_keyboard(), parse_mode='HTML')
        return ConversationHandler.END

    if data == 'order_now':
        pid = context.user_data.get('current_product_id')
        p = database.get_product(pid)
        if not p or p[4] <= 0:
            await query.answer("Out of stock!", show_alert=True)
            return ConversationHandler.END
        await query.edit_message_text(f"{ce('order')} <b>{html_escape(str(p[1]))}</b>\n\nQuantity (1-{p[4]}):", reply_markup=utils.quantity_selection_keyboard(), parse_mode=ParseMode.HTML)
        return QUANTITY

    if data == 'back_to_product_details':
        pid = context.user_data.get('current_product_id')
        if not pid:
            return await start(update, context)
        await query.edit_message_text(products_helper.get_product_details_message(pid), reply_markup=utils.product_details_keyboard(), parse_mode='HTML')
        return ConversationHandler.END

    if data == 'back_to_quantity':
        pid = context.user_data.get('current_product_id')
        p = database.get_product(pid)
        if not p:
            return await start(update, context)
        await query.edit_message_text(f"{ce('quantity')} <b>{html_escape(str(p[1]))}</b>\n\nQuantity (1-{p[4]}):", reply_markup=utils.quantity_selection_keyboard(), parse_mode=ParseMode.HTML)
        return QUANTITY

    if data == 'back_to_payment_method':
        qty = context.user_data.get('quantity')
        total = context.user_data.get('total_amount')
        pid = context.user_data.get('current_product_id')
        p = database.get_product(pid)
        if not p or not qty or total is None:
            return await start(update, context)
        text = (
            f"{ce('confirm')} <b>Order Summary</b>\n\n"
            f"Product: {html_escape(str(p[1]))}\n"
            f"Qty: {qty}\n"
            f"Total: <b>{total} USDT</b>\n\n"
            f"Select Payment:"
        )
        await query.edit_message_text(text, reply_markup=utils.payment_method_keyboard(), parse_mode='HTML')
        return ConversationHandler.END

    if data == 'pay_binance':
        total = context.user_data.get('total_amount')
        await query.edit_message_text(payment.get_binance_payment_details(total), reply_markup=utils.binance_payment_keyboard(), parse_mode='HTML')
        return ConversationHandler.END

    if data == 'check_binance_payment':
        await query.edit_message_text("Send your <b>Transaction ID / Reference ID</b>:", parse_mode='HTML')
        return BINANCE_ORDER_ID

    if data == 'pay_wallet':
        total = context.user_data.get('total_amount')
        user = database.get_user(uid)
        markup = utils.wallet_payment_keyboard() if user[3] >= total else utils.insufficient_balance_keyboard()
        await query.edit_message_text(payment.get_wallet_payment_summary(uid, total), reply_markup=markup, parse_mode='HTML')
        return ConversationHandler.END

    if data == 'confirm_wallet_payment':
        pid = context.user_data.get('current_product_id')
        qty = context.user_data.get('quantity')
        total = context.user_data.get('total_amount')
        if not pid or not qty or len(database.get_unsold_items(pid, qty)) < qty:
            await query.edit_message_text(f"{ce('cancel')} Stock mismatch. Contact support.", reply_markup=utils.main_menu_keyboard(), parse_mode=ParseMode.HTML)
            return ConversationHandler.END
        success, msg = payment.process_wallet_payment(uid, None, pid, qty, total)
        if success:
            await deliver_product(update, context, 'Wallet')
        else:
            await query.edit_message_text(msg, reply_markup=utils.main_menu_keyboard(), parse_mode='HTML')
        return ConversationHandler.END

    if data == 'cancel_order':
        return await start(update, context)
    return ConversationHandler.END


# =============================================================================
#   ADMIN CALLBACKS
# =============================================================================

async def admin_button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    if not admin.is_admin(update.effective_user.id):
        return ConversationHandler.END
    await query.answer()
    data = query.data

    if data == 'admin_panel_back':
        await query.edit_message_text(f"{ce('admin')} <b>Admin Panel</b>", reply_markup=utils.admin_main_keyboard(), parse_mode=ParseMode.HTML)
        return ConversationHandler.END
    if data == 'admin_view_stats':
        await query.edit_message_text(admin.get_stats_admin(), reply_markup=utils.admin_back_keyboard(), parse_mode=ParseMode.HTML)
    elif data == 'admin_view_products':
        await query.edit_message_text(admin.get_all_products_admin(), reply_markup=utils.admin_back_keyboard(), parse_mode=ParseMode.HTML)
    elif data == 'admin_view_all_orders':
        await query.edit_message_text(admin.get_all_orders_admin(), reply_markup=utils.admin_back_keyboard(), parse_mode=ParseMode.HTML)
    elif data == 'admin_withdraw_requests':
        await query.edit_message_text(admin.get_withdrawal_requests_admin(), reply_markup=utils.admin_back_keyboard(), parse_mode=ParseMode.HTML)
    elif data == 'admin_order_details':
        await query.edit_message_text(admin.guide_order_details(), reply_markup=utils.admin_cancel_keyboard(), parse_mode='HTML')
        return ADMIN_ORDER_DETAILS
    elif data == 'admin_add_product':
        await query.edit_message_text(admin.guide_add_product(), reply_markup=utils.admin_cancel_keyboard(), parse_mode='HTML')
        return ADMIN_ADD_PRODUCT
    elif data == 'admin_bulk_add_products':
        await query.edit_message_text(admin.guide_bulk_products(), reply_markup=utils.admin_cancel_keyboard(), parse_mode='HTML')
        return ADMIN_BULK_ADD_PRODUCTS
    elif data == 'admin_add_items':
        await query.edit_message_text(admin.guide_add_stock(), reply_markup=utils.admin_cancel_keyboard(), parse_mode='HTML')
        return ADMIN_ADD_ITEMS
    elif data == 'admin_edit_product_details':
        await query.edit_message_text(
            "<b>Edit Product Details</b>\n\nSend the Product ID first.\n\n<b>Example:</b>\n<code>1</code>",
            reply_markup=utils.admin_cancel_keyboard(),
            parse_mode='HTML'
        )
        return ADMIN_EDIT_PRODUCT_DETAILS_ID
    elif data == 'admin_edit_stock_details':
        await query.edit_message_text(
            "<b>Edit Stock Details</b>\n\nSend the Product ID first.\n\n<b>Example:</b>\n<code>1</code>",
            reply_markup=utils.admin_cancel_keyboard(),
            parse_mode='HTML'
        )
        return ADMIN_EDIT_STOCK_DETAILS_ID
    elif data == 'admin_edit_price':
        await query.edit_message_text(admin.guide_edit_price(), reply_markup=utils.admin_cancel_keyboard(), parse_mode='HTML')
        return ADMIN_EDIT_PRICE
    elif data == 'admin_edit_stock':
        await query.edit_message_text(admin.guide_edit_stock_count(), reply_markup=utils.admin_cancel_keyboard(), parse_mode='HTML')
        return ADMIN_EDIT_STOCK
    elif data == 'admin_add_balance':
        await query.edit_message_text(admin.guide_add_balance(), reply_markup=utils.admin_cancel_keyboard(), parse_mode='HTML')
        return ADMIN_ADD_BALANCE
    elif data == 'admin_approve_withdrawal':
        await query.edit_message_text(admin.guide_approve_withdrawal(), reply_markup=utils.admin_cancel_keyboard(), parse_mode='HTML')
        return ADMIN_APPROVE_WITHDRAWAL
    elif data == 'admin_broadcast':
        await query.edit_message_text(admin.guide_broadcast(), reply_markup=utils.admin_cancel_keyboard(), parse_mode='HTML')
        return ADMIN_BROADCAST
    elif data == 'admin_delete_product':
        await query.edit_message_text(admin.guide_delete_product(), reply_markup=utils.admin_cancel_keyboard(), parse_mode='HTML')
        return ADMIN_DELETE_PRODUCT
    elif data == 'admin_freebies_settings':
        await query.edit_message_text(admin.get_freebies_settings_admin(), reply_markup=utils.admin_back_keyboard(), parse_mode=ParseMode.HTML)
        return ADMIN_SETUP_FREEBIES
    elif data == 'admin_freebie_products':
        await query.edit_message_text(admin.get_freebie_products_admin(), reply_markup=utils.admin_back_keyboard(), parse_mode=ParseMode.HTML)
        return ADMIN_TOGGLE_FREEBIE
    elif data == 'admin_freebie_stock':
        await query.edit_message_text(admin.guide_freebie_stock(), reply_markup=utils.admin_cancel_keyboard(), parse_mode='HTML')
        return ADMIN_FREEBIE_STOCK
    return ConversationHandler.END


# =============================================================================
#   INPUT HANDLERS
# =============================================================================

async def handle_quantity(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    try:
        qty = int(update.message.text)
        pid = context.user_data.get('current_product_id')
        p = database.get_product(pid)
        if not p or qty <= 0 or qty > p[4]:
            await update.message.reply_text(f"{ce('cancel')} Invalid. Max: {p[4] if p else 0}", parse_mode=ParseMode.HTML)
            return QUANTITY
        context.user_data.update({'quantity': qty, 'total_amount': p[3] * qty})
        text = (
            f"{ce('confirm')} <b>Order Summary</b>\n\n"
            f"Product: {html_escape(str(p[1]))}\n"
            f"Qty: {qty}\n"
            f"Total: <b>{context.user_data['total_amount']} USDT</b>\n\n"
            f"Select Payment:"
        )
        await update.message.reply_text(text, reply_markup=utils.payment_method_keyboard(), parse_mode=ParseMode.HTML)
        return ConversationHandler.END
    except Exception:
        await update.message.reply_text(f"{ce('cancel')} Send a valid number.", parse_mode=ParseMode.HTML)
        return QUANTITY


async def handle_order_details(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    o = database.get_order_by_id(update.message.text)
    if not o:
        await update.message.reply_text(f"{ce('cancel')} Not found.", parse_mode=ParseMode.HTML)
        return ConversationHandler.END
    p = database.get_product(o[2])
    text = (
        f"{ce('order_details')} <b>Order</b>\n\n"
        f"ID: <code>{o[0]}</code>\n"
        f"Product: {html_escape(str(p[1] if p else 'N/A'))}\n"
        f"Qty: {o[3]} | {o[4]} USDT | {o[6]}\n\n"
        f"<b>Delivery:</b>\n"
    )
    for i, item in enumerate(json.loads(o[8]), 1):
        text += f"\nItem #{i}:\n" + html_code_lines(item) + "\n"
    await update.message.reply_text(text, reply_markup=utils.main_menu_keyboard(), parse_mode='HTML')
    return ConversationHandler.END


async def handle_wallet_deposit_amount(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    try:
        amount = parse_positive_amount(update.message.text)
    except Exception:
        await update.message.reply_text(f"{ce('cancel')} Send a valid USDT amount greater than 0.", reply_markup=utils.wallet_deposit_amount_keyboard(), parse_mode=ParseMode.HTML)
        return WALLET_DEPOSIT_AMOUNT

    context.user_data['wallet_deposit_amount'] = amount
    await update.message.reply_text(payment.get_binance_payment_details(amount), reply_markup=utils.deposit_wallet_keyboard(), parse_mode='HTML')
    return ConversationHandler.END


async def handle_deposit_txid(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    amount = context.user_data.get('wallet_deposit_amount')
    if amount is None:
        await update.message.reply_text(wallet_deposit_amount_prompt(), reply_markup=utils.wallet_deposit_amount_keyboard(), parse_mode='HTML')
        return WALLET_DEPOSIT_AMOUNT

    success, msg = payment.process_wallet_deposit(update.effective_user.id, amount, update.message.text)
    await update.message.reply_text(msg, reply_markup=utils.main_menu_keyboard(), parse_mode='HTML')
    if success:
        context.user_data.pop('wallet_deposit_amount', None)
    return ConversationHandler.END


async def handle_binance_id(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    pid = context.user_data.get('current_product_id')
    qty = context.user_data.get('quantity')
    if not pid or not qty or len(database.get_unsold_items(pid, qty)) < qty:
        await update.message.reply_text(f"{ce('cancel')} Stock mismatch. Contact support.", reply_markup=utils.main_menu_keyboard(), parse_mode=ParseMode.HTML)
        return ConversationHandler.END

    success, msg = payment.process_binance_payment(
        update.effective_user.id,
        None,
        pid,
        qty,
        context.user_data.get('total_amount'),
        update.message.text
    )
    if success:
        await deliver_product(update, context, 'Binance')
    else:
        await update.message.reply_text(msg, parse_mode='HTML', reply_markup=utils.main_menu_keyboard())
    return ConversationHandler.END


async def deliver_product(update: Update, context: ContextTypes.DEFAULT_TYPE, method: str):
    pid = context.user_data.get('current_product_id')
    qty = context.user_data.get('quantity')
    items = database.get_unsold_items(pid, qty)
    if len(items) < qty:
        msg = update.callback_query.message if update.callback_query else update.message
        await msg.reply_text(f"{ce('cancel')} Stock mismatch. Contact support.", parse_mode=ParseMode.HTML)
        return
    data = [i['data'] for i in items]
    oid = utils.generate_order_id()
    database.create_order(oid, update.effective_user.id, pid, qty, context.user_data.get('total_amount'), method, 'Confirmed', data)
    database.mark_items_as_sold(pid, [i['id'] for i in items])
    database.update_product_stock(pid, -qty)
    p = database.get_product(pid)
    text = f"{ce('confirm')} <b>Delivered!</b>\n\nOrder: <code>{oid}</code>\nProduct: <b>{html_escape(str(p[1]))}</b>\n\n"
    for i, d in enumerate(data, 1):
        text += f"<b>Item #{i}:</b>\n" + html_code_lines(d) + "\n"
    msg = update.callback_query.message if update.callback_query else update.message
    await msg.reply_text(text, parse_mode='HTML', reply_markup=utils.main_menu_keyboard())


# Admin Input Handlers
async def h_admin_add_p(u, c):
    try:
        d = admin.parse_product_block(u.message.text)
        r = admin.add_product_admin(d['name'], d['duration'], d['price'], d['description'], d['note'], d['emoji_id'])
        await u.message.reply_text(r, reply_markup=utils.admin_main_keyboard(), parse_mode=ParseMode.HTML)
    except Exception as e:
        await u.message.reply_text(f"{ce('cancel')} {html_escape(str(e))}", parse_mode=ParseMode.HTML)
    return ConversationHandler.END


async def h_admin_bulk_p(u, c):
    try:
        data = admin.parse_bulk_products_format(u.message.text)
        r = admin.add_bulk_products_admin(data)
        await u.message.reply_text(r, reply_markup=utils.admin_main_keyboard(), parse_mode=ParseMode.HTML)
    except Exception as e:
        await u.message.reply_text(f"{ce('cancel')} Error: {html_escape(str(e))}", parse_mode=ParseMode.HTML)
    return ConversationHandler.END


async def h_admin_add_i(u, c):
    try:
        s = admin.parse_stock_bulk_format(u.message.text)
        r = admin.add_stock_bulk_admin(s)
        notify_report = await notify_stock_updates(c, s)
        await u.message.reply_text(f"{r}\n\n{notify_report}", reply_markup=utils.admin_main_keyboard(), parse_mode=ParseMode.HTML)
    except Exception as e:
        await u.message.reply_text(f"{ce('cancel')} {html_escape(str(e))}", parse_mode=ParseMode.HTML)
    return ConversationHandler.END


async def h_admin_edit_p(u, c):
    try:
        pid, pr = u.message.text.split(' | ')
        r = admin.edit_product_price(int(pid), float(pr))
        await u.message.reply_text(r, reply_markup=utils.admin_main_keyboard(), parse_mode=ParseMode.HTML)
    except Exception:
        await u.message.reply_text(f"{ce('cancel')} Format: PID | Price", parse_mode=ParseMode.HTML)
    return ConversationHandler.END


async def h_admin_edit_s(u, c):
    try:
        pid, st = u.message.text.split(' | ')
        r = admin.edit_product_stock(int(pid), int(st))
        await u.message.reply_text(r, reply_markup=utils.admin_main_keyboard(), parse_mode=ParseMode.HTML)
    except Exception:
        await u.message.reply_text(f"{ce('cancel')} Format: PID | Stock", parse_mode=ParseMode.HTML)
    return ConversationHandler.END


async def h_admin_edit_product_details_id(u, c):
    try:
        pid = int(u.message.text.strip())
        product = database.get_product(pid)
        if not product:
            await u.message.reply_text(f"{ce('cancel')} Product not found.", reply_markup=utils.admin_main_keyboard(), parse_mode=ParseMode.HTML)
            return ConversationHandler.END
        c.user_data['admin_edit_product_id'] = pid
        await u.message.reply_text(admin.get_product_detail_edit_guide(product), reply_markup=utils.admin_cancel_keyboard(), parse_mode='HTML')
        return ADMIN_EDIT_PRODUCT_DETAILS_APPLY
    except Exception:
        await u.message.reply_text(f"{ce('cancel')} Send a valid Product ID.", reply_markup=utils.admin_cancel_keyboard(), parse_mode=ParseMode.HTML)
        return ADMIN_EDIT_PRODUCT_DETAILS_ID


async def h_admin_edit_product_details_apply(u, c):
    pid = c.user_data.get('admin_edit_product_id')
    if not pid:
        await u.message.reply_text(f"{ce('cancel')} Product ID missing. Start Edit Product Details again.", reply_markup=utils.admin_main_keyboard(), parse_mode=ParseMode.HTML)
        return ConversationHandler.END
    try:
        r = admin.edit_product_details_admin(pid, u.message.text)
        c.user_data.pop('admin_edit_product_id', None)
        await u.message.reply_text(r, reply_markup=utils.admin_main_keyboard(), parse_mode=ParseMode.HTML)
    except Exception as e:
        await u.message.reply_text(f"{ce('cancel')} Error: {html_escape(str(e))}", reply_markup=utils.admin_cancel_keyboard(), parse_mode=ParseMode.HTML)
        return ADMIN_EDIT_PRODUCT_DETAILS_APPLY
    return ConversationHandler.END


async def h_admin_edit_stock_details_id(u, c):
    try:
        pid = int(u.message.text.strip())
        guide = admin.get_stock_detail_edit_guide(pid)
        if not guide:
            await u.message.reply_text(f"{ce('cancel')} Product not found.", reply_markup=utils.admin_main_keyboard(), parse_mode=ParseMode.HTML)
            return ConversationHandler.END
        c.user_data['admin_edit_stock_product_id'] = pid
        await u.message.reply_text(guide, reply_markup=utils.admin_cancel_keyboard(), parse_mode='HTML')
        return ADMIN_EDIT_STOCK_DETAILS_APPLY
    except Exception:
        await u.message.reply_text(f"{ce('cancel')} Send a valid Product ID.", reply_markup=utils.admin_cancel_keyboard(), parse_mode=ParseMode.HTML)
        return ADMIN_EDIT_STOCK_DETAILS_ID


async def h_admin_edit_stock_details_apply(u, c):
    pid = c.user_data.get('admin_edit_stock_product_id')
    if not pid:
        await u.message.reply_text(f"{ce('cancel')} Product ID missing. Start Edit Stock Details again.", reply_markup=utils.admin_main_keyboard(), parse_mode=ParseMode.HTML)
        return ConversationHandler.END
    try:
        r = admin.edit_stock_details_admin(pid, u.message.text)
        c.user_data.pop('admin_edit_stock_product_id', None)
        await u.message.reply_text(r, reply_markup=utils.admin_main_keyboard(), parse_mode=ParseMode.HTML)
    except Exception as e:
        await u.message.reply_text(f"{ce('cancel')} Error: {html_escape(str(e))}", reply_markup=utils.admin_cancel_keyboard(), parse_mode=ParseMode.HTML)
        return ADMIN_EDIT_STOCK_DETAILS_APPLY
    return ConversationHandler.END


async def h_admin_add_b(u, c):
    try:
        uid, am = u.message.text.split(' | ')
        r = admin.add_balance_admin(int(uid), float(am))
        await u.message.reply_text(r, reply_markup=utils.admin_main_keyboard(), parse_mode=ParseMode.HTML)
    except Exception:
        await u.message.reply_text(f"{ce('cancel')} Format: UID | Amt", parse_mode=ParseMode.HTML)
    return ConversationHandler.END


async def h_admin_approve_w(u, c):
    try:
        r = admin.approve_withdrawal_admin(int(u.message.text.strip()))
        await u.message.reply_text(r, reply_markup=utils.admin_main_keyboard(), parse_mode=ParseMode.HTML)
    except Exception:
        await u.message.reply_text(f"{ce('cancel')} Send a valid withdrawal ID.", reply_markup=utils.admin_cancel_keyboard(), parse_mode=ParseMode.HTML)
        return ADMIN_APPROVE_WITHDRAWAL
    return ConversationHandler.END


async def h_admin_broadcast(u, c):
    users = database.get_all_users()
    sent = 0
    text = utils.render_custom_emoji_placeholders(u.message.text)
    for user in users:
        try:
            await c.bot.send_message(user[0], text, parse_mode='HTML')
            sent += 1
        except Exception:
            pass
    await u.message.reply_text(f"{ce('confirm')} Sent to {sent}/{len(users)} users.", reply_markup=utils.admin_main_keyboard(), parse_mode=ParseMode.HTML)
    return ConversationHandler.END


async def h_admin_del_p(u, c):
    try:
        r = admin.delete_product_admin(int(u.message.text))
        await u.message.reply_text(r, reply_markup=utils.admin_main_keyboard(), parse_mode=ParseMode.HTML)
    except Exception:
        await u.message.reply_text(f"{ce('cancel')} Send valid PID", parse_mode=ParseMode.HTML)
    return ConversationHandler.END


async def h_admin_freebie_s(u, c):
    try:
        d = u.message.text.split(' | ')
        database.update_freebies_config(int(d[1]), d[2], d[3].lower() == 'enable')
        await u.message.reply_text(f"{ce('confirm')} Updated!", reply_markup=utils.admin_main_keyboard(), parse_mode=ParseMode.HTML)
    except Exception:
        await u.message.reply_text(f"{ce('cancel')} Error.", parse_mode=ParseMode.HTML)
    return ConversationHandler.END


async def h_admin_freebie_t(u, c):
    try:
        pid = int(u.message.text.split(' | ')[1])
        r = admin.toggle_product_freebie_admin(pid)
        await u.message.reply_text(r, reply_markup=utils.admin_main_keyboard(), parse_mode=ParseMode.HTML)
    except Exception:
        await u.message.reply_text(f"{ce('cancel')} Error.", parse_mode=ParseMode.HTML)
    return ConversationHandler.END


async def h_admin_freebie_stock(u, c):
    try:
        s = admin.parse_stock_bulk_format(u.message.text)
        r = admin.add_freebie_stock_bulk_admin(s)
        notify_report = await notify_stock_updates(c, s, require_freebie=True)
        await u.message.reply_text(f"{r}\n\n{notify_report}", reply_markup=utils.admin_main_keyboard(), parse_mode=ParseMode.HTML)
    except Exception as e:
        await u.message.reply_text(f"{ce('cancel')} Error: {html_escape(str(e))}", reply_markup=utils.admin_cancel_keyboard(), parse_mode=ParseMode.HTML)
        return ADMIN_FREEBIE_STOCK
    return ConversationHandler.END


async def h_admin_order_d(u, c):
    o = database.get_order_by_id(u.message.text)
    if not o:
        await u.message.reply_text(f"{ce('cancel')} Not found.", parse_mode=ParseMode.HTML)
        return ConversationHandler.END
    p = database.get_product(o[2])
    text = (
        f"{ce('order_details')} <b>Admin Order</b>\n\n"
        f"ID: <code>{o[0]}</code>\n"
        f"User: <code>{o[1]}</code>\n"
        f"Product: {html_escape(str(p[1] if p else 'N/A'))}\n"
        f"Qty: {o[3]} | {o[4]} USDT | {o[6]}\n\n"
        f"<b>Delivery:</b>\n"
    )
    for i, item in enumerate(json.loads(o[8]), 1):
        text += f"\nItem #{i}:\n" + html_code_lines(item) + "\n"
    await u.message.reply_text(text, reply_markup=utils.admin_main_keyboard(), parse_mode='HTML')
    return ConversationHandler.END


# =============================================================================
#   MAIN
# =============================================================================

def main():
    database.init_db()
    app = ApplicationBuilder().token(config.TOKEN).build()

    conv = ConversationHandler(
        entry_points=[
            CommandHandler('start', start),
            CommandHandler(
                'admin',
                lambda u, c: u.message.reply_text(
                    f"{ce('admin')} <b>Admin Panel</b>",
                    reply_markup=utils.admin_main_keyboard(),
                    parse_mode=ParseMode.HTML
                ) if admin.is_admin(u.effective_user.id) else None
            ),
            CommandHandler('emoji_test', emoji_test),
            CallbackQueryHandler(admin_button_handler, pattern='^admin_'),
            CallbackQueryHandler(button_handler),
        ],
        states={
            QUANTITY: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_quantity)],
            ORDER_DETAILS: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_order_details)],
            BINANCE_ORDER_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_binance_id)],
            DEPOSIT_TX_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_deposit_txid)],
            WALLET_DEPOSIT_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_wallet_deposit_amount)],
            ADMIN_ORDER_DETAILS: [MessageHandler(filters.TEXT & ~filters.COMMAND, h_admin_order_d)],
            ADMIN_ADD_PRODUCT: [MessageHandler(filters.TEXT & ~filters.COMMAND, h_admin_add_p)],
            ADMIN_BULK_ADD_PRODUCTS: [MessageHandler(filters.TEXT & ~filters.COMMAND, h_admin_bulk_p)],
            ADMIN_ADD_ITEMS: [MessageHandler(filters.TEXT & ~filters.COMMAND, h_admin_add_i)],
            ADMIN_EDIT_PRICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, h_admin_edit_p)],
            ADMIN_EDIT_STOCK: [MessageHandler(filters.TEXT & ~filters.COMMAND, h_admin_edit_s)],
            ADMIN_EDIT_PRODUCT_DETAILS_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, h_admin_edit_product_details_id)],
            ADMIN_EDIT_PRODUCT_DETAILS_APPLY: [MessageHandler(filters.TEXT & ~filters.COMMAND, h_admin_edit_product_details_apply)],
            ADMIN_EDIT_STOCK_DETAILS_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, h_admin_edit_stock_details_id)],
            ADMIN_EDIT_STOCK_DETAILS_APPLY: [MessageHandler(filters.TEXT & ~filters.COMMAND, h_admin_edit_stock_details_apply)],
            ADMIN_ADD_BALANCE: [MessageHandler(filters.TEXT & ~filters.COMMAND, h_admin_add_b)],
            ADMIN_APPROVE_WITHDRAWAL: [MessageHandler(filters.TEXT & ~filters.COMMAND, h_admin_approve_w)],
            ADMIN_BROADCAST: [MessageHandler(filters.TEXT & ~filters.COMMAND, h_admin_broadcast)],
            ADMIN_DELETE_PRODUCT: [MessageHandler(filters.TEXT & ~filters.COMMAND, h_admin_del_p)],
            ADMIN_SETUP_FREEBIES: [MessageHandler(filters.TEXT & ~filters.COMMAND, h_admin_freebie_s)],
            ADMIN_TOGGLE_FREEBIE: [MessageHandler(filters.TEXT & ~filters.COMMAND, h_admin_freebie_t)],
            ADMIN_FREEBIE_STOCK: [MessageHandler(filters.TEXT & ~filters.COMMAND, h_admin_freebie_stock)],
        },
        fallbacks=[
            CommandHandler('start', start),
            CallbackQueryHandler(admin_button_handler, pattern='^admin_'),
            CallbackQueryHandler(button_handler),
        ],
        per_message=False,
        allow_reentry=True
    )

    app.add_handler(conv)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, start))

    print("Bot is running...")
    app.run_polling(drop_pending_updates=True)


if __name__ == '__main__':
    main()
