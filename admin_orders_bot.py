#!/usr/bin/env python3
"""admin_orders_bot.py — Order notifications & delivery."""

import asyncio, logging, os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, filters, ContextTypes,
)
from telegram.error import BadRequest, TelegramError
import shared_db as db

ORDERS_BOT_TOKEN = os.environ["ORDERS_TOKEN"]
ADMIN_IDS        = [8093715116]
NOTIFY_INTERVAL  = 15

HTML = "HTML"
logging.basicConfig(format="%(asctime)s — %(levelname)s — %(message)s", level=logging.INFO)
logging.getLogger("httpx").setLevel(logging.WARNING)

def is_admin(uid): return uid in ADMIN_IDS

async def safe_ans(q, text="", alert=False):
    try: await q.answer(text, show_alert=alert)
    except BadRequest: pass

def kb_home():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📋 Recent Orders", callback_data="ord_recent"),
         InlineKeyboardButton("📊 Stats",         callback_data="ord_stats")],
        [InlineKeyboardButton("📦 Deliver Order", callback_data="ord_deliver")],
    ])

def kb_back_home():
    return InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Orders Home", callback_data="ord_home")]])

async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("⛔ Unauthorised."); return
    u, o, po, r, pd = db.get_stats()
    await update.message.reply_text(
        f"📦 <b>Admin Orders Bot</b>\n\n"
        f"📦 Orders: <b>{o}</b>  (⏳ {po} pending)\n"
        f"💰 Revenue: <b>${r:.2f} USDT</b>\n\n"
        f"You'll get notified here for every new order.\n"
        f"Tap ✅ Deliver Now on a notification to send product to customer.",
        parse_mode=HTML, reply_markup=kb_home())

async def on_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q    = update.callback_query
    data = q.data
    user = update.effective_user
    if not is_admin(user.id): await safe_ans(q, "⛔ Unauthorised.", alert=True); return
    await safe_ans(q)

    if data == "ord_home":
        u, o, po, r, _ = db.get_stats()
        await q.edit_message_text(
            f"📦 <b>Orders Bot</b>\n\nOrders: <b>{o}</b> (⏳{po}) | Revenue: <b>${r:.2f}</b>",
            parse_mode=HTML, reply_markup=kb_home())

    elif data == "ord_recent":
        orders = db.get_recent_orders_admin(20)
        if not orders:
            await q.edit_message_text("📋 No orders yet.", reply_markup=kb_back_home()); return
        lines = []
        for ref, name, price, qty, status, created, uname, username, tg_id in orders:
            icon = "✅" if status == "delivered" else "⏳"
            who  = f"@{username}" if username else str(tg_id)
            lines.append(
                f"{icon} <code>{ref}</code>\n"
                f"   📦 {name} × {qty} — ${price:.2f}\n"
                f"   👤 {uname} ({who})")
        await q.edit_message_text(
            "📋 <b>Recent Orders</b>\n\n" + "\n\n".join(lines[:10]),
            parse_mode=HTML, reply_markup=kb_back_home())

    elif data == "ord_stats":
        u, o, po, r, pd = db.get_stats()
        await q.edit_message_text(
            f"📊 <b>Stats</b>\n\n"
            f"👥 Users: <b>{u}</b>\n"
            f"📦 Orders: <b>{o}</b> (⏳{po})\n"
            f"💰 Revenue: <b>${r:.2f}</b>",
            parse_mode=HTML, reply_markup=kb_back_home())

    elif data == "ord_deliver":
        ctx.user_data["action"] = "deliver_manual"
        await q.edit_message_text(
            "📦 Send the order reference (e.g. <code>#TG12345</code>):",
            parse_mode=HTML,
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("❌ Cancel", callback_data="ord_home")
            ]]))

    elif data.startswith("ord_do_"):
        # ord_do_ORDERREF_TGID
        parts     = data[7:].rsplit("_", 1)
        order_ref = parts[0]
        tg_id     = int(parts[1])
        await _deliver(ctx.bot, order_ref, tg_id, q)

    elif data.startswith("ord_send_"):
        # admin sends product manually from this bot
        # ord_send_ORDERREF_TGID
        parts     = data[9:].rsplit("_", 1)
        order_ref = parts[0]
        tg_id     = int(parts[1])
        ctx.user_data["action"]           = "sending_product"
        ctx.user_data["deliver_ref"]      = order_ref
        ctx.user_data["deliver_tg_id"]    = tg_id
        await q.edit_message_text(
            f"📤 <b>Send Product</b>\n\n"
            f"Order: <code>{order_ref}</code>\n\n"
            f"Forward or send the product content now.\n"
            f"<i>Text, photo, document, video — anything.</i>",
            parse_mode=HTML,
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("❌ Cancel", callback_data="ord_home")
            ]]))


async def _deliver(bot, order_ref, tg_id, q=None):
    """Deliver product stored in DB."""
    result = db.deliver_order(order_ref)
    if not result:
        msg = f"⚠️ Order <code>{order_ref}</code> not found."
        if q: await q.edit_message_text(msg, parse_mode=HTML, reply_markup=kb_back_home())
        return

    customer_tg_id, dtype, dcontent, qty = result
    ok = True
    try:
        if dtype == "photo":
            await bot.send_photo(customer_tg_id, dcontent,
                caption=f"✅ <b>Your order is here!</b>\n📋 Ref: <code>{order_ref}</code>\n🔢 Qty: {qty}",
                parse_mode=HTML)
        elif dtype == "document":
            await bot.send_document(customer_tg_id, dcontent,
                caption=f"✅ <b>Your order is here!</b>\n📋 Ref: <code>{order_ref}</code>\n🔢 Qty: {qty}",
                parse_mode=HTML)
        elif dtype == "video":
            await bot.send_video(customer_tg_id, dcontent,
                caption=f"✅ <b>Your order is here!</b>\n📋 Ref: <code>{order_ref}</code>\n🔢 Qty: {qty}",
                parse_mode=HTML)
        else:
            await bot.send_message(customer_tg_id,
                f"✅ <b>Your order is here!</b>\n\n"
                f"📋 Ref: <code>{order_ref}</code>\n"
                f"🔢 Quantity: <b>{qty}</b>\n\n"
                f"<code>{dcontent}</code>",
                parse_mode=HTML)
    except TelegramError as e:
        ok = False; logging.error(f"Delivery failed: {e}")

    status_msg = (
        f"{'✅' if ok else '⚠️'} Order <code>{order_ref}</code> — "
        f"{'delivered to customer.' if ok else 'FAILED (customer may have blocked bot).'}"
    )
    if q:
        await q.edit_message_text(status_msg, parse_mode=HTML, reply_markup=kb_back_home())
    else:
        for aid in ADMIN_IDS:
            try: await bot.send_message(aid, status_msg, parse_mode=HTML)
            except TelegramError: pass


async def on_any_message(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id): return
    action = ctx.user_data.get("action")
    if not action: return

    # ── Manual order ref ──────────────────────────────
    if action == "deliver_manual":
        ctx.user_data.pop("action")
        order_ref = (update.message.text or "").strip()
        result    = db.deliver_order(order_ref)
        if not result:
            await update.message.reply_text(
                f"⚠️ Not found: <code>{order_ref}</code>", parse_mode=HTML); return
        customer_tg_id, dtype, dcontent, qty = result
        await _deliver(ctx.bot, order_ref, customer_tg_id)
        await update.message.reply_text(
            f"✅ Done: <code>{order_ref}</code>", parse_mode=HTML, reply_markup=kb_back_home())

    # ── Admin manually sends product content ──────────
    elif action == "sending_product":
        ctx.user_data.pop("action")
        order_ref = ctx.user_data.pop("deliver_ref", "")
        tg_id     = ctx.user_data.pop("deliver_tg_id", None)
        if not tg_id: return

        msg = update.message
        ok  = True
        try:
            if msg.photo:
                await ctx.bot.send_photo(tg_id, msg.photo[-1].file_id,
                    caption=f"✅ <b>Your order is here!</b>\n📋 Ref: <code>{order_ref}</code>",
                    parse_mode=HTML)
            elif msg.document:
                await ctx.bot.send_document(tg_id, msg.document.file_id,
                    caption=f"✅ <b>Your order is here!</b>\n📋 Ref: <code>{order_ref}</code>",
                    parse_mode=HTML)
            elif msg.video:
                await ctx.bot.send_video(tg_id, msg.video.file_id,
                    caption=f"✅ <b>Your order is here!</b>\n📋 Ref: <code>{order_ref}</code>",
                    parse_mode=HTML)
            elif msg.text:
                await ctx.bot.send_message(tg_id,
                    f"✅ <b>Your order is here!</b>\n\n"
                    f"📋 Ref: <code>{order_ref}</code>\n\n"
                    f"<code>{msg.text}</code>",
                    parse_mode=HTML)
            # Mark delivered in DB
            db.deliver_order(order_ref)
        except TelegramError as e:
            ok = False; logging.error(f"Manual send failed: {e}")

        await update.message.reply_text(
            f"{'✅ Product sent!' if ok else '⚠️ Failed to send. Customer may have blocked the bot.'}",
            reply_markup=kb_back_home())


async def notify_loop(bot):
    while True:
        try:
            for row in db.get_unnotified_orders():
                oid, tg_id, ref, prod_name, price, qty, created, uname, username = row
                who  = f"@{username}" if username else f"ID:{tg_id}"
                unit = price / qty if qty else price
                text = (
                    f"🛍 <b>New Order!</b>\n\n"
                    f"👤 Customer  : {uname} ({who})\n"
                    f"📦 Product   : <b>{prod_name}</b>\n"
                    f"🔢 Quantity  : <b>{qty}</b>\n"
                    f"💰 Unit Price: <b>${unit:.2f}</b>\n"
                    f"💵 Total     : <b>${price:.2f} USDT</b>\n"
                    f"📋 Ref       : <code>{ref}</code>\n"
                    f"📅 Time      : {created}"
                )
                kb = InlineKeyboardMarkup([
                    [InlineKeyboardButton("✅ Deliver (from DB)",      callback_data=f"ord_do_{ref}_{tg_id}")],
                    [InlineKeyboardButton("📤 Send Product Manually",  callback_data=f"ord_send_{ref}_{tg_id}")],
                ])
                for aid in ADMIN_IDS:
                    try: await bot.send_message(aid, text, parse_mode=HTML, reply_markup=kb)
                    except TelegramError: pass
                db.mark_order_notified(oid)
        except Exception as e:
            logging.error(f"notify_loop: {e}")
        await asyncio.sleep(NOTIFY_INTERVAL)


async def run():
    app = Application.builder().token(ORDERS_BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CallbackQueryHandler(on_callback))
    app.add_handler(MessageHandler(
        (filters.TEXT | filters.PHOTO | filters.Document.ALL | filters.VIDEO)
        & ~filters.COMMAND,
        on_any_message))
    print("✅ Admin Orders Bot running...")
    async with app:
        await app.start()
        await app.updater.start_polling(allowed_updates=Update.ALL_TYPES)
        asyncio.create_task(notify_loop(app.bot))
        await asyncio.Event().wait()
        await app.updater.stop()
        await app.stop()

if __name__ == "__main__":
    asyncio.run(run())
