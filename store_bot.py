#!/usr/bin/env python3
"""store_bot.py — Customer store bot with quantity selection."""

import asyncio, logging, os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, filters, ContextTypes,
)
from telegram.error import BadRequest
import shared_db as db

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
            f"📦 {p['name']}  |  ${p['price']:.2f}/each  |  {p['stock']} in stock",
            callback_data=f"acc_{p['id']}")])
    rows.append([InlineKeyboardButton("🔄 Refresh", callback_data="products"),
                 InlineKeyboardButton("🏠 Menu",    callback_data="main_menu")])
    return InlineKeyboardMarkup(rows)

def kb_product_detail(pid):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🛒 Order Now", callback_data=f"order_start_{pid}")],
        [InlineKeyboardButton("⬅️ Back",      callback_data="products"),
         InlineKeyboardButton("🏠 Menu",      callback_data="main_menu")],
    ])

def kb_qty(pid, price, stock):
    """Quick quantity buttons + custom option."""
    qtys  = [1, 2, 3, 5, 10]
    valid = [q for q in qtys if q <= stock]
    rows  = []
    row   = []
    for q in valid:
        row.append(InlineKeyboardButton(
            f"{q}  (${price*q:.2f})", callback_data=f"qty_{pid}_{q}"))
        if len(row) == 3:
            rows.append(row); row = []
    if row: rows.append(row)
    rows.append([InlineKeyboardButton("✏️ Enter Custom Quantity", callback_data=f"qty_custom_{pid}")])
    rows.append([InlineKeyboardButton("❌ Cancel", callback_data=f"acc_{pid}")])
    return InlineKeyboardMarkup(rows)

def kb_confirm_order(pid, qty, total):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(f"✅ Confirm  (${total:.2f})", callback_data=f"confirm_order_{pid}_{qty}")],
        [InlineKeyboardButton("✏️ Change Qty",               callback_data=f"order_start_{pid}"),
         InlineKeyboardButton("❌ Cancel",                   callback_data="products")],
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
        f"🎯 How it works:\n"
        f"1. Browse Products\n"
        f"2. Select quantity\n"
        f"3. Confirm & pay from wallet\n"
        f"4. Receive within 5–10 min!\n\n"
        f"Choose an option below:"
    )

def txt_product(p):
    return (
        f"📦 <b>{p['name']}</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"💰 Price  : <b>${p['price']:.2f} USDT</b> per unit\n"
        f"📦 Stock  : <b>{p['stock']} available</b>\n"
        f"✅ Status : IN STOCK"
    )

def txt_wallet_info(bal):
    return (
        f"👛 <b>Your Wallet</b>\n\n"
        f"💰 Balance: <b>${bal:.2f} USDT</b>\n\n"
        f"Deposit funds to start buying.\n"
        f"<i>Min deposit: $1.00 USDT</i>"
    )

def txt_history(orders):
    if not orders:
        return "📋 <b>My Orders</b>\n\nNo orders yet!"
    lines = []
    for ref, name, price, qty, status, created in orders[:20]:
        icon = "✅" if status == "delivered" else "⏳"
        lines.append(
            f"{icon} <code>{ref}</code>\n"
            f"   📦 {name} × {qty} — ${price:.2f}\n"
            f"   📅 {created}")
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
#  COMMAND HANDLERS
# ══════════════════════════════════════════════════════

async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db.ensure_user(user.id, user.first_name, user.username or "")
    await update.message.reply_text(
        txt_welcome(user.first_name), parse_mode=HTML, reply_markup=kb_main())

# ══════════════════════════════════════════════════════
#  CALLBACK HANDLER
# ══════════════════════════════════════════════════════

async def on_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q    = update.callback_query
    data = q.data
    user = update.effective_user
    db.ensure_user(user.id, user.first_name, user.username or "")
    await safe_ans(q)

    # ── Main menu ─────────────────────────────────────
    if data == "main_menu":
        await q.edit_message_text("🏠 <b>Main Menu</b>", parse_mode=HTML, reply_markup=kb_main())

    # ── Products ──────────────────────────────────────
    elif data == "products":
        prods = db.get_active_products()
        if not prods:
            await q.edit_message_text("😔 No products right now. Check back soon!",
                                      reply_markup=kb_back_main()); return
        await q.edit_message_text("🛍 <b>PRODUCTS</b>\n\n💡 Choose a product:",
                                  parse_mode=HTML, reply_markup=kb_products(prods))

    # ── Product detail ────────────────────────────────
    elif data.startswith("acc_"):
        pid = int(data[4:])
        p   = db.get_product(pid)
        if not p: await safe_ans(q, "Not found.", alert=True); return
        await q.edit_message_text(txt_product(p), parse_mode=HTML,
                                  reply_markup=kb_product_detail(pid))

    # ── Start order — show quantity picker ────────────
    elif data.startswith("order_start_"):
        pid = int(data[12:])
        p   = db.get_product(pid)
        if not p: await safe_ans(q, "Not found.", alert=True); return
        if p["stock"] < 1:
            await safe_ans(q, "❌ Out of stock!", alert=True); return
        await q.edit_message_text(
            f"📦 <b>{p['name']}</b>\n\n"
            f"💰 Price : <b>${p['price']:.2f}</b> per unit\n"
            f"📦 Stock : <b>{p['stock']} available</b>\n\n"
            f"<b>How many do you need?</b>\n"
            f"<i>Tap a quantity or enter custom.</i>",
            parse_mode=HTML,
            reply_markup=kb_qty(pid, p["price"], p["stock"]))

    # ── Quick quantity selected ───────────────────────
    elif data.startswith("qty_") and not data.startswith("qty_custom_"):
        parts = data.split("_")
        pid   = int(parts[1])
        qty   = int(parts[2])
        p     = db.get_product(pid)
        if not p: await safe_ans(q, "Not found.", alert=True); return
        if qty > p["stock"]:
            await safe_ans(q, f"Only {p['stock']} in stock!", alert=True); return
        total = p["price"] * qty
        await q.edit_message_text(
            f"🛒 <b>Order Summary</b>\n\n"
            f"📦 Product  : <b>{p['name']}</b>\n"
            f"🔢 Quantity : <b>{qty}</b>\n"
            f"💰 Price ea : <b>${p['price']:.2f}</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"💵 Total    : <b>${total:.2f} USDT</b>\n\n"
            f"Your balance: <b>${db.get_balance(user.id):.2f} USDT</b>",
            parse_mode=HTML,
            reply_markup=kb_confirm_order(pid, qty, total))

    # ── Custom quantity ───────────────────────────────
    elif data.startswith("qty_custom_"):
        pid = int(data[11:])
        p   = db.get_product(pid)
        if not p: return
        ctx.user_data["state"]       = "awaiting_qty"
        ctx.user_data["order_pid"]   = pid
        await q.edit_message_text(
            f"✏️ <b>Enter Quantity</b>\n\n"
            f"📦 <b>{p['name']}</b>\n"
            f"💰 ${p['price']:.2f} per unit\n"
            f"📦 Max available: <b>{p['stock']}</b>\n\n"
            f"Type the quantity you want:",
            parse_mode=HTML,
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("❌ Cancel", callback_data=f"acc_{pid}")
            ]]))

    # ── Confirm order ─────────────────────────────────
    elif data.startswith("confirm_order_"):
        parts = data.split("_")
        pid   = int(parts[2])
        qty   = int(parts[3])
        p     = db.get_product(pid)
        if not p: await safe_ans(q, "Not found.", alert=True); return
        if qty > p["stock"]:
            await safe_ans(q, f"Only {p['stock']} left!", alert=True); return
        total   = p["price"] * qty
        balance = db.get_balance(user.id)
        if balance < total:
            needed = total - balance
            await q.edit_message_text(
                f"❌ <b>Insufficient Balance</b>\n\n"
                f"💵 Order Total : <b>${total:.2f} USDT</b>\n"
                f"👛 Your Balance: <b>${balance:.2f} USDT</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"⚠️ You need <b>${needed:.2f} more.</b>",
                parse_mode=HTML,
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("💳 Deposit Funds", callback_data="deposit_menu")],
                    [InlineKeyboardButton("🏠 Main Menu",     callback_data="main_menu")],
                ])); return

        db.deduct_balance(user.id, total)
        order_ref = db.new_ref("TG")
        db.save_order(user.id, p, order_ref, qty)
        db.reduce_stock(pid, qty)

        await q.edit_message_text(
            f"✅ <b>Order Placed!</b>\n\n"
            f"📦 Product  : <b>{p['name']}</b>\n"
            f"🔢 Quantity : <b>{qty}</b>\n"
            f"💰 Total    : <b>${total:.2f} USDT</b>\n"
            f"📋 Ref      : <code>{order_ref}</code>\n"
            f"👛 Balance  : <b>${db.get_balance(user.id):.2f} USDT</b>\n\n"
            f"⏳ <b>Your product will be delivered within 5–10 minutes.</b>\n"
            f"Not received? Contact {SUPPORT}",
            parse_mode=HTML,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("📋 My Orders",         callback_data="history")],
                [InlineKeyboardButton("🛍 Continue Shopping", callback_data="products")],
            ]))

    # ── Wallet ────────────────────────────────────────
    elif data == "wallet":
        bal = db.get_balance(user.id)
        await q.edit_message_text(txt_wallet_info(bal), parse_mode=HTML, reply_markup=kb_wallet())

    # ── Deposit — pick network ─────────────────────────
    elif data == "deposit_menu":
        wallets = db.get_active_wallets()
        await q.edit_message_text(
            "💳 <b>Deposit Funds</b>\n\nMinimum: <b>$1.00 USDT</b>\n\nSelect a payment network:",
            parse_mode=HTML, reply_markup=kb_networks(wallets))

    # ── Deposit — show address ─────────────────────────
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
            f"After sending, tap the button below.",
            parse_mode=HTML, reply_markup=kb_sent(key))

    # ── User tapped "I Have Sent" ──────────────────────
    elif data.startswith("sent_"):
        ctx.user_data["state"]       = "awaiting_txn"
        ctx.user_data["dep_ref"]     = db.new_ref("DEP")
        ctx.user_data["dep_network"] = ctx.user_data.get(
            "dep_network_label", ctx.user_data.get("dep_network", "Unknown"))
        await q.edit_message_text(
            "🔑 <b>Enter Transaction ID</b>\n\n"
            "Please send your <b>Transaction ID (TXN ID / Hash)</b>.\n\n"
            "<i>You can find it in your wallet's transaction history.</i>",
            parse_mode=HTML,
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("❌ Cancel", callback_data="wallet")
            ]]))

    # ── Profile ───────────────────────────────────────
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

    # ── History ───────────────────────────────────────
    elif data == "history":
        orders = db.get_orders(user.id)
        await q.edit_message_text(txt_history(orders), parse_mode=HTML, reply_markup=kb_back_main())

    # ── Redeem ────────────────────────────────────────
    elif data == "redeem":
        ctx.user_data["state"] = "awaiting_redeem"
        await q.edit_message_text(
            "🎁 <b>Redeem Code</b>\n\nSend your code:",
            parse_mode=HTML,
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("❌ Cancel", callback_data="main_menu")
            ]]))

    # ── Support ───────────────────────────────────────
    elif data == "support":
        await q.edit_message_text(
            f"🆘 <b>Support</b>\n\nContact us: {SUPPORT}",
            parse_mode=HTML, reply_markup=kb_back_main())


# ══════════════════════════════════════════════════════
#  MESSAGE HANDLER
# ══════════════════════════════════════════════════════

async def on_text(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user  = update.effective_user
    text  = (update.message.text or "").strip()
    state = ctx.user_data.get("state")
    db.ensure_user(user.id, user.first_name, user.username or "")

    # ── Quantity input ────────────────────────────────
    if state == "awaiting_qty":
        pid = ctx.user_data.get("order_pid")
        p   = db.get_product(pid) if pid else None
        if not p:
            ctx.user_data.pop("state", None)
            await update.message.reply_text("⚠️ Product not found.", reply_markup=kb_back_main()); return
        try:
            qty = int(text)
            if qty < 1: raise ValueError
        except ValueError:
            await update.message.reply_text("⚠️ Please enter a valid number (e.g. 3)."); return
        if qty > p["stock"]:
            await update.message.reply_text(
                f"⚠️ Only <b>{p['stock']}</b> in stock. Enter a lower quantity.",
                parse_mode=HTML); return
        ctx.user_data.pop("state", None)
        ctx.user_data.pop("order_pid", None)
        total = p["price"] * qty
        await update.message.reply_text(
            f"🛒 <b>Order Summary</b>\n\n"
            f"📦 Product  : <b>{p['name']}</b>\n"
            f"🔢 Quantity : <b>{qty}</b>\n"
            f"💰 Price ea : <b>${p['price']:.2f}</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"💵 Total    : <b>${total:.2f} USDT</b>\n\n"
            f"Your balance: <b>${db.get_balance(user.id):.2f} USDT</b>",
            parse_mode=HTML,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton(f"✅ Confirm  (${total:.2f})",
                                      callback_data=f"confirm_order_{pid}_{qty}")],
                [InlineKeyboardButton("❌ Cancel", callback_data="products")],
            ]))

    # ── TXN ID input ──────────────────────────────────
    elif state == "awaiting_txn":
        ctx.user_data.pop("state", None)
        ref     = ctx.user_data.pop("dep_ref",    db.new_ref("DEP"))
        network = ctx.user_data.pop("dep_network", "Unknown")
        txn_id  = text
        db.save_deposit_txn(user.id, ref, network, txn_id)
        await update.message.reply_text(
            f"✅ <b>Deposit Request Submitted!</b>\n\n"
            f"⚡ Your payment is being verified.\n"
            f"📋 Status  : <b>Pending</b>\n"
            f"🔑 TXN ID  : <code>{txn_id}</code>\n"
            f"⏳ Time    : 3 Hours (Max)\n\n"
            f"📌 Reference: <code>{ref}</code>",
            parse_mode=HTML, reply_markup=kb_back_main())

    # ── Redeem code ───────────────────────────────────
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


# ══════════════════════════════════════════════════════
#  MAIN
# ══════════════════════════════════════════════════════

async def run():
    db.init_db()
    app = Application.builder().token(STORE_BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CallbackQueryHandler(on_callback))
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
