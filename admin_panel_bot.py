#!/usr/bin/env python3
"""admin_panel_bot.py — Manage products & wallets."""

import asyncio, logging, os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, filters, ContextTypes,
)
from telegram.error import BadRequest
import shared_db as db

PANEL_BOT_TOKEN = os.environ["PANEL_TOKEN"]
ADMIN_IDS       = [8093715116]

HTML = "HTML"
logging.basicConfig(format="%(asctime)s — %(levelname)s — %(message)s", level=logging.INFO)
logging.getLogger("httpx").setLevel(logging.WARNING)

def is_admin(uid): return uid in ADMIN_IDS

async def safe_ans(q, text="", alert=False):
    try: await q.answer(text, show_alert=alert)
    except BadRequest: pass

def kb_home():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📦 Products",     callback_data="pnl_products"),
         InlineKeyboardButton("💳 Wallets",      callback_data="pnl_wallets")],
        [InlineKeyboardButton("👥 Users",        callback_data="pnl_users"),
         InlineKeyboardButton("📊 Stats",        callback_data="pnl_stats")],
        [InlineKeyboardButton("🎁 Redeem Codes", callback_data="pnl_codes")],
    ])

def kb_back_home():
    return InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Panel Home", callback_data="pnl_home")]])

def kb_product_list(products):
    rows = []
    for p in products:
        icon  = "✅" if p["active"] else "🔴"
        short = p["name"][:28] + "…" if len(p["name"]) > 28 else p["name"]
        rows.append([InlineKeyboardButton(
            f"{icon} [{p['id']}] {short} — ${p['price']:.2f} | 📦{p['stock']}",
            callback_data=f"pnl_p_{p['id']}")])
    rows.append([InlineKeyboardButton("➕ Add Product", callback_data="pnl_add"),
                 InlineKeyboardButton("🏠 Home",        callback_data="pnl_home")])
    return InlineKeyboardMarkup(rows)

def kb_product_actions(pid):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✏️ Name",   callback_data=f"pnl_pname_{pid}"),
         InlineKeyboardButton("💰 Price",  callback_data=f"pnl_pprice_{pid}"),
         InlineKeyboardButton("📦 Stock",  callback_data=f"pnl_pstock_{pid}")],
        [InlineKeyboardButton("📝 Delivery Content", callback_data=f"pnl_pdel_{pid}")],
        [InlineKeyboardButton("🔁 ON/OFF", callback_data=f"pnl_ptoggle_{pid}"),
         InlineKeyboardButton("🗑 Delete", callback_data=f"pnl_pdelconfirm_{pid}")],
        [InlineKeyboardButton("⬅️ Back",   callback_data="pnl_products")],
    ])

def kb_wallet_list(wallets):
    rows = []
    for w in wallets:
        icon  = "✅" if w["active"] else "🔴"
        short = w["address"][:20] + "…"
        rows.append([InlineKeyboardButton(
            f"{icon} {w['label']}  •  {short}",
            callback_data=f"pnl_w_{w['key']}")])
    rows.append([InlineKeyboardButton("🏠 Home", callback_data="pnl_home")])
    return InlineKeyboardMarkup(rows)

def kb_wallet_actions(key):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✏️ Change Address", callback_data=f"pnl_waddr_{key}"),
         InlineKeyboardButton("🔁 ON/OFF",         callback_data=f"pnl_wtoggle_{key}")],
        [InlineKeyboardButton("⬅️ Back",            callback_data="pnl_wallets")],
    ])

async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("⛔ Unauthorised."); return
    u, o, po, r, pd = db.get_stats()
    await update.message.reply_text(
        f"🔧 <b>Admin Panel Bot</b>\n\n"
        f"👥 Users: <b>{u}</b>  |  📦 Orders: <b>{o}</b>\n"
        f"💰 Revenue: <b>${r:.2f}</b>  |  ⏳ Deps: <b>{pd}</b>",
        parse_mode=HTML, reply_markup=kb_home())

async def on_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q    = update.callback_query
    data = q.data
    user = update.effective_user
    if not is_admin(user.id): await safe_ans(q, "⛔ Unauthorised.", alert=True); return
    await safe_ans(q)

    if data == "pnl_home":
        u, o, po, r, pd = db.get_stats()
        await q.edit_message_text(
            f"🔧 <b>Admin Panel</b>\n\n"
            f"👥 Users: <b>{u}</b> | 📦 Orders: <b>{o}</b>\n"
            f"💰 Revenue: <b>${r:.2f}</b> | ⏳ Deposits: <b>{pd}</b>",
            parse_mode=HTML, reply_markup=kb_home())

    elif data == "pnl_products":
        prods = db.get_all_products()
        await q.edit_message_text(
            f"📦 <b>Products</b>  ({len(prods)} total)\n✅=active  🔴=hidden",
            parse_mode=HTML, reply_markup=kb_product_list(prods))

    elif data == "pnl_add":
        ctx.user_data["action"] = ("add_content", None)
        await q.edit_message_text(
            "➕ <b>Add New Product</b>\n\n"
            "📩 <b>Step 1:</b> Send or forward the product content.\n\n"
            "Kuch bhi bhejo — photo, video, document, ya text.\n"
            "Caption mein likho: <code>Name | Price | Stock</code>\n\n"
            "Example caption:\n"
            "<code>ChatGPT Plus 1M | 2.50 | 30</code>\n\n"
            "<i>Caption nahi diya? Agle step mein poochhunga.</i>",
            parse_mode=HTML,
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("❌ Cancel", callback_data="pnl_products")
            ]]))

    elif data.startswith("pnl_p_") and not any(data.startswith(x) for x in
          ["pnl_pname_","pnl_pprice_","pnl_pstock_","pnl_pdel_","pnl_ptoggle_","pnl_pdelconfirm_","pnl_pdelete_"]):
        pid = int(data[6:])
        p   = db.get_product(pid)
        if not p: await safe_ans(q, "Not found.", alert=True); return
        status = "✅ Active" if p["active"] else "🔴 Hidden"
        await q.edit_message_text(
            f"📦 <b>Product #{pid}</b>\n\n"
            f"Name    : <b>{p['name']}</b>\n"
            f"Price   : <b>${p['price']:.2f} USDT</b>\n"
            f"Stock   : <b>{p['stock']}</b>\n"
            f"Delivery: <b>{p['delivery_type']}</b>\n"
            f"Status  : {status}",
            parse_mode=HTML, reply_markup=kb_product_actions(pid))

    elif data.startswith("pnl_pname_"):
        pid = int(data[10:]); ctx.user_data["action"] = ("edit_name", pid)
        await q.edit_message_text(f"✏️ Send new name for product #{pid}:", parse_mode=HTML,
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel", callback_data=f"pnl_p_{pid}")]]))

    elif data.startswith("pnl_pprice_"):
        pid = int(data[11:]); ctx.user_data["action"] = ("edit_price", pid)
        await q.edit_message_text(f"💰 Send new price for product #{pid} (e.g. <code>2.50</code>):",
            parse_mode=HTML,
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel", callback_data=f"pnl_p_{pid}")]]))

    elif data.startswith("pnl_pstock_"):
        pid = int(data[11:]); ctx.user_data["action"] = ("edit_stock", pid)
        await q.edit_message_text(f"📦 Send new stock for product #{pid} (e.g. <code>50</code>):",
            parse_mode=HTML,
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel", callback_data=f"pnl_p_{pid}")]]))

    elif data.startswith("pnl_pdel_") and not data.startswith("pnl_pdelconfirm_"):
        pid = int(data[9:]); ctx.user_data["action"] = ("edit_delivery", pid)
        await q.edit_message_text(
            f"📝 <b>Edit Delivery Content — Product #{pid}</b>\n\n"
            f"Jo bhi bhejo (photo, video, document, text) — wahi delivery content ban jayega.",
            parse_mode=HTML,
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel", callback_data=f"pnl_p_{pid}")]]))

    elif data.startswith("pnl_ptoggle_"):
        pid    = int(data[12:])
        active = db.toggle_product(pid)
        status = "✅ Active" if active else "🔴 Hidden"
        await safe_ans(q, f"Product is now {status}", alert=True)
        p = db.get_product(pid)
        if p:
            await q.edit_message_text(
                f"📦 <b>Product #{pid}</b>\n\nName: {p['name']}\nStatus: {status}",
                parse_mode=HTML, reply_markup=kb_product_actions(pid))

    elif data.startswith("pnl_pdelconfirm_"):
        pid = int(data[16:])
        await q.edit_message_text(f"🗑 <b>Delete Product #{pid}?</b>\n\nThis cannot be undone.",
            parse_mode=HTML,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("✅ Yes, Delete", callback_data=f"pnl_pdelete_{pid}"),
                 InlineKeyboardButton("❌ Cancel",      callback_data=f"pnl_p_{pid}")],
            ]))

    elif data.startswith("pnl_pdelete_"):
        pid = int(data[12:])
        db.delete_product(pid)
        await q.edit_message_text(f"🗑 Product #{pid} deleted.", reply_markup=kb_back_home())

    elif data == "pnl_wallets":
        await q.edit_message_text("💳 <b>Wallet Addresses</b>", parse_mode=HTML,
                                  reply_markup=kb_wallet_list(db.get_all_wallets()))

    elif data.startswith("pnl_w_") and not data.startswith("pnl_waddr_") and not data.startswith("pnl_wtoggle_"):
        key = data[6:]
        ws  = {w["key"]: w for w in db.get_all_wallets()}
        w   = ws.get(key)
        if not w: await safe_ans(q, "Not found.", alert=True); return
        status = "✅ Active" if w["active"] else "🔴 Hidden"
        await q.edit_message_text(
            f"💳 <b>{w['label']}</b>\n\n"
            f"Address : <code>{w['address']}</code>\n"
            f"Status  : {status}",
            parse_mode=HTML, reply_markup=kb_wallet_actions(key))

    elif data.startswith("pnl_waddr_"):
        key = data[10:]; ctx.user_data["action"] = ("edit_wallet", key)
        await q.edit_message_text(f"✏️ Send new address for <b>{key}</b>:", parse_mode=HTML,
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel", callback_data="pnl_wallets")]]))

    elif data.startswith("pnl_wtoggle_"):
        key    = data[12:]
        active = db.toggle_wallet(key)
        status = "✅ Active" if active else "🔴 Hidden"
        await safe_ans(q, f"Wallet is now {status}", alert=True)
        await q.edit_message_text("💳 <b>Wallet Addresses</b>", parse_mode=HTML,
                                  reply_markup=kb_wallet_list(db.get_all_wallets()))

    elif data == "pnl_users":
        users = db.get_all_users()
        lines = [f"👤 <code>{r[0]}</code> — {r[1]} — 💰${r[3]:.2f}" for r in users]
        await q.edit_message_text(
            "👥 <b>Users (last 50)</b>\n\n" + "\n".join(lines), parse_mode=HTML,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("💰 Set Balance", callback_data="pnl_setbal")],
                [InlineKeyboardButton("🏠 Home",        callback_data="pnl_home")],
            ]))

    elif data == "pnl_setbal":
        ctx.user_data["action"] = ("set_balance", None)
        await q.edit_message_text(
            "💰 Send: <code>USER_ID AMOUNT</code>\n\nExample: <code>123456789 10.00</code>",
            parse_mode=HTML,
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel", callback_data="pnl_users")]]))

    elif data == "pnl_stats":
        u, o, po, r, pd = db.get_stats()
        prods = db.get_all_products()
        await q.edit_message_text(
            f"📊 <b>Statistics</b>\n\n"
            f"👥 Users        : <b>{u}</b>\n"
            f"📦 Total Orders : <b>{o}</b>  (⏳ {po} pending)\n"
            f"💰 Revenue      : <b>${r:.2f} USDT</b>\n"
            f"💳 Pending Deps : <b>{pd}</b>\n"
            f"🛍 Products     : <b>{sum(1 for p in prods if p['active'])}/{len(prods)} active</b>",
            parse_mode=HTML, reply_markup=kb_back_home())

    elif data == "pnl_codes":
        ctx.user_data["action"] = ("create_code", None)
        await q.edit_message_text(
            "🎁 <b>Create Redeem Code</b>\n\nSend: <code>CODE AMOUNT MAX_USES</code>\n\nExample: <code>SAVE5 5.00 10</code>",
            parse_mode=HTML,
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel", callback_data="pnl_home")]]))


# ══════════════════════════════════════════════════════
#  SMART CONTENT EXTRACTOR
# ══════════════════════════════════════════════════════

async def _get_content(message):
    """Extract delivery type and content from any message."""
    if message.photo:     return "photo",    message.photo[-1].file_id
    if message.document:  return "document", message.document.file_id
    if message.video:     return "video",    message.video.file_id
    if message.audio:     return "audio",    message.audio.file_id
    if message.sticker:   return "text",     message.sticker.file_id
    if message.text:      return "text",     message.text
    if message.caption:   return "text",     message.caption
    return "text", ""

def _parse_details(text):
    """Parse 'Name | Price | Stock' from text. Returns (name, price, stock) or None."""
    if not text: return None
    parts = [x.strip() for x in text.split("|")]
    if len(parts) < 3: return None
    try:
        return parts[0], float(parts[1]), int(parts[2])
    except ValueError:
        return None


# ══════════════════════════════════════════════════════
#  MESSAGE HANDLER — handles all admin messages
# ══════════════════════════════════════════════════════

async def on_any_message(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id): return
    action = ctx.user_data.get("action")
    if not action: return
    kind    = action[0]
    message = update.message

    # ── ADD PRODUCT — single message flow ─────────────
    if kind == "add_content":
        dtype, dcontent = await _get_content(message)
        if not dcontent:
            await message.reply_text("⚠️ Kuch samajh nahi aaya. Dobara bhejo."); return

        # Try to get details from caption or text
        caption_text = (message.caption or message.text or "").strip()
        details = _parse_details(caption_text)

        if details:
            # All info in one message — save directly
            name, price, stock = details
            ctx.user_data.pop("action", None)
            pid = db.add_product(name, price, stock, dtype, dcontent)
            await message.reply_text(
                f"✅ <b>Product Added!</b>\n\n"
                f"🆔 ID     : #{pid}\n"
                f"📦 Name   : <b>{name}</b>\n"
                f"💰 Price  : <b>${price:.2f} USDT</b>\n"
                f"📦 Stock  : <b>{stock}</b>\n"
                f"📎 Type   : <b>{dtype}</b>",
                parse_mode=HTML, reply_markup=kb_back_home())
        else:
            # Content saved, now ask for details
            ctx.user_data["action"]         = ("add_details", None)
            ctx.user_data["new_prod_dtype"] = dtype
            ctx.user_data["new_prod_dcont"] = dcontent
            await message.reply_text(
                f"✅ Content saved! (<b>{dtype}</b>)\n\n"
                f"Ab product details bhejo:\n"
                f"<code>Name | Price | Stock</code>\n\n"
                f"Example: <code>ChatGPT Plus 1M | 2.50 | 30</code>",
                parse_mode=HTML)

    elif kind == "add_details":
        details = _parse_details(message.text or "")
        if not details:
            await message.reply_text(
                "⚠️ Sahi format bhejo:\n<code>Name | Price | Stock</code>\n\n"
                "Example: <code>Netflix 1M | 3.00 | 20</code>",
                parse_mode=HTML)
            ctx.user_data["action"] = ("add_details", None); return
        name, price, stock = details
        dtype    = ctx.user_data.pop("new_prod_dtype", "text")
        dcontent = ctx.user_data.pop("new_prod_dcont", "")
        ctx.user_data.pop("action", None)
        pid = db.add_product(name, price, stock, dtype, dcontent)
        await message.reply_text(
            f"✅ <b>Product Added!</b>\n\n"
            f"🆔 ID     : #{pid}\n"
            f"📦 Name   : <b>{name}</b>\n"
            f"💰 Price  : <b>${price:.2f} USDT</b>\n"
            f"📦 Stock  : <b>{stock}</b>\n"
            f"📎 Type   : <b>{dtype}</b>",
            parse_mode=HTML, reply_markup=kb_back_home())

    # ── EDIT DELIVERY ──────────────────────────────────
    elif kind == "edit_delivery":
        pid = action[1]; ctx.user_data.pop("action", None)
        dtype, dcontent = await _get_content(message)
        if not dcontent: await message.reply_text("⚠️ Content samajh nahi aaya."); return
        db.update_product(pid, delivery_type=dtype, delivery_content=dcontent)
        await message.reply_text(f"✅ Delivery updated! ({dtype})", reply_markup=kb_back_home())

    # ── EDIT NAME ──────────────────────────────────────
    elif kind == "edit_name":
        pid = action[1]; ctx.user_data.pop("action", None)
        db.update_product(pid, name=(message.text or "").strip())
        await message.reply_text("✅ Name updated!", reply_markup=kb_back_home())

    # ── EDIT PRICE ─────────────────────────────────────
    elif kind == "edit_price":
        pid = action[1]; ctx.user_data.pop("action", None)
        try:
            price = float((message.text or "").strip())
            db.update_product(pid, price=price)
            await message.reply_text(f"✅ Price set to ${price:.2f}", reply_markup=kb_back_home())
        except ValueError:
            await message.reply_text("⚠️ Invalid price."); ctx.user_data["action"] = action

    # ── EDIT STOCK ─────────────────────────────────────
    elif kind == "edit_stock":
        pid = action[1]; ctx.user_data.pop("action", None)
        try:
            stock = int((message.text or "").strip())
            db.update_product(pid, stock=stock)
            await message.reply_text(f"✅ Stock set to {stock}", reply_markup=kb_back_home())
        except ValueError:
            await message.reply_text("⚠️ Invalid stock."); ctx.user_data["action"] = action

    # ── EDIT WALLET ────────────────────────────────────
    elif kind == "edit_wallet":
        key = action[1]; ctx.user_data.pop("action", None)
        addr = (message.text or "").strip()
        if len(addr) < 10: await message.reply_text("⚠️ Too short."); return
        db.update_wallet(key, addr)
        await message.reply_text(f"✅ Address updated!\n<code>{addr}</code>",
                                 parse_mode=HTML, reply_markup=kb_back_home())

    # ── SET BALANCE ────────────────────────────────────
    elif kind == "set_balance":
        ctx.user_data.pop("action", None)
        parts = (message.text or "").split()
        if len(parts) < 2:
            await message.reply_text("⚠️ Format: <code>USER_ID AMOUNT</code>", parse_mode=HTML); return
        try:
            db.set_balance(int(parts[0]), float(parts[1]))
            await message.reply_text("✅ Done!", reply_markup=kb_back_home())
        except ValueError:
            await message.reply_text("⚠️ Invalid format.")

    # ── CREATE REDEEM CODE ─────────────────────────────
    elif kind == "create_code":
        ctx.user_data.pop("action", None)
        parts = (message.text or "").split()
        if len(parts) < 3:
            await message.reply_text("⚠️ Format: <code>CODE AMOUNT MAX_USES</code>", parse_mode=HTML); return
        try:
            ok = db.create_redeem_code(parts[0], float(parts[1]), int(parts[2]))
            msg = f"✅ Code <code>{parts[0].upper()}</code> created!" if ok else "⚠️ Code already exists."
            await message.reply_text(msg, parse_mode=HTML, reply_markup=kb_back_home())
        except ValueError:
            await message.reply_text("⚠️ Invalid format.")


async def run():
    app = Application.builder().token(PANEL_BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CallbackQueryHandler(on_callback))
    app.add_handler(MessageHandler(
        (filters.TEXT | filters.PHOTO | filters.Document.ALL |
         filters.VIDEO | filters.AUDIO | filters.Sticker.ALL)
        & ~filters.COMMAND, on_any_message))
    print("✅ Admin Panel Bot running...")
    async with app:
        await app.start()
        await app.updater.start_polling(allowed_updates=Update.ALL_TYPES)
        await asyncio.Event().wait()
        await app.updater.stop()
        await app.stop()

if __name__ == "__main__":
    asyncio.run(run())
