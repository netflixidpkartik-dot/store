#!/usr/bin/env python3
"""admin_payments_bot.py — Deposit proof review & approval."""

import asyncio, logging, os, sqlite3
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, filters, ContextTypes,
)
from telegram.error import BadRequest, TelegramError
import shared_db as db

PAYMENTS_BOT_TOKEN = os.environ["PAYMENTS_TOKEN"]
ADMIN_IDS          = [int(x) for x in os.environ["ADMIN_IDS"].split(",")]
NOTIFY_INTERVAL    = 15

HTML = "HTML"
logging.basicConfig(format="%(asctime)s — %(levelname)s — %(message)s", level=logging.INFO)
logging.getLogger("httpx").setLevel(logging.WARNING)

def is_admin(uid): return uid in ADMIN_IDS

async def safe_ans(q, text="", alert=False):
    try: await q.answer(text, show_alert=alert)
    except BadRequest: pass

def kb_home():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("💰 Pending Deposits", callback_data="pay_pending"),
         InlineKeyboardButton("📊 Stats",            callback_data="pay_stats")],
    ])

def kb_back_home():
    return InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Payments Home", callback_data="pay_home")]])

def kb_proof_actions(dep_id, tg_id):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Approve", callback_data=f"pay_approve_{dep_id}_{tg_id}"),
         InlineKeyboardButton("❌ Reject",  callback_data=f"pay_reject_{dep_id}_{tg_id}")],
    ])

async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("⛔ Unauthorised."); return
    _, _, _, _, pd = db.get_stats()
    await update.message.reply_text(
        f"💳 <b>Admin Payments Bot</b>\n\n"
        f"⏳ Pending Deposits: <b>{pd}</b>\n\n"
        f"You'll be notified when a customer submits payment proof.",
        parse_mode=HTML, reply_markup=kb_home())

async def on_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q    = update.callback_query
    data = q.data
    user = update.effective_user
    if not is_admin(user.id): await safe_ans(q, "⛔ Unauthorised.", alert=True); return
    await safe_ans(q)

    if data == "pay_home":
        _, _, _, _, pd = db.get_stats()
        await q.edit_message_text(
            f"💳 <b>Payments Bot</b>\n\n⏳ Pending: <b>{pd}</b>",
            parse_mode=HTML, reply_markup=kb_home())

    elif data == "pay_pending":
        con = sqlite3.connect(db.DB_FILE)
        all_p = con.execute("""
            SELECT d.id,d.tg_id,d.ref,d.network,d.txn_id,d.proof_type,d.created_at,u.name,u.username
            FROM deposits d LEFT JOIN users u ON d.tg_id=u.tg_id
            WHERE d.status='pending' ORDER BY d.id DESC LIMIT 20""").fetchall()
        con.close()
        if not all_p:
            await q.edit_message_text("✅ No pending deposits.", reply_markup=kb_back_home()); return
        rows = []
        for d in all_p:
            dep_id, tg_id, ref, network, txn_id, ptype, created, name, username = d
            who = f"@{username}" if username else str(tg_id)
            rows.append([InlineKeyboardButton(
                f"💰 {ref} | {name or who} | {network}",
                callback_data=f"pay_view_{dep_id}_{tg_id}")])
        rows.append([InlineKeyboardButton("🏠 Home", callback_data="pay_home")])
        await q.edit_message_text(f"💰 <b>Pending ({len(all_p)})</b>",
            parse_mode=HTML, reply_markup=InlineKeyboardMarkup(rows))

    elif data.startswith("pay_view_"):
        parts  = data[9:].split("_", 1)
        dep_id = int(parts[0]); tg_id = int(parts[1])
        con = sqlite3.connect(db.DB_FILE)
        d = con.execute("""
            SELECT d.id,d.tg_id,d.ref,d.network,d.txn_id,d.proof_type,d.proof_content,d.created_at,
                   u.name,u.username
            FROM deposits d LEFT JOIN users u ON d.tg_id=u.tg_id WHERE d.id=?""", (dep_id,)).fetchone()
        con.close()
        if not d: await safe_ans(q, "Not found.", alert=True); return
        _, _, ref, network, txn_id, ptype, pcontent, created, name, username = d
        who = f"@{username}" if username else str(tg_id)
        await q.edit_message_text(
            f"💰 <b>Deposit</b>\n\n"
            f"📋 Ref     : <code>{ref}</code>\n"
            f"👤 User    : {name} ({who})\n"
            f"🌐 Network : {network}\n"
            f"🔑 TXN ID  : <code>{txn_id or 'Not provided'}</code>\n"
            f"📅 Time    : {created}\n"
            f"📎 Type    : {ptype}",
            parse_mode=HTML, reply_markup=kb_proof_actions(dep_id, tg_id))

    elif data.startswith("pay_approve_"):
        parts  = data[12:].split("_", 1)
        dep_id = int(parts[0]); tg_id = int(parts[1])
        ctx.user_data["action"] = ("approve", dep_id, tg_id)
        await q.edit_message_text(
            "✅ Enter amount in USDT to credit (e.g. <code>5.00</code>):",
            parse_mode=HTML,
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel", callback_data="pay_pending")]]))

    elif data.startswith("pay_reject_"):
        parts  = data[11:].split("_", 1)
        dep_id = int(parts[0]); tg_id = int(parts[1])
        db.reject_deposit(dep_id)
        try:
            await update.get_bot().send_message(tg_id,
                "❌ <b>Deposit Rejected</b>\n\n"
                "Your payment proof could not be verified.\n"
                "Contact support if you think this is wrong.", parse_mode=HTML)
        except TelegramError: pass
        await q.edit_message_text("❌ Deposit rejected.", reply_markup=kb_back_home())

    elif data == "pay_stats":
        u, o, po, r, pd = db.get_stats()
        await q.edit_message_text(
            f"📊 <b>Payment Stats</b>\n\n"
            f"⏳ Pending : <b>{pd}</b>\n"
            f"💰 Revenue : <b>${r:.2f} USDT</b>\n"
            f"👥 Users   : <b>{u}</b>",
            parse_mode=HTML, reply_markup=kb_back_home())


async def on_text(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id): return
    action = ctx.user_data.get("action")
    if not action or action[0] != "approve": return
    _, dep_id, tg_id = action
    ctx.user_data.pop("action")
    try:
        amount = float((update.message.text or "").strip())
        if amount < 0.01: raise ValueError
    except ValueError:
        await update.message.reply_text("⚠️ Invalid amount."); return

    db.approve_deposit(dep_id, amount)
    await update.message.reply_text(
        f"✅ Approved! <b>${amount:.2f} USDT</b> → <code>{tg_id}</code>",
        parse_mode=HTML, reply_markup=kb_back_home())
    try:
        await update.get_bot().send_message(tg_id,
            f"✅ <b>Deposit Approved!</b>\n\n"
            f"💰 <b>${amount:.2f} USDT</b> added to your wallet.\n"
            f"You can now purchase products!", parse_mode=HTML)
    except TelegramError: pass


async def notify_loop(bot):
    while True:
        try:
            for row in db.get_unnotified_deposits():
                dep_id, tg_id, ref, network, ptype, pcontent, txn_id, created, name, username = row
                who  = f"@{username}" if username else f"ID:{tg_id}"
                text = (
                    f"💰 <b>New Payment Proof!</b>\n\n"
                    f"👤 Customer : {name} ({who})\n"
                    f"🌐 Network  : {network}\n"
                    f"🔑 TXN ID   : <code>{txn_id or 'Not provided'}</code>\n"
                    f"📋 Ref      : <code>{ref}</code>\n"
                    f"📅 Time     : {created}"
                )
                kb = kb_proof_actions(dep_id, tg_id)
                for aid in ADMIN_IDS:
                    try:
                        if ptype == "photo":
                            await bot.send_photo(aid, pcontent, caption=text,
                                                 parse_mode=HTML, reply_markup=kb)
                        else:
                            await bot.send_message(aid, text, parse_mode=HTML, reply_markup=kb)
                    except TelegramError as e:
                        logging.error(f"notify admin failed: {e}")
                db.mark_deposit_notified(dep_id)
        except Exception as e:
            logging.error(f"notify_loop: {e}")
        await asyncio.sleep(NOTIFY_INTERVAL)


async def run():
    app = Application.builder().token(PAYMENTS_BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CallbackQueryHandler(on_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_text))
    print("✅ Admin Payments Bot running...")
    async with app:
        await app.start()
        await app.updater.start_polling(allowed_updates=Update.ALL_TYPES)
        asyncio.create_task(notify_loop(app.bot))
        await asyncio.Event().wait()
        await app.updater.stop()
        await app.stop()

if __name__ == "__main__":
    asyncio.run(run())
