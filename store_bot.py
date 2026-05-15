#!/usr/bin/env python3
"""
TGAccsShop — Store Bot (v2)
Products & wallets are now loaded from DB (managed by Admin Bot).
"""

import asyncio
import sqlite3
import random
import logging
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, filters, ContextTypes,
)
from telegram.error import BadRequest

# ══════════════════════════════════════════════════════
#  CONFIG  — only change these
# ══════════════════════════════════════════════════════

STORE_BOT_TOKEN = "8832979292:AAH_n-kwIS1Vihwuoy42kxEBuSW966AIQOQ"
BOT_NAME        = "N E X   S T O R E"
SUPPORT         = "@nexindo"
DB_FILE         = "tgaccs.db"          # shared with admin bot

# ══════════════════════════════════════════════════════
#  DATABASE  — init + helpers
# ══════════════════════════════════════════════════════

def init_db():
    con = sqlite3.connect(DB_FILE)
    # Users
    con.execute("""CREATE TABLE IF NOT EXISTS users (
        tg_id INTEGER PRIMARY KEY, name TEXT, username TEXT,
        created_at TEXT, balance REAL DEFAULT 0.0)""")
    # Cart
    con.execute("""CREATE TABLE IF NOT EXISTS carts (
        tg_id INTEGER, product_id INTEGER, PRIMARY KEY (tg_id, product_id))""")
    # Orders
    con.execute("""CREATE TABLE IF NOT EXISTS orders (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        tg_id INTEGER, order_ref TEXT, product_id INTEGER,
        product_label TEXT, price REAL, status TEXT DEFAULT 'pending',
        created_at TEXT)""")
    # Deposits
    con.execute("""CREATE TABLE IF NOT EXISTS deposits (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        tg_id INTEGER, ref TEXT, amount REAL,
        network TEXT, status TEXT DEFAULT 'pending', created_at TEXT)""")
    # Products (managed by admin bot)
    con.execute("""CREATE TABLE IF NOT EXISTS products (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        flag TEXT, country TEXT, age TEXT,
        price REAL, stock INTEGER DEFAULT 50,
        active INTEGER DEFAULT 1)""")
    # Wallets (managed by admin bot)
    con.execute("""CREATE TABLE IF NOT EXISTS wallets (
        key TEXT PRIMARY KEY, label TEXT, address TEXT, active INTEGER DEFAULT 1)""")
    # Redeem codes
    con.execute("""CREATE TABLE IF NOT EXISTS redeem_codes (
        code TEXT PRIMARY KEY, amount REAL,
        max_uses INTEGER, used INTEGER DEFAULT 0, created_at TEXT)""")

    # Seed default products if empty
    if con.execute("SELECT COUNT(*) FROM products").fetchone()[0] == 0:
        defaults = [
            ("🇮🇳","India",  "1Y+ Aged",0.30,50),
            ("🇮🇳","India",  "2Y+ Aged",0.32,40),
            ("🇳🇵","Nepal",  "1Y+ Aged",0.30,35),
            ("🇳🇵","Nepal",  "2Y+ Aged",0.32,25),
            ("🇲🇲","Myanmar","1Y+ Aged",0.30,30),
            ("🇲🇲","Myanmar","2Y+ Aged",0.33,20),
            ("🇺🇸","USA",    "1Y+ Aged",0.40,22),
            ("🇺🇸","USA",    "2Y+ Aged",0.45,18),
            ("🇺🇸","USA",    "3Y+ Aged",0.48,12),
            ("🇷🇺","Russia", "1Y+ Aged",0.42,19),
            ("🇷🇺","Russia", "2Y+ Aged",0.47,15),
            ("🇷🇺","Russia", "3Y+ Aged",0.50,11),
        ]
        con.executemany(
            "INSERT INTO products (flag,country,age,price,stock,active) VALUES (?,?,?,?,?,1)",
            defaults)

    # Seed default wallets if empty
    if con.execute("SELECT COUNT(*) FROM wallets").fetchone()[0] == 0:
        defaults = [
            ("usdt_bep20","💵 USDT BEP-20 (BSC)",   "0xcF0ABcDF3afccBE577d4D930e01af5c7F50f5aB7"),
            ("usdt_eth",  "🔷 USDT ERC-20 (ETH)",   "0xcF0ABcDF3afccBE577d4D930e01af5c7F50f5aB7"),
            ("btc",       "₿ Bitcoin (BTC)",         "bc1q0gtel9l8sczkrlv3ywdqkk9adln8f84zw0wczr"),
            ("ltc",       "🥈 Litecoin (LTC)",       "ltc1qj3f4rdevg738hrnf0xpdvlkc9k98u3ahkfykrj"),
            ("ton",       "💎 TON",                  "UQCAoTZkL0N_gxjDnV1-PC1rgqdPgfGDhtJs-YU2yHbkeZy-"),
            ("usdt_sol",  "🟣 USDT SPL (Solana)",    "CLiBT9JuTJCjpBkf4HXZMCimkzxJKX8PJxJtxHTd6iFe"),
            ("bnb",       "🟡 BNB (BSC)",            "0xcF0ABcDF3afccBE577d4D930e01af5c7F50f5aB7"),
        ]
        con.executemany("INSERT INTO wallets (key,label,address,active) VALUES (?,?,?,1)", defaults)

    con.commit(); con.close()

def _db():
    return sqlite3.connect(DB_FILE)

# ── Product helpers ────────────────────────────────────
def get_active_products():
    con = _db()
    rows = con.execute(
        "SELECT id,flag,country,age,price,stock FROM products WHERE active=1 ORDER BY id"
    ).fetchall()
    con.close()
    return [{"id":r[0],"flag":r[1],"country":r[2],"age":r[3],"price":r[4],"stock":r[5]} for r in rows]

def get_product(pid):
    con = _db()
    r = con.execute("SELECT id,flag,country,age,price,stock,active FROM products WHERE id=?", (pid,)).fetchone()
    con.close()
    if not r: return None
    return {"id":r[0],"flag":r[1],"country":r[2],"age":r[3],"price":r[4],"stock":r[5],"active":r[6]}

# ── Wallet helpers ─────────────────────────────────────
def get_active_wallets():
    con = _db()
    rows = con.execute("SELECT key,label,address FROM wallets WHERE active=1").fetchall()
    con.close()
    return {r[0]: (r[1], r[2]) for r in rows}

# ── User helpers ───────────────────────────────────────
def ensure_user(tg_id, name, username=""):
    con = _db()
    con.execute(
        "INSERT OR IGNORE INTO users (tg_id,name,username,created_at,balance) VALUES (?,?,?,?,0.0)",
        (tg_id, name, username, datetime.now().isoformat()))
    con.commit(); con.close()

def get_balance(tg_id):
    con = _db()
    r = con.execute("SELECT balance FROM users WHERE tg_id=?", (tg_id,)).fetchone()
    con.close(); return r[0] if r else 0.0

def deduct_balance(tg_id, amount):
    con = _db()
    con.execute("UPDATE users SET balance=balance-? WHERE tg_id=?", (amount, tg_id))
    con.commit(); con.close()

def get_user_info(tg_id):
    con = _db()
    r = con.execute("SELECT name,username,created_at,balance FROM users WHERE tg_id=?", (tg_id,)).fetchone()
    con.close(); return r

# ── Cart helpers ───────────────────────────────────────
def get_cart(tg_id):
    con = _db()
    ids = {r[0] for r in con.execute("SELECT product_id FROM carts WHERE tg_id=?", (tg_id,)).fetchall()}
    con.close()
    prods = get_active_products()
    return [p for p in prods if p["id"] in ids]

def add_to_cart(tg_id, pid):
    con = _db(); con.execute("INSERT OR IGNORE INTO carts VALUES (?,?)", (tg_id, pid))
    con.commit(); con.close()

def remove_from_cart(tg_id, pid):
    con = _db(); con.execute("DELETE FROM carts WHERE tg_id=? AND product_id=?", (tg_id, pid))
    con.commit(); con.close()

def clear_cart(tg_id):
    con = _db(); con.execute("DELETE FROM carts WHERE tg_id=?", (tg_id,))
    con.commit(); con.close()

# ── Order helpers ──────────────────────────────────────
def save_orders(tg_id, cart_items, order_ref):
    con = _db(); now = datetime.now().strftime("%d/%m/%Y %H:%M")
    for p in cart_items:
        label = f"{p['flag']} {p['country']} ({p['age']})"
        con.execute(
            "INSERT INTO orders (tg_id,order_ref,product_id,product_label,price,status,created_at) "
            "VALUES (?,?,?,?,?,'pending',?)",
            (tg_id, order_ref, p["id"], label, p["price"], now))
    con.commit(); con.close()

def get_orders(tg_id):
    con = _db()
    rows = con.execute(
        "SELECT order_ref,product_label,price,status,created_at FROM orders WHERE tg_id=? ORDER BY id DESC",
        (tg_id,)).fetchall()
    con.close(); return rows

# ── Deposit helpers ────────────────────────────────────
def save_deposit(tg_id, ref, network_label):
    con = _db(); now = datetime.now().strftime("%d/%m/%Y %H:%M")
    con.execute("INSERT INTO deposits (tg_id,ref,amount,network,status,created_at) VALUES (?,?,0,?,'pending',?)",
                (tg_id, ref, network_label, now))
    con.commit(); con.close()

# ── Redeem helpers ─────────────────────────────────────
def try_redeem(tg_id, code):
    con = _db()
    r = con.execute("SELECT amount,max_uses,used FROM redeem_codes WHERE code=?", (code.upper(),)).fetchone()
    if not r: con.close(); return None, "❌ Invalid code."
    amount, max_uses, used = r
    if used >= max_uses: con.close(); return None, "❌ Code already used up."
    con.execute("UPDATE redeem_codes SET used=used+1 WHERE code=?", (code.upper(),))
    con.execute("UPDATE users SET balance=balance+? WHERE tg_id=?", (amount, tg_id))
    con.commit(); con.close()
    return amount, "ok"

# ══════════════════════════════════════════════════════
#  KEYBOARDS
# ══════════════════════════════════════════════════════

def kb_main():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🛍 Products",         callback_data="products"),
         InlineKeyboardButton("🎁 Redeem Code",      callback_data="redeem")],
        [InlineKeyboardButton("👤 My Profile",       callback_data="profile"),
         InlineKeyboardButton("📋 Purchase History", callback_data="history")],
        [InlineKeyboardButton("👛 Wallet",           callback_data="wallet")],
        [InlineKeyboardButton("🆘 Support",          callback_data="support"),
         InlineKeyboardButton("ℹ️ About",            callback_data="about")],
    ])

def kb_back_main():
    return InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Main Menu", callback_data="main_menu")]])

def kb_products(products):
    rows = []
    for p in products:
        stock_str = str(p["stock"]) if p["stock"] > 0 else "0"
        rows.append([InlineKeyboardButton(
            f"{p['flag']} ${p['price']:.2f} | {p['country']} — {p['age']} | 📦 {stock_str}",
            callback_data=f"acc_{p['id']}")])
    rows.append([InlineKeyboardButton("🔄 Refresh",    callback_data="products"),
                 InlineKeyboardButton("🏠 Main Menu",  callback_data="main_menu")])
    return InlineKeyboardMarkup(rows)

def kb_acc_detail(pid, in_cart):
    label = "✅ In Cart" if in_cart else "🛒 Add to Cart"
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(label,           callback_data=f"addcart_{pid}"),
         InlineKeyboardButton("⚡ Buy Now",    callback_data=f"buynow_{pid}")],
        [InlineKeyboardButton("⬅️ Back",       callback_data="products"),
         InlineKeyboardButton("🏠 Menu",       callback_data="main_menu")],
    ])

def kb_cart(cart_items):
    rows = [[InlineKeyboardButton(
        f"❌ {p['flag']} {p['country']} {p['age']}  (${p['price']:.2f})",
        callback_data=f"rmcart_{p['id']}")] for p in cart_items]
    rows.append([InlineKeyboardButton("✅ Checkout",      callback_data="checkout")])
    rows.append([InlineKeyboardButton("🛍 Browse More",  callback_data="products"),
                 InlineKeyboardButton("🏠 Menu",          callback_data="main_menu")])
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

def kb_deposit_networks(wallets):
    rows = [[InlineKeyboardButton(label, callback_data=f"deposit_{key}")]
            for key, (label, _) in wallets.items()]
    rows.append([InlineKeyboardButton("❌ Cancel", callback_data="wallet")])
    return InlineKeyboardMarkup(rows)

def kb_deposit_sent(network_key):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ I've Sent the Payment", callback_data=f"dep_confirm_{network_key}")],
        [InlineKeyboardButton("⬅️ Change Network",        callback_data="deposit_menu")],
    ])

def kb_post_order():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📋 Purchase History", callback_data="history")],
        [InlineKeyboardButton("🛍 Continue Shopping", callback_data="products")],
    ])

# ══════════════════════════════════════════════════════
#  TEXT HELPERS
# ══════════════════════════════════════════════════════

HTML = "HTML"

def txt_welcome(name):
    return (
        f"🚀 <b>System Dashboard Activated</b>\n\n"
        f"👋 Welcome back, <b>{name}</b>!\n\n"
        f"🎯 <b>Quick guide:</b>\n"
        f"1. Tap 'Products'.\n"
        f"2. Choose the account you want.\n"
        f"3. Complete the payment.\n"
        f"4. Your account will be delivered instantly.\n\n"
        f"🛍 Please choose a menu:"
    )

def txt_wallet(bal):
    return (
        f"👛 <b>Your Wallet Balance: ${bal:.2f}</b>\n\n"
        f"Use your balance to buy products instantly.\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"Minimum deposit: <b>$1.00 USDT</b>\n"
        f"<i>Funds credited after admin approval.</i>"
    )

def txt_acc(p):
    return (
        f"📱 <b>{p['flag']} {p['country']} Telegram Account</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🌍 Country  : {p['flag']} <b>{p['country']}</b>\n"
        f"⏳ Age      : <code>{p['age']}</code>\n"
        f"💰 Price    : <b>${p['price']:.2f} USDT</b>\n"
        f"📦 Stock    : <code>{p['stock']} available</code>\n"
        f"✅ Status   : IN STOCK\n"
        f"🔒 Verified : Yes"
    )

def txt_cart(cart_items):
    lines = "\n".join(
        f"• {p['flag']} {p['country']} ({p['age']}) — <b>${p['price']:.2f}</b>"
        for p in cart_items)
    total = sum(p["price"] for p in cart_items)
    return (
        f"🛒 <b>Your Cart</b>\n\n{lines}\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"💰 Total: <b>${total:.2f} USDT</b>")

def txt_profile(row, tg_id, order_count):
    name, username, created_at, balance = row
    return (
        f"👤 <b>My Profile</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🆔 ID       : <code>{tg_id}</code>\n"
        f"👤 Name     : <b>{name}</b>\n"
        f"📛 Username : {'@'+username if username else '—'}\n"
        f"📅 Joined   : {created_at[:10] if created_at else '—'}\n"
        f"💰 Balance  : <b>${balance:.2f} USDT</b>\n"
        f"📦 Orders   : <b>{order_count}</b>")

def txt_history(orders):
    if not orders:
        return ("📋 <b>Purchase History</b>\n\n"
                "No orders yet.\n\n<i>Browse and make your first purchase!</i>")
    lines = []
    for ref, label, price, status, created in orders[:20]:
        icon = "✅" if status == "delivered" else "⏳"
        lines.append(f"{icon} <code>{ref}</code>\n   📱 {label}\n   💰 ${price:.2f} | {created[:10]}")
    return "📋 <b>Purchase History</b>\n\n" + "\n\n".join(lines)

# ══════════════════════════════════════════════════════
#  LOGGING
# ══════════════════════════════════════════════════════

logging.basicConfig(format="%(asctime)s — %(levelname)s — %(message)s", level=logging.INFO)
logging.getLogger("httpx").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)

async def safe_answer(q, text="", alert=False):
    try: await q.answer(text, show_alert=alert)
    except BadRequest: pass

# ══════════════════════════════════════════════════════
#  HANDLERS
# ══════════════════════════════════════════════════════

async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    ensure_user(user.id, user.first_name, user.username or "")
    await update.message.reply_text(txt_welcome(user.first_name), parse_mode=HTML, reply_markup=kb_main())

async def cmd_menu(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ensure_user(update.effective_user.id, update.effective_user.first_name)
    await update.message.reply_text("🏠 <b>Main Menu</b>", parse_mode=HTML, reply_markup=kb_main())

async def on_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q    = update.callback_query
    data = q.data
    user = update.effective_user
    ensure_user(user.id, user.first_name, user.username or "")
    await safe_answer(q)

    if data == "main_menu":
        await q.edit_message_text("🏠 <b>Main Menu</b>", parse_mode=HTML, reply_markup=kb_main())

    elif data == "products":
        prods = get_active_products()
        if not prods:
            await q.edit_message_text("😔 No products available right now. Check back soon!",
                                      reply_markup=kb_back_main()); return
        await q.edit_message_text("🛍 <b>PRODUCTS</b>\n\n💡 Choose a product:",
                                  parse_mode=HTML, reply_markup=kb_products(prods))

    elif data.startswith("acc_"):
        pid = int(data[4:])
        p   = get_product(pid)
        if not p:
            await safe_answer(q, "Product not found.", alert=True); return
        in_cart = any(c["id"] == pid for c in get_cart(user.id))
        await q.edit_message_text(txt_acc(p), parse_mode=HTML, reply_markup=kb_acc_detail(pid, in_cart))

    elif data.startswith("addcart_"):
        pid = int(data[8:])
        if any(c["id"] == pid for c in get_cart(user.id)):
            await safe_answer(q, "Already in your cart! 🛒", alert=True)
        else:
            add_to_cart(user.id, pid)
            await safe_answer(q, "✅ Added to cart!", alert=True)
            try:
                await q.edit_message_reply_markup(reply_markup=kb_acc_detail(pid, True))
            except BadRequest: pass

    elif data.startswith("buynow_"):
        pid = int(data[7:])
        if not any(c["id"] == pid for c in get_cart(user.id)):
            add_to_cart(user.id, pid)
        await _do_checkout(q, user.id)

    elif data == "cart":
        cart = get_cart(user.id)
        if not cart:
            await q.edit_message_text("🛒 <b>Your cart is empty.</b>", parse_mode=HTML, reply_markup=kb_empty_cart())
        else:
            await q.edit_message_text(txt_cart(cart), parse_mode=HTML, reply_markup=kb_cart(cart))

    elif data.startswith("rmcart_"):
        pid = int(data[7:])
        remove_from_cart(user.id, pid)
        cart = get_cart(user.id)
        if not cart:
            await q.edit_message_text("🛒 <b>Your cart is empty.</b>", parse_mode=HTML, reply_markup=kb_empty_cart())
        else:
            await q.edit_message_text(txt_cart(cart), parse_mode=HTML, reply_markup=kb_cart(cart))

    elif data == "checkout":
        await _do_checkout(q, user.id)

    elif data == "wallet":
        bal = get_balance(user.id)
        await q.edit_message_text(txt_wallet(bal), parse_mode=HTML, reply_markup=kb_wallet())

    elif data == "deposit_menu":
        wallets = get_active_wallets()
        await q.edit_message_text(
            "💳 <b>Deposit Funds</b>\n\nMinimum: <b>$1.00 USDT</b>\n\nSelect a network:",
            parse_mode=HTML, reply_markup=kb_deposit_networks(wallets))

    elif data.startswith("deposit_"):
        network_key = data[8:]
        wallets = get_active_wallets()
        if network_key not in wallets:
            await safe_answer(q, "Network not available.", alert=True); return
        label, addr = wallets[network_key]
        await q.edit_message_text(
            f"💳 <b>Deposit Details</b>\n\n"
            f"🌐 Network : <b>{label}</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"📬 <b>Send to:</b>\n<code>{addr}</code>\n\n"
            f"⚠️ <i>Minimum: $1.00 USDT. After sending tap below.</i>",
            parse_mode=HTML, reply_markup=kb_deposit_sent(network_key))

    elif data.startswith("dep_confirm_"):
        network_key = data[12:]
        wallets = get_active_wallets()
        label   = wallets.get(network_key, ("Unknown",))[0] if network_key in wallets else "Unknown"
        dep_ref = f"#DEP{random.randint(10000,99999)}"
        save_deposit(user.id, dep_ref, label)
        await q.edit_message_text(
            f"✅ <b>Deposit Request Submitted!</b>\n\n"
            f"⚡ Your proof is being verified.\n"
            f"📋 Status: <code>Pending</code>\n"
            f"⏳ Time: 3 Hours (Max)\n\n"
            f"You will be notified once funds are added.",
            parse_mode=HTML,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("👛 My Wallet", callback_data="wallet")],
                [InlineKeyboardButton("🏠 Main Menu", callback_data="main_menu")],
            ]))

    elif data == "profile":
        row    = get_user_info(user.id)
        orders = get_orders(user.id)
        if row:
            await q.edit_message_text(
                txt_profile(row, user.id, len(orders)), parse_mode=HTML,
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("💳 Deposit", callback_data="deposit_menu")],
                    [InlineKeyboardButton("🏠 Main Menu", callback_data="main_menu")],
                ]))

    elif data == "history":
        orders = get_orders(user.id)
        await q.edit_message_text(txt_history(orders), parse_mode=HTML, reply_markup=kb_back_main())

    elif data == "redeem":
        ctx.user_data["awaiting_redeem"] = True
        await q.edit_message_text(
            "🎁 <b>Redeem Code</b>\n\nSend your code as a message:",
            parse_mode=HTML,
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel", callback_data="main_menu")]]))

    elif data == "support":
        await q.edit_message_text(
            f"🆘 <b>Support</b>\n\nContact: {SUPPORT}",
            parse_mode=HTML, reply_markup=kb_back_main())

    elif data == "about":
        await q.edit_message_text(
            f"ℹ️ <b>About {BOT_NAME}</b>\n\n"
            "📱 Premium Telegram accounts\n"
            f"💰 $0.30–$0.50 USDT\n⚡ Fast delivery\n📞 {SUPPORT}",
            parse_mode=HTML, reply_markup=kb_back_main())


async def _do_checkout(q, user_id):
    cart = get_cart(user_id)
    if not cart:
        await q.edit_message_text("🛒 <b>Your cart is empty!</b>", parse_mode=HTML, reply_markup=kb_empty_cart()); return
    total   = sum(p["price"] for p in cart)
    balance = get_balance(user_id)
    if balance < total:
        needed = total - balance
        await q.edit_message_text(
            f"❌ <b>Insufficient Balance</b>\n\n"
            f"🛒 Cart Total   : <b>${total:.2f} USDT</b>\n"
            f"👛 Your Balance : <b>${balance:.2f} USDT</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"⚠️ You need <b>${needed:.2f} more.</b>",
            parse_mode=HTML,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("💳 Deposit Funds", callback_data="deposit_menu")],
                [InlineKeyboardButton("🏠 Main Menu",     callback_data="main_menu")],
            ])); return
    deduct_balance(user_id, total)
    order_ref = f"#TG{random.randint(10000,99999)}"
    save_orders(user_id, cart, order_ref)
    clear_cart(user_id)
    await q.edit_message_text(
        f"🎉 <b>Order Placed!</b>\n\n"
        f"💰 <b>${total:.2f} USDT</b> deducted.\n"
        f"📋 Ref: <code>{order_ref}</code>\n"
        f"👛 Balance: <b>${get_balance(user_id):.2f} USDT</b>\n\n"
        f"⏳ <i>Delivery in 10–30 minutes.</i>",
        parse_mode=HTML, reply_markup=kb_post_order())


async def on_message(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    text = (update.message.text or "").strip()
    if ctx.user_data.get("awaiting_redeem"):
        ctx.user_data.pop("awaiting_redeem")
        ensure_user(user.id, user.first_name, user.username or "")
        amount, msg = try_redeem(user.id, text)
        if amount:
            await update.message.reply_text(
                f"🎉 <b>Redeemed!</b>\n💰 <b>${amount:.2f} USDT</b> added!\nBalance: <b>${get_balance(user.id):.2f}</b>",
                parse_mode=HTML, reply_markup=kb_back_main())
        else:
            await update.message.reply_text(msg, reply_markup=kb_back_main())

# ══════════════════════════════════════════════════════
#  MAIN
# ══════════════════════════════════════════════════════

async def run():
    init_db()
    app = Application.builder().token(STORE_BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("menu",  cmd_menu))
    app.add_handler(CallbackQueryHandler(on_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_message))
    print(f"✅ {BOT_NAME} Store Bot running...")
    async with app:
        await app.start()
        await app.updater.start_polling(allowed_updates=Update.ALL_TYPES)
        await asyncio.Event().wait()
        await app.updater.stop()
        await app.stop()

if __name__ == "__main__":
    asyncio.run(run())
