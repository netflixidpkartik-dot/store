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
ADMIN_IDS        = [int(x) for x in os.environ["ADMIN_IDS"].split(",")]
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
        f"You'll get notified here for every new order.",
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
        for ref, name, price, status, created, uname, username, tg_id in orders:
            icon = "✅" if status == "delivered" else "⏳"
            who  = f"@{username}" if username else str(tg_id)
            lines.append(f"{icon} <code>{ref}</code>\n   📦 {name} — ${price:.2f}\n   👤 {uname} ({who})")
        await q.edit_message_text(
            "📋 <b>Recent Orders</b>\n\n" + "\n\n".join(lines[:10]),
            parse_mode=HTML, reply_markup=kb_back_home())

    elif data == "ord_stats":
        u, o, po, r, pd = db.get_stats()
        await q.edit_message_text(
            f"📊 <b>Stats</b>\n\n👥 Users: <b>{u}</b>\n📦 Orders: <b>{o}</b> (⏳{po})\n💰 Revenue: <b>${r:.2f}</b>",
            parse_mode=HTML, reply_markup=kb_back_home())

    elif data == "ord_deliver":
        ctx.user_data["action"] = "deliver_manual"
        await q.edit_message_text(
            "📦 Send the order reference (e.g. <code>#TG12345</code>):",
            parse_mode=HTML,
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel", callback_data="ord_home")]]))

    elif data.startswith("ord_do_"):
        parts     = data[7:].rsplit("_", 1)
        order_ref = parts[0]
        tg_id     = int(parts[1])
        await _deliver(update.get_bot(), order_ref, tg_id, q)


async def _deliver(bot, order_ref, tg_id, q=None):
    result = db.deliver_order(order_ref)
    if not result:
        msg = f"⚠️ Order <code>{order_ref}</code> not found."
        if q: await q.edit_message_text(msg, parse_mode=HTML, reply_markup=kb_back_home())
        return
    customer_tg_id, dtype, dcontent = result
    ok = True
    try:
        if dtype == "photo":
            await bot.send_photo(customer_tg_id, dcontent,
                caption=f"✅ <b>Order Delivered!</b>\nRef: <code>{order_ref}</code>", parse_mode=HTML)
        elif dtype == "document":
            await bot.send_document(customer_tg_id, dcontent,
                caption=f"✅ <b>Order Delivered!</b>\nRef: <code>{order_ref}</code>", parse_mode=HTML)
        elif dtype == "video":
            await bot.send_video(customer_tg_id, dcontent,
                caption=f"✅ <b>Order Delivered!</b>\nRef: <code>{order_ref}</code>", parse_mode=HTML)
        else:
            await bot.send_message(customer_tg_id,
                f"✅ <b>Your Order is Delivered!</b>\n\n"
                f"📋 Ref: <code>{order_ref}</code>\n\n"
                f"<code>{dcontent}</code>", parse_mode=HTML)
    except TelegramError as e:
        ok = False; logging.error(f"Delivery failed: {e}")

    status_msg = (
        f"{'✅' if ok else '⚠️'} Order <code>{order_ref}</code> — "
        f"{'sent to customer.' if ok else 'failed (customer may have blocked bot).'}"
    )
    if q:
        await q.edit_message_text(status_msg, parse_mode=HTML, reply_markup=kb_back_home())
    else:
        for aid in ADMIN_IDS:
            try: await bot.send_message(aid, status_msg, parse_mode=HTML)
            except TelegramError: pass


async def on_text(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id): return
    if ctx.user_data.get("action") == "deliver_manual":
        ctx.user_data.pop("action")
        order_ref = (update.message.text or "").strip()
        result    = db.deliver_order(order_ref)
        if not result:
            await update.message.reply_text(f"⚠️ Not found: <code>{order_ref}</code>", parse_mode=HTML); return
        customer_tg_id, dtype, dcontent = result
        await _deliver(update.get_bot(), order_ref, customer_tg_id)
        await update.message.reply_text(f"✅ Done: <code>{order_ref}</code>",
                                        parse_mode=HTML, reply_markup=kb_back_home())


async def notify_loop(bot):
    while True:
        try:
            for row in db.get_unnotified_orders():
                oid, tg_id, ref, prod_name, price, created, uname, username = row
                who = f"@{username}" if username else f"ID:{tg_id}"
                text = (
                    f"🛍 <b>New Order!</b>\n\n"
                    f"👤 Customer : {uname} ({who})\n"
                    f"📦 Product  : <b>{prod_name}</b>\n"
                    f"💰 Price    : <b>${price:.2f} USDT</b>\n"
                    f"📋 Ref      : <code>{ref}</code>\n"
                    f"📅 Time     : {created}"
                )
                kb = InlineKeyboardMarkup([[
                    InlineKeyboardButton("✅ Deliver Now", callback_data=f"ord_do_{ref}_{tg_id}")
                ]])
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
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_text))
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
