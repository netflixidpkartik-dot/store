#!/usr/bin/env python3
"""store_bot.py — Customer facing store bot."""

import asyncio, logging, os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, filters, ContextTypes,
)
from telegram.error import BadRequest
import shared_db as db

# ══════════════════════════════════════════════════════
#  CONFIG  — set these in Railway Variables
# ══════════════════════════════════════════════════════

STORE_BOT_TOKEN = os.environ["STORE_TOKEN"]
BOT_NAME        = os.environ.get("BOT_NAME", "Xing Store")
SUPPORT         = os.environ.get("SUPPORT_USERNAME", "@xingstorebot")

HTML = "HTML"
logging.basicConfig(format="%(asctime)s — %(levelname)s — %(message)s", level=logging.INFO)
logging.getLogger("httpx").setLevel(logging.WARNING)

# ══════════════════════════════════════════════════════
#  KEYBOARDS
# ══════════════════════════════════════════════════════

def kb_main():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🛍 Products",         callback_data="products"),
         InlineKeyboardButton("🎁 Redeem Code",      callback_data="redeem")],
        [InlineKeyboardButton("👤 My Profile",       callback_data="profile"),
         InlineKeyboardButton("📋 My Orders",        callback_data="history")],
        [InlineKeyboardButton("👛 Wallet",           callback_data="wallet")],
        [InlineKeyboardButton("🆘 Support",          callback_data="support")],
    ])

def kb_back_main():
    return InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Main Menu", callback_data="main_menu")]])

def kb_products(products):
    rows = []
    for p in products:
        rows.append([InlineKeyboardButton(
            f"📦 {p['name']}  |  ${p['price']:.2f}  |  {p['stock']} left",
            callback_data=f"acc_{p['id']}")])
    rows.append([InlineKeyboardButton("🔄 Refresh", callback_data="products"),
                 InlineKeyboardButton("🏠 Menu",    callback_data="main_menu")])
    return InlineKeyboardMarkup(rows)

def kb_product_detail(pid, in_cart):
    btn = "✅ In Cart" if in_cart else "🛒 Add to Cart"
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(btn,           callback_data=f"addcart_{pid}"),
         InlineKeyboardButton("⚡ Buy Now",  callback_data=f"buynow_{pid}")],
        [InlineKeyboardButton("⬅️ Back",     callback_data="products"),
         InlineKeyboardButton("🏠 Menu",     callback_data="main_menu")],
    ])

def kb_cart(cart):
    rows = [[InlineKeyboardButton(
        f"❌ {p['name']}  (${p['price']:.2f})",
        callback_data=f"rmcart_{p['id']}")] for p in cart]
    rows.append([InlineKeyboardButton("✅ Checkout", callback_data="checkout")])
    rows.append([InlineKeyboardButton("🛍 Browse",  callback_data="products"),
                 InlineKeyboardButton("🏠 Menu",    callback_data="main_menu")])
    return InlineKeyboardMarkup(rows)

def kb_empty_cart():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🛍 Browse Products", callback_data="products")],
        [InlineKeyboardButton("🏠 Main Menu",       callback_data="main_menu")],
    ])

def kb_wallet():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("💳 Deposit Funds", callback_data="deposit_menu")],
        [InlineKeyboardButton("🏠 Main Menu",     callback_data="main_menu")],
    ])

def kb_networks(wallets):
    rows = [[InlineKeyboardButton(label, callback_data=f"pay_net_{key}")]
            for key, (label, _) in wallets.items()]
    rows.append([InlineKeyboardButton("❌ Cancel", callback_data="wallet")])
    return InlineKeyboardMarkup(rows)

def kb_sent(key):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ I Have Sent Payment", callback_data=f"sent_{key}")],
        [InlineKeyboardButton("⬅️ Change Network",      callback_data="deposit_menu")],
    ])

# ══════════════════════════════════════════════════════
#  TEXT HELPERS
# ══════════════════════════════════════════════════════

def txt_welcome(name):
    return (
        f"🚀 <b>Welcome to {BOT_NAME}, {name}!</b>\n\n"
        f"🎯 Quick guide:\n"
        f"1. Tap 'Products' to browse.\n"
        f"2. Add to cart or Buy Now.\n"
        f"3. Pay via wallet balance.\n"
        f"4. Receive your product instantly!\n\n"
        f"Choose an option below:"
    )

def txt_wallet_info(bal):
    return (
        f"👛 <b>Your Wallet</b>\n\n"
        f"💰 Balance: <b>${bal:.2f} USDT</b>\n\n"
        f"Deposit funds to start buying.\n"
        f"<i>Min deposit: $1.00 USDT</i>"
    )

def txt_product(p):
    return (
        f"📦 <b>{p['name']}</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"💰 Price : <b>${p['price']:.2f} USDT</b>\n"
        f"📦 Stock : <b>{p['stock']} available</b>\n"
        f"✅ Status: IN STOCK"
    )

def txt_cart(cart):
    lines = "\n".join(f"• {p['name']} — <b>${p['price']:.2f}</b>" for p in cart)
    total = sum(p["price"] for p in cart)
    return (f"🛒 <b>Your Cart</b>\n\n{lines}\n\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"💰 Total: <b>${total:.2f} USDT</b>")

def txt_history(orders):
    if not orders:
        return "📋 <b>My Orders</b>\n\nNo orders yet!"
    lines = []
    for ref, name, price, status, created in orders[:20]:
        icon = "✅" if status == "delivered" else "⏳"
        lines.append(f"{icon} <code>{ref}</code>\n   📦 {name} — ${price:.2f}\n   📅 {created}")
    return "📋 <b>My Orders</b>\n\n" + "\n\n".join(lines)

def txt_profile(row, tg_id, order_count):
    name, username, created_at, balance = row
    return (
        f"👤 <b>My Profile</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🆔 ID       : <code>{tg_id}</code>\n"
        f"👤 Name     : <b>{name}</b>\n"
        f"📛 Username : {'@'+username if username else '—'}\n"
        f"📅 Joined   : {(created_at or '')[:10]}\n"
        f"💰 Balance  : <b>${balance:.2f} USDT</b>\n"
        f"📦 Orders   : <b>{order_count}</b>"
    )

async def safe_ans(q, text="", alert=False):
    try: await q.answer(text, show_alert=alert)
    except BadRequest: pass

# ══════════════════════════════════════════════════════
#  HANDLERS
# ══════════════════════════════════════════════════════

async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db.ensure_user(user.id, user.first_name, user.username or "")
    await update.message.reply_text(
        txt_welcome(user.first_name), parse_mode=HTML, reply_markup=kb_main())

async def on_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q    = update.callback_query
    data = q.data
    user = update.effective_user
    db.ensure_user(user.id, user.first_name, user.username or "")
    await safe_ans(q)

    if data == "main_menu":
        await q.edit_message_text("🏠 <b>Main Menu</b>", parse_mode=HTML, reply_markup=kb_main())

    elif data == "products":
        prods = db.get_active_products()
        if not prods:
            await q.edit_message_text("😔 No products available right now.",
                                      reply_markup=kb_back_main()); return
        await q.edit_message_text("🛍 <b>PRODUCTS</b>\n\n💡 Choose a product:",
                                  parse_mode=HTML, reply_markup=kb_products(prods))

    elif data.startswith("acc_"):
        pid = int(data[4:])
        p   = db.get_product(pid)
        if not p: await safe_ans(q, "Not found.", alert=True); return
        in_cart = any(c["id"] == pid for c in db.get_cart(user.id))
        await q.edit_message_text(txt_product(p), parse_mode=HTML,
                                  reply_markup=kb_product_detail(pid, in_cart))

    elif data.startswith("addcart_"):
        pid = int(data[8:])
        if any(c["id"] == pid for c in db.get_cart(user.id)):
            await safe_ans(q, "Already in cart!", alert=True)
        else:
            db.add_to_cart(user.id, pid)
            await safe_ans(q, "✅ Added to cart!", alert=True)
            try: await q.edit_message_reply_markup(reply_markup=kb_product_detail(pid, True))
            except BadRequest: pass

    elif data.startswith("buynow_"):
        pid = int(data[7:])
        if not any(c["id"] == pid for c in db.get_cart(user.id)):
            db.add_to_cart(user.id, pid)
        await _do_checkout(q, user.id)

    elif data == "cart":
        cart = db.get_cart(user.id)
        if not cart:
            await q.edit_message_text("🛒 <b>Cart is empty.</b>",
                                      parse_mode=HTML, reply_markup=kb_empty_cart())
        else:
            await q.edit_message_text(txt_cart(cart), parse_mode=HTML, reply_markup=kb_cart(cart))

    elif data.startswith("rmcart_"):
        pid = int(data[7:])
        db.remove_from_cart(user.id, pid)
        cart = db.get_cart(user.id)
        if not cart:
            await q.edit_message_text("🛒 <b>Cart is empty.</b>",
                                      parse_mode=HTML, reply_markup=kb_empty_cart())
        else:
            await q.edit_message_text(txt_cart(cart), parse_mode=HTML, reply_markup=kb_cart(cart))

    elif data == "checkout":
        await _do_checkout(q, user.id)

    elif data == "wallet":
        bal = db.get_balance(user.id)
        await q.edit_message_text(txt_wallet_info(bal), parse_mode=HTML, reply_markup=kb_wallet())

    elif data == "deposit_menu":
        wallets = db.get_active_wallets()
        await q.edit_message_text(
            "💳 <b>Deposit Funds</b>\n\nMinimum: <b>$1.00 USDT</b>\n\nSelect a payment network:",
            parse_mode=HTML, reply_markup=kb_networks(wallets))

    elif data.startswith("pay_net_"):
        key = data[8:]
        wallets = db.get_active_wallets()
        if key not in wallets:
            await safe_ans(q, "Network unavailable.", alert=True); return
        label, addr = wallets[key]
        ctx.user_data["dep_network"]       = key
        ctx.user_data["dep_network_label"] = label
        await q.edit_message_text(
            f"💳 <b>Deposit via {label}</b>\n\n"
            f"📬 <b>Send to this address:</b>\n"
            f"<code>{addr}</code>\n\n"
            f"⚠️ <i>After sending, tap the button below to submit your proof.</i>",
            parse_mode=HTML, reply_markup=kb_sent(key))

    elif data.startswith("sent_"):
        ctx.user_data["state"]       = "awaiting_proof"
        ctx.user_data["dep_ref"]     = db.new_ref("DEP")
        ctx.user_data["dep_network"] = ctx.user_data.get(
            "dep_network_label", ctx.user_data.get("dep_network", "Unknown"))
        await q.edit_message_text(
            "📸 <b>Submit Payment Proof</b>\n\n"
            "Please send a <b>screenshot</b> of your payment.\n"
            "Write your <b>Transaction ID (TXN ID)</b> as the caption.\n\n"
            "<i>No screenshot? Just send the TXN ID as a text message.</i>",
            parse_mode=HTML,
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("❌ Cancel", callback_data="wallet")
            ]]))

    elif data == "profile":
        row    = db.get_user_info(user.id)
        orders = db.get_orders(user.id)
        if row:
            await q.edit_message_text(
                txt_profile(row, user.id, len(orders)), parse_mode=HTML,
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("💳 Deposit",   callback_data="deposit_menu")],
                    [InlineKeyboardButton("🏠 Main Menu", callback_data="main_menu")],
                ]))

    elif data == "history":
        orders = db.get_orders(user.id)
        await q.edit_message_text(txt_history(orders), parse_mode=HTML, reply_markup=kb_back_main())

    elif data == "redeem":
        ctx.user_data["state"] = "awaiting_redeem"
        await q.edit_message_text(
            "🎁 <b>Redeem Code</b>\n\nSend your code:",
            parse_mode=HTML,
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("❌ Cancel", callback_data="main_menu")
            ]]))

    elif data == "support":
        await q.edit_message_text(
            f"🆘 <b>Support</b>\n\nContact us: {SUPPORT}",
            parse_mode=HTML, reply_markup=kb_back_main())


async def _do_checkout(q, user_id):
    cart = db.get_cart(user_id)
    if not cart:
        await q.edit_message_text("🛒 <b>Cart is empty!</b>",
                                  parse_mode=HTML, reply_markup=kb_empty_cart()); return
    p       = cart[0]
    total   = p["price"]
    balance = db.get_balance(user_id)
    if balance < total:
        needed = total - balance
        await q.edit_message_text(
            f"❌ <b>Insufficient Balance</b>\n\n"
            f"💰 Price   : <b>${total:.2f} USDT</b>\n"
            f"👛 Balance : <b>${balance:.2f} USDT</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"⚠️ You need <b>${needed:.2f} more.</b>",
            parse_mode=HTML,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("💳 Deposit Funds", callback_data="deposit_menu")],
                [InlineKeyboardButton("🏠 Main Menu",     callback_data="main_menu")],
            ])); return

    db.deduct_balance(user_id, total)
    order_ref = db.new_ref("TG")
    db.save_order(user_id, p, order_ref)
    db.remove_from_cart(user_id, p["id"])

    await q.edit_message_text(
        f"✅ <b>Order Placed!</b>\n\n"
        f"📦 Product : <b>{p['name']}</b>\n"
        f"💰 Paid    : <b>${total:.2f} USDT</b>\n"
        f"📋 Ref     : <code>{order_ref}</code>\n"
        f"👛 Balance : <b>${db.get_balance(user_id):.2f} USDT</b>\n\n"
        f"⏳ <b>Your product will be delivered within 5–10 minutes.</b>\n"
        f"If not received, contact {SUPPORT}",
        parse_mode=HTML,
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("📋 My Orders",         callback_data="history")],
            [InlineKeyboardButton("🛍 Continue Shopping", callback_data="products")],
        ]))


async def _save_proof(update, ctx, proof_type, proof_content, txn_id):
    user    = update.effective_user
    ref     = ctx.user_data.pop("dep_ref",    db.new_ref("DEP"))
    network = ctx.user_data.pop("dep_network", "Unknown")
    ctx.user_data.pop("state", None)
    db.ensure_user(user.id, user.first_name, user.username or "")
    db.save_deposit_proof(user.id, ref, network, proof_type, proof_content, txn_id)
    await update.message.reply_text(
        f"✅ <b>Deposit Request Submitted!</b>\n\n"
        f"⚡ Your proof is being verified.\n"
        f"📋 Status : <b>Pending</b>\n"
        f"⏳ Time   : 3 Hours (Max)\n\n"
        f"📌 Reference: <code>{ref}</code>",
        parse_mode=HTML, reply_markup=kb_back_main())

async def on_photo(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if ctx.user_data.get("state") == "awaiting_proof":
        file_id = update.message.photo[-1].file_id
        txn_id  = (update.message.caption or "").strip() or "Not provided"
        await _save_proof(update, ctx, "photo", file_id, txn_id)

async def on_text(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user  = update.effective_user
    text  = (update.message.text or "").strip()
    state = ctx.user_data.get("state")
    db.ensure_user(user.id, user.first_name, user.username or "")

    if state == "awaiting_proof":
        await _save_proof(update, ctx, "text", text, text)

    elif state == "awaiting_redeem":
        ctx.user_data.pop("state", None)
        amount, msg = db.try_redeem(user.id, text)
        if amount:
            await update.message.reply_text(
                f"🎉 <b>Redeemed!</b>\n\n"
                f"💰 <b>${amount:.2f} USDT</b> added!\n"
                f"Balance: <b>${db.get_balance(user.id):.2f} USDT</b>",
                parse_mode=HTML, reply_markup=kb_back_main())
        else:
            await update.message.reply_text(msg, reply_markup=kb_back_main())


async def run():
    db.init_db()
    app = Application.builder().token(STORE_BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CallbackQueryHandler(on_callback))
    app.add_handler(MessageHandler(filters.PHOTO, on_photo))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_text))
    print("✅ Store Bot running...")
    async with app:
        await app.start()
        await app.updater.start_polling(allowed_updates=Update.ALL_TYPES)
        await asyncio.Event().wait()
        await app.updater.stop()
        await app.stop()

if __name__ == "__main__":
    asyncio.run(run())
