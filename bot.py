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
    ADMIN_SETUP_FREEBIES,
    ADMIN_TOGGLE_FREEBIE,
) = range(15)

def ce(name: str) -> str:
    emoji_id, fallback = utils.EMOJIS.get(name, ("", ""))
    if not emoji_id:
        return fallback
    return f'<tg-emoji emoji-id="{emoji_id}">{fallback}</tg-emoji>'

# ══════════════════════════════════════════════════════════
#   START & MENU
# ══════════════════════════════════════════════════════════

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = update.effective_user
    db_user = database.get_user(user.id)
    if not db_user:
        database.create_user(user.id, user.username)
        if context.args and context.args[0].startswith('ref_'):
            try:
                ref_id = int(context.args[0].split('_')[1])
                if ref_id != user.id: database.add_referral(ref_id)
            except: pass

    text = (
        f"{ce('welcome_star')} <b>Welcome to Bunny Tools!</b>\n\n"
        f"Hey <b>{html_escape(user.first_name or 'there')}</b> 👋\n\n"
        f"Choose an option below to get started:"
    )
    
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
        f"🆔 ID: <code>{user[0]}</code>\n"
        f"📛 User: @{html_escape(user[1] or 'N/A')}\n"
        f"📅 Joined: {user[2]}\n\n"
        f"💰 Balance: <b>{user[3]} USDT</b>\n"
        f"📦 Orders: {user[4]}\n"
        f"👥 Referrals: {user[5]} ({user[6]} USDT earned)\n\n"
        f"🔗 <b>Referral Link:</b>\n<code>t.me/{bot}?start=ref_{user[0]}</code>"
    )
    await update.callback_query.edit_message_text(text, reply_markup=utils.main_menu_keyboard(), parse_mode='HTML')

async def show_history(update: Update, context: ContextTypes.DEFAULT_TYPE):
    orders = database.get_user_orders(update.effective_user.id)
    if not orders:
        text = "❌ You have no orders yet."
    else:
        text = f"{ce('order_details')} <b>Purchase History</b>\n\n"
        for o in orders[:10]:
            p = database.get_product(o[2])
            text += f"<b>Order #{o[0]}</b>\n{html_escape(p[1] if p else 'N/A')}\n{o[3]} qty | {o[4]} USDT | {o[6]}\n━━━━━━━━━━━━━━━━━━\n"
    await update.callback_query.edit_message_text(text, reply_markup=utils.main_menu_keyboard(), parse_mode='HTML')

# ══════════════════════════════════════════════════════════
#   CALLBACK HANDLER
# ══════════════════════════════════════════════════════════

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    data = query.data
    uid = update.effective_user.id
    await query.answer()

    if data == 'main_menu': return await start(update, context)
    if data == 'profile': await show_profile(update, context); return ConversationHandler.END
    if data == 'purchase_history': await show_history(update, context); return ConversationHandler.END
    
    if data == 'products':
        ps = database.get_all_products()
        await query.edit_message_text("📦 <b>Available Products:</b>", reply_markup=utils.products_list_keyboard(ps), parse_mode='HTML')
        return ConversationHandler.END

    if data == 'wallet':
        user = database.get_user(uid)
        txs = database.get_user_transactions(uid)
        msg = f"{ce('wallet')} <b>My Wallet</b>\n\nBalance: <b>{user[3]} USDT</b>\n\n<b>Recent Transactions:</b>\n"
        if not txs: msg += "No transactions found.\n"
        else:
            for t in txs[:5]: msg += f"{'+' if t[3]>0 else ''}{t[3]} USDT | {t[2]} | {str(t[4]).split(' ')[0]}\n"
        await query.edit_message_text(msg, reply_markup=utils.wallet_options_keyboard(), parse_mode='HTML')
        return ConversationHandler.END

    if data == 'support':
        text = f"{ce('support_center')} <b>Support Center</b>\n\nContact: @Bunnyhaccks\nChannel: @bunnyhackss"
        await query.edit_message_text(text, reply_markup=utils.support_keyboard(), parse_mode='HTML')
        return ConversationHandler.END

    if data == 'faq':
        await query.edit_message_text("❓ <b>FAQ</b>\n\nInstant delivery after payment. For help, contact @Bunnyhaccks.", reply_markup=utils.support_keyboard(), parse_mode='HTML')
        return ConversationHandler.END

    if data == 'deposit_wallet':
        text = f"💰 <b>Deposit</b>\n\nAddress: <code>{config.BINANCE_WALLET_ADDRESS}</code>\nNetwork: {config.BINANCE_NETWORK}\n\nSend TXID after payment."
        await query.edit_message_text(text, reply_markup=utils.deposit_wallet_keyboard(), parse_mode='HTML')
        return DEPOSIT_TX_ID

    if data == 'check_deposit_payment':
        await query.edit_message_text("📨 Send your <b>TXID</b>:")
        return DEPOSIT_TX_ID

    if data == 'order_details':
        await query.edit_message_text("🔎 Send your <b>Order ID</b>:")
        return ORDER_DETAILS

    if data == 'freebies':
        cfg = database.get_freebies_config()
        if not cfg[3]: await query.answer("❌ Disabled.", show_alert=True); return ConversationHandler.END
        await query.edit_message_text("🎁 <b>Freebies</b>", reply_markup=utils.freebies_keyboard(database.get_freebie_products(), cfg), parse_mode='HTML')
        return ConversationHandler.END

    if data.startswith('claim_freebie_'):
        pid = int(data.split('_')[2])
        if database.has_user_received_freebie(uid, pid): await query.answer("❌ Already claimed!", show_alert=True); return ConversationHandler.END
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
        if not p or p[4] <= 0: await query.answer("❌ Out of stock!", show_alert=True); return ConversationHandler.END
        await query.edit_message_text(f"🔢 <b>{p[1]}</b>\n\nQuantity (1-{p[4]}):", reply_markup=utils.quantity_selection_keyboard(), parse_mode='HTML')
        return QUANTITY

    if data == 'back_to_product_details':
        pid = context.user_data.get('current_product_id')
        if not pid: return await start(update, context)
        await query.edit_message_text(products_helper.get_product_details_message(pid), reply_markup=utils.product_details_keyboard(), parse_mode='HTML')
        return ConversationHandler.END

    if data == 'pay_binance':
        total = context.user_data.get('total_amount')
        await query.edit_message_text(payment.get_binance_payment_details(total), reply_markup=utils.binance_payment_keyboard(), parse_mode='HTML')
        return ConversationHandler.END

    if data == 'check_binance_payment':
        await query.edit_message_text("📨 Send your <b>Binance Order ID</b>:")
        return BINANCE_ORDER_ID

    if data == 'pay_wallet':
        total = context.user_data.get('total_amount')
        user = database.get_user(uid)
        markup = utils.wallet_payment_keyboard() if user[3] >= total else utils.insufficient_balance_keyboard()
        await query.edit_message_text(payment.get_wallet_payment_summary(uid, total), reply_markup=markup, parse_mode='HTML')
        return ConversationHandler.END

    if data == 'confirm_wallet_payment':
        pid, qty, total = context.user_data.get('current_product_id'), context.user_data.get('quantity'), context.user_data.get('total_amount')
        success, msg = payment.process_wallet_payment(uid, None, pid, qty, total)
        if success: await deliver_product(update, context, 'Wallet')
        else: await query.edit_message_text(msg, reply_markup=utils.main_menu_keyboard(), parse_mode='HTML')
        return ConversationHandler.END

    if data == 'cancel_order': return await start(update, context)
    return ConversationHandler.END

# ══════════════════════════════════════════════════════════
#   ADMIN CALLBACKS
# ══════════════════════════════════════════════════════════

async def admin_button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    if not admin.is_admin(update.effective_user.id): return ConversationHandler.END
    await query.answer()
    data = query.data

    if data == 'admin_panel_back': await query.edit_message_text("👑 <b>Admin Panel</b>", reply_markup=utils.admin_main_keyboard(), parse_mode='HTML'); return ConversationHandler.END
    if data == 'admin_view_stats': await query.edit_message_text(admin.get_stats_admin(), reply_markup=utils.admin_back_keyboard(), parse_mode='Markdown')
    elif data == 'admin_view_products': await query.edit_message_text(admin.get_all_products_admin(), reply_markup=utils.admin_back_keyboard(), parse_mode='Markdown')
    elif data == 'admin_view_all_orders': await query.edit_message_text(admin.get_all_orders_admin(), reply_markup=utils.admin_back_keyboard(), parse_mode='Markdown')
    elif data == 'admin_withdraw_requests': await query.edit_message_text(admin.get_withdrawal_requests_admin(), reply_markup=utils.admin_back_keyboard(), parse_mode='Markdown')
    elif data == 'admin_order_details': await query.edit_message_text("🔎 Send Order ID:", reply_markup=utils.admin_cancel_keyboard()); return ADMIN_ORDER_DETAILS
    elif data == 'admin_add_product': await query.edit_message_text("➕ Format: `Name | Duration | Price | Desc | Note | Emoji`", reply_markup=utils.admin_cancel_keyboard()); return ADMIN_ADD_PRODUCT
    elif data == 'admin_add_items': await query.edit_message_text("📦 Format: `PID[{f:v}]`", reply_markup=utils.admin_cancel_keyboard()); return ADMIN_ADD_ITEMS
    elif data == 'admin_edit_price': await query.edit_message_text("💰 Send: `PID | Price`", reply_markup=utils.admin_cancel_keyboard()); return ADMIN_EDIT_PRICE
    elif data == 'admin_edit_stock': await query.edit_message_text("📦 Send: `PID | Stock`", reply_markup=utils.admin_cancel_keyboard()); return ADMIN_EDIT_STOCK
    elif data == 'admin_add_balance': await query.edit_message_text("💰 Send: `UID | Amt`", reply_markup=utils.admin_cancel_keyboard()); return ADMIN_ADD_BALANCE
    elif data == 'admin_broadcast': await query.edit_message_text("📢 Send message:", reply_markup=utils.admin_cancel_keyboard()); return ADMIN_BROADCAST
    elif data == 'admin_delete_product': await query.edit_message_text("❌ Send PID:", reply_markup=utils.admin_cancel_keyboard()); return ADMIN_DELETE_PRODUCT
    elif data == 'admin_freebies_settings': await query.edit_message_text(admin.get_freebies_settings_admin(), reply_markup=utils.admin_back_keyboard(), parse_mode='Markdown'); return ADMIN_SETUP_FREEBIES
    elif data == 'admin_freebie_products': await query.edit_message_text(admin.get_freebie_products_admin(), reply_markup=utils.admin_back_keyboard(), parse_mode='Markdown'); return ADMIN_TOGGLE_FREEBIE
    return ConversationHandler.END

# ══════════════════════════════════════════════════════════
#   INPUT HANDLERS
# ══════════════════════════════════════════════════════════

async def handle_quantity(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    try:
        qty = int(update.message.text)
        pid = context.user_data.get('current_product_id')
        p = database.get_product(pid)
        if not p or qty <= 0 or qty > p[4]:
            await update.message.reply_text(f"❌ Invalid. Max: {p[4] if p else 0}")
            return QUANTITY
        context.user_data.update({'quantity': qty, 'total_amount': p[3]*qty})
        text = f"✅ <b>Order Summary</b>\n\nProduct: {p[1]}\nQty: {qty}\nTotal: <b>{context.user_data['total_amount']} USDT</b>\n\nSelect Payment:"
        await update.message.reply_text(text, reply_markup=utils.payment_method_keyboard(), parse_mode='HTML')
        return ConversationHandler.END
    except: await update.message.reply_text("❌ Send a valid number."); return QUANTITY

async def handle_order_details(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    o = database.get_order_by_id(update.message.text)
    if not o: await update.message.reply_text("❌ Not found."); return ConversationHandler.END
    p = database.get_product(o[2])
    text = f"🔎 <b>Order</b>\n\nID: <code>{o[0]}</code>\nProduct: {p[1] if p else 'N/A'}\nQty: {o[3]} | {o[4]} USDT | {o[6]}\n\n<b>Delivery:</b>\n"
    for i, item in enumerate(json.loads(o[8]), 1):
        text += f"\nItem #{i}:\n" + "\n".join([f"{k}: <code>{v}</code>" for k, v in item.items()]) + "\n"
    await update.message.reply_text(text, reply_markup=utils.main_menu_keyboard(), parse_mode='HTML')
    return ConversationHandler.END

async def handle_deposit_txid(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("✅ <b>Request Sent!</b> Admin will verify soon.", reply_markup=utils.main_menu_keyboard(), parse_mode='HTML')
    await context.bot.send_message(config.ADMIN_ID, f"🔔 <b>Deposit</b>\nUser: {update.effective_user.id}\nTXID: <code>{update.message.text}</code>", parse_mode='HTML')
    return ConversationHandler.END

async def handle_binance_id(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    success, msg = payment.process_binance_payment(update.effective_user.id, None, context.user_data.get('current_product_id'), context.user_data.get('quantity'), context.user_data.get('total_amount'), update.message.text)
    if success: await deliver_product(update, context, 'Binance')
    else: await update.message.reply_text(msg, parse_mode='HTML', reply_markup=utils.main_menu_keyboard())
    return ConversationHandler.END

async def deliver_product(update: Update, context: ContextTypes.DEFAULT_TYPE, method: str):
    pid, qty = context.user_data.get('current_product_id'), context.user_data.get('quantity')
    items = database.get_unsold_items(pid, qty)
    if len(items) < qty:
        msg = update.callback_query.message if update.callback_query else update.message
        await msg.reply_text("❌ Stock mismatch. Contact support.")
        return
    data = [i['data'] for i in items]
    oid = utils.generate_order_id()
    database.create_order(oid, update.effective_user.id, pid, qty, context.user_data.get('total_amount'), method, 'Confirmed', data)
    database.mark_items_as_sold(pid, [i['id'] for i in items])
    database.update_product_stock(pid, -qty)
    p = database.get_product(pid)
    text = f"✅ <b>Delivered!</b>\n\nOrder: <code>{oid}</code>\nProduct: <b>{p[1]}</b>\n\n"
    for i, d in enumerate(data, 1): text += f"<b>Item #{i}:</b>\n" + "\n".join([f"{k}: <code>{v}</code>" for k, v in d.items()]) + "\n"
    msg = update.callback_query.message if update.callback_query else update.message
    await msg.reply_text(text, parse_mode='HTML', reply_markup=utils.main_menu_keyboard())

# Admin Input Handlers
async def h_admin_add_p(u, c):
    try:
        d = admin.parse_product_block(u.message.text)
        r = admin.add_product_admin(d['name'], d['duration'], d['price'], d['description'], d['note'], d['emoji_id'])
        await u.message.reply_text(r, reply_markup=utils.admin_main_keyboard())
    except Exception as e: await u.message.reply_text(f"❌ {e}")
    return ConversationHandler.END

async def h_admin_add_i(u, c):
    try:
        s = admin.parse_stock_bulk_format(u.message.text)
        r = admin.add_stock_bulk_admin(s)
        await u.message.reply_text(r, reply_markup=utils.admin_main_keyboard())
    except Exception as e: await u.message.reply_text(f"❌ {e}")
    return ConversationHandler.END

async def h_admin_edit_p(u, c):
    try:
        pid, pr = u.message.text.split(' | ')
        r = admin.edit_product_price(int(pid), float(pr))
        await u.message.reply_text(r, reply_markup=utils.admin_main_keyboard())
    except: await u.message.reply_text("❌ Format: PID | Price")
    return ConversationHandler.END

async def h_admin_edit_s(u, c):
    try:
        pid, st = u.message.text.split(' | ')
        r = admin.edit_product_stock(int(pid), int(st))
        await u.message.reply_text(r, reply_markup=utils.admin_main_keyboard())
    except: await u.message.reply_text("❌ Format: PID | Stock")
    return ConversationHandler.END

async def h_admin_add_b(u, c):
    try:
        uid, am = u.message.text.split(' | ')
        r = admin.add_balance_admin(int(uid), float(am))
        await u.message.reply_text(r, reply_markup=utils.admin_main_keyboard())
    except: await u.message.reply_text("❌ Format: UID | Amt")
    return ConversationHandler.END

async def h_admin_broadcast(u, c):
    users = database.get_all_users()
    sent = 0
    for user in users:
        try: await c.bot.send_message(user[0], u.message.text, parse_mode='HTML'); sent += 1
        except: pass
    await u.message.reply_text(f"✅ Sent to {sent}/{len(users)} users.", reply_markup=utils.admin_main_keyboard())
    return ConversationHandler.END

async def h_admin_del_p(u, c):
    try:
        r = admin.delete_product_admin(int(u.message.text))
        await u.message.reply_text(r, reply_markup=utils.admin_main_keyboard())
    except: await u.message.reply_text("❌ Send valid PID")
    return ConversationHandler.END

async def h_admin_freebie_s(u, c):
    try:
        d = u.message.text.split(' | ')
        database.update_freebies_config(int(d[1]), d[2], d[3].lower() == 'enable')
        await u.message.reply_text("✅ Updated!", reply_markup=utils.admin_main_keyboard())
    except: await u.message.reply_text("❌ Error.")
    return ConversationHandler.END

async def h_admin_freebie_t(u, c):
    try:
        pid = int(u.message.text.split(' | ')[1])
        p = database.get_product(pid)
        database.toggle_product_freebie(pid, not p[10])
        await u.message.reply_text("✅ Toggled!", reply_markup=utils.admin_main_keyboard())
    except: await u.message.reply_text("❌ Error.")
    return ConversationHandler.END

async def h_admin_order_d(u, c):
    o = database.get_order_by_id(u.message.text)
    if not o: await u.message.reply_text("❌ Not found."); return ConversationHandler.END
    p = database.get_product(o[2])
    text = f"🔎 <b>Admin Order</b>\n\nID: <code>{o[0]}</code>\nUser: <code>{o[1]}</code>\nProduct: {p[1] if p else 'N/A'}\nQty: {o[3]} | {o[4]} USDT | {o[6]}\n\n<b>Delivery:</b>\n"
    for i, item in enumerate(json.loads(o[8]), 1):
        text += f"\nItem #{i}:\n" + "\n".join([f"{k}: <code>{v}</code>" for k, v in item.items()]) + "\n"
    await u.message.reply_text(text, reply_markup=utils.admin_main_keyboard(), parse_mode='HTML')
    return ConversationHandler.END

# ══════════════════════════════════════════════════════════
#   MAIN
# ══════════════════════════════════════════════════════════

def main():
    database.init_db()
    app = ApplicationBuilder().token(config.TOKEN).build()
    
    conv = ConversationHandler(
        entry_points=[
            CommandHandler('start', start),
            CommandHandler('admin', lambda u, c: u.message.reply_text("👑 <b>Admin Panel</b>", reply_markup=utils.admin_main_keyboard(), parse_mode='HTML') if admin.is_admin(u.effective_user.id) else None),
            CallbackQueryHandler(admin_button_handler, pattern='^admin_'),
            CallbackQueryHandler(button_handler),
        ],
        states={
            QUANTITY: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_quantity)],
            ORDER_DETAILS: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_order_details)],
            BINANCE_ORDER_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_binance_id)],
            DEPOSIT_TX_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_deposit_txid)],
            ADMIN_ORDER_DETAILS: [MessageHandler(filters.TEXT & ~filters.COMMAND, h_admin_order_d)],
            ADMIN_ADD_PRODUCT: [MessageHandler(filters.TEXT & ~filters.COMMAND, h_admin_add_p)],
            ADMIN_ADD_ITEMS: [MessageHandler(filters.TEXT & ~filters.COMMAND, h_admin_add_i)],
            ADMIN_EDIT_PRICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, h_admin_edit_p)],
            ADMIN_EDIT_STOCK: [MessageHandler(filters.TEXT & ~filters.COMMAND, h_admin_edit_s)],
            ADMIN_ADD_BALANCE: [MessageHandler(filters.TEXT & ~filters.COMMAND, h_admin_add_b)],
            ADMIN_BROADCAST: [MessageHandler(filters.TEXT & ~filters.COMMAND, h_admin_broadcast)],
            ADMIN_DELETE_PRODUCT: [MessageHandler(filters.TEXT & ~filters.COMMAND, h_admin_del_p)],
            ADMIN_SETUP_FREEBIES: [MessageHandler(filters.TEXT & ~filters.COMMAND, h_admin_freebie_s)],
            ADMIN_TOGGLE_FREEBIE: [MessageHandler(filters.TEXT & ~filters.COMMAND, h_admin_freebie_t)],
        },
        fallbacks=[CommandHandler('start', start), CallbackQueryHandler(button_handler)],
        per_message=False,
        allow_reentry=True
    )
    
    app.add_handler(conv)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, start)) # Final fallback
    
    print("Bot is running...")
    app.run_polling(drop_pending_updates=True)

if __name__ == '__main__':
    main()
