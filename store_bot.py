#!/usr/bin/env python3
"""store_bot.py — Multi-language store with quantity selection and TXN-only deposit."""

import asyncio, logging, os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
from telegram.error import BadRequest
import shared_db as db

STORE_BOT_TOKEN = os.environ["STORE_TOKEN"]
BOT_NAME        = os.environ.get("BOT_NAME", "Xing Store")
SUPPORT         = "@xingmart"
HTML            = "HTML"

logging.basicConfig(format="%(asctime)s — %(levelname)s — %(message)s", level=logging.INFO)
logging.getLogger("httpx").setLevel(logging.WARNING)

LANGS = {"en":"🇬🇧 English","zh":"🇨🇳 中文","ru":"🇷🇺 Русский","vi":"🇻🇳 Tiếng Việt"}

# ── Translations ────────────────────────────────────────────────────────────────
T = {
"en":{
  "welcome":     lambda n,b: f"🚀 <b>Welcome to {b}, {n}!</b>\n\n1. Browse Products\n2. Pick quantity & confirm\n3. Pay from wallet balance\n4. Get delivered instantly!\n\nChoose below:",
  "products":    "🛍 PRODUCTS","choose":"💡 Choose a product:","no_products":"😔 No products available.",
  "in_stock":"✅ IN STOCK","out_of_stock":"😔 Out of stock.","price":"💰 Price","stock":"📦 Stock","left":"left",
  "qty_ask":     lambda n,p,s: f"🛒 <b>{n}</b>\n\n💰 Unit Price : <b>${p:.2f} USDT</b>\n📦 In Stock   : <b>{s}</b>\n\nHow many do you want?",
  "qty_custom":  "✏️ Enter number",
  "qty_enter":   lambda n,s: f"✏️ How many <b>{n}</b> do you want?\nMax available: <b>{s}</b>\n\nSend a number:",
  "qty_invalid": lambda s: f"⚠️ Please send a number between 1 and {s}.",
  "qty_exceed":  lambda s: f"⚠️ Only <b>{s}</b> in stock!",
  "confirm_order": lambda n,q,u,t,b: f"🛒 <b>Confirm Order</b>\n\n📦 Product  : <b>{n}</b>\n🔢 Quantity : <b>{q}</b>\n💰 Unit     : <b>${u:.2f} USDT</b>\n━━━━━━━━━━━━━━━━━━\n💵 Total    : <b>${t:.2f} USDT</b>\n👛 Balance  : <b>${b:.2f} USDT</b>",
  "confirm_btn":"✅ Confirm & Pay","cancel_btn":"❌ Cancel",
  "wallet_title":"👛 Your Wallet","wallet_balance":"💰 Balance",
  "wallet_note":"Deposit funds to start buying.\n<i>Min deposit: $1.00 USDT</i>",
  "deposit_btn":"💳 Deposit Funds","deposit_title":"💳 Deposit Funds",
  "deposit_min":"Minimum: <b>$1.00 USDT</b>\n\nSelect a payment network:",
  "deposit_via": lambda l: f"💳 Deposit via {l}",
  "send_to":"📬 Send to this address:","after_send":"⚠️ <i>After sending, tap the button below.</i>",
  "sent_btn":"✅ I Have Sent — Submit TXN ID","change_net":"⬅️ Change Network",
  "txn_ask":"🔑 <b>Enter Your Transaction ID</b>\n\nSend your <b>TXN ID / Transaction Hash</b> as a text message.\n\n<i>Required to verify your payment.</i>",
  "txn_ok":"✅ <b>Deposit Request Submitted!</b>",
  "txn_pending":"⚡ TXN ID is being verified.\n📋 Status : <b>Pending</b>\n⏳ Time   : up to 3 hours",
  "reference":"📌 Reference",
  "profile_title":"👤 My Profile","id":"🆔 ID","name_lbl":"👤 Name","username_lbl":"📛 Username",
  "joined":"📅 Joined","balance":"💰 Balance","orders_count":"📦 Orders",
  "orders_title":"📋 My Orders","no_orders":"No orders yet.",
  "order_placed":"✅ Order Placed!","product_lbl":"📦 Product","qty_lbl":"🔢 Quantity",
  "paid_lbl":"💰 Paid","ref_lbl":"📋 Ref","balance_lbl":"👛 Balance",
  "deliver_note": lambda s: f"⏳ <b>Your product will be delivered within 5–10 minutes.</b>\nNot received? Contact {s}",
  "my_orders_btn":"📋 My Orders","continue_btn":"🛍 Continue Shopping",
  "insuf_bal":"❌ Insufficient Balance","price_lbl":"💰 Price","bal_lbl":"👛 Balance",
  "need_more": lambda n: f"⚠️ You need <b>${n:.2f} more.</b>",
  "redeem_title":"🎁 Redeem Code","redeem_send":"Send your code:",
  "redeemed":"🎉 Redeemed!","redeem_added": lambda a,b: f"💰 <b>${a:.2f} USDT</b> added!\nBalance: <b>${b:.2f} USDT</b>",
  "support_title":"🆘 Support","support_body": lambda s: f"Contact us: {s}",
  "net_unavail":"Network unavailable.","not_found":"Not found.",
  "main_menu":"🏠 Main Menu","back_btn":"⬅️ Back","refresh_btn":"🔄 Refresh","menu_btn":"🏠 Menu",
  "lang_btn":"🌐 Language","products_btn":"🛍 Products","redeem_btn":"🎁 Redeem Code",
  "profile_btn":"👤 My Profile","history_btn":"📋 My Orders","wallet_btn":"👛 Wallet","support_btn":"🆘 Support",
},
"zh":{
  "welcome":     lambda n,b: f"🚀 <b>欢迎来到 {b}，{n}！</b>\n\n1. 浏览产品\n2. 选择数量并确认\n3. 用钱包余额付款\n4. 立即收到产品！\n\n请选择：",
  "products":"🛍 产品","choose":"💡 选择产品：","no_products":"😔 暂无可用产品。",
  "in_stock":"✅ 有货","out_of_stock":"😔 已售罄。","price":"💰 价格","stock":"📦 库存","left":"个",
  "qty_ask":     lambda n,p,s: f"🛒 <b>{n}</b>\n\n💰 单价：<b>${p:.2f} USDT</b>\n📦 库存：<b>{s}</b>\n\n您需要多少个？",
  "qty_custom":"✏️ 输入数量",
  "qty_enter":   lambda n,s: f"✏️ 您需要多少个 <b>{n}</b>？\n最多：<b>{s}</b>\n\n请发送数字：",
  "qty_invalid": lambda s: f"⚠️ 请输入 1 到 {s} 之间的数字。",
  "qty_exceed":  lambda s: f"⚠️ 库存只有 <b>{s}</b> 个！",
  "confirm_order": lambda n,q,u,t,b: f"🛒 <b>确认订单</b>\n\n📦 产品：<b>{n}</b>\n🔢 数量：<b>{q}</b>\n💰 单价：<b>${u:.2f} USDT</b>\n━━━━━━━━━━━━━━━━━━\n💵 总计：<b>${t:.2f} USDT</b>\n👛 余额：<b>${b:.2f} USDT</b>",
  "confirm_btn":"✅ 确认付款","cancel_btn":"❌ 取消",
  "wallet_title":"👛 我的钱包","wallet_balance":"💰 余额",
  "wallet_note":"充值后即可购买。\n<i>最低充值：$1.00 USDT</i>",
  "deposit_btn":"💳 充值","deposit_title":"💳 充值",
  "deposit_min":"最低：<b>$1.00 USDT</b>\n\n请选择支付网络：",
  "deposit_via": lambda l: f"💳 通过 {l} 充值",
  "send_to":"📬 发送到此地址：","after_send":"⚠️ <i>发送后，请点击下方按钮。</i>",
  "sent_btn":"✅ 已付款 — 提交交易ID","change_net":"⬅️ 更换网络",
  "txn_ask":"🔑 <b>输入交易ID</b>\n\n请发送您的 <b>TXN ID / 交易哈希</b>。\n\n<i>验证付款所必需。</i>",
  "txn_ok":"✅ <b>充值申请已提交！</b>",
  "txn_pending":"⚡ 正在验证交易ID。\n📋 状态：<b>待处理</b>\n⏳ 时间：最长 3 小时",
  "reference":"📌 参考号",
  "profile_title":"👤 我的资料","id":"🆔 ID","name_lbl":"👤 姓名","username_lbl":"📛 用户名",
  "joined":"📅 注册时间","balance":"💰 余额","orders_count":"📦 订单数",
  "orders_title":"📋 我的订单","no_orders":"暂无订单。",
  "order_placed":"✅ 下单成功！","product_lbl":"📦 产品","qty_lbl":"🔢 数量",
  "paid_lbl":"💰 已付","ref_lbl":"📋 参考号","balance_lbl":"👛 余额",
  "deliver_note": lambda s: f"⏳ <b>产品将在 5–10 分钟内送达。</b>\n未收到？请联系 {s}",
  "my_orders_btn":"📋 我的订单","continue_btn":"🛍 继续购物",
  "insuf_bal":"❌ 余额不足","price_lbl":"💰 价格","bal_lbl":"👛 余额",
  "need_more": lambda n: f"⚠️ 您还需要 <b>${n:.2f}</b>。",
  "redeem_title":"🎁 兑换码","redeem_send":"请发送您的兑换码：",
  "redeemed":"🎉 兑换成功！","redeem_added": lambda a,b: f"💰 已添加 <b>${a:.2f} USDT</b>！\n余额：<b>${b:.2f} USDT</b>",
  "support_title":"🆘 客服支持","support_body": lambda s: f"联系我们：{s}",
  "net_unavail":"该网络不可用。","not_found":"未找到。",
  "main_menu":"🏠 主菜单","back_btn":"⬅️ 返回","refresh_btn":"🔄 刷新","menu_btn":"🏠 菜单",
  "lang_btn":"🌐 语言","products_btn":"🛍 产品","redeem_btn":"🎁 兑换码",
  "profile_btn":"👤 我的资料","history_btn":"📋 我的订单","wallet_btn":"👛 钱包","support_btn":"🆘 客服",
},
"ru":{
  "welcome":     lambda n,b: f"🚀 <b>Добро пожаловать в {b}, {n}!</b>\n\n1. Каталог товаров\n2. Выберите количество и подтвердите\n3. Оплатите с баланса\n4. Получите мгновенно!\n\nВыберите действие:",
  "products":"🛍 ТОВАРЫ","choose":"💡 Выберите товар:","no_products":"😔 Товаров пока нет.",
  "in_stock":"✅ В НАЛИЧИИ","out_of_stock":"😔 Нет в наличии.","price":"💰 Цена","stock":"📦 Остаток","left":"шт.",
  "qty_ask":     lambda n,p,s: f"🛒 <b>{n}</b>\n\n💰 Цена за шт. : <b>${p:.2f} USDT</b>\n📦 В наличии   : <b>{s}</b>\n\nСколько вам нужно?",
  "qty_custom":"✏️ Ввести число",
  "qty_enter":   lambda n,s: f"✏️ Сколько <b>{n}</b> вам нужно?\nМаксимум: <b>{s}</b>\n\nОтправьте число:",
  "qty_invalid": lambda s: f"⚠️ Введите число от 1 до {s}.",
  "qty_exceed":  lambda s: f"⚠️ В наличии только <b>{s}</b> шт.!",
  "confirm_order": lambda n,q,u,t,b: f"🛒 <b>Подтверждение заказа</b>\n\n📦 Товар   : <b>{n}</b>\n🔢 Кол-во  : <b>{q}</b>\n💰 За шт.  : <b>${u:.2f} USDT</b>\n━━━━━━━━━━━━━━━━━━\n💵 Итого   : <b>${t:.2f} USDT</b>\n👛 Баланс  : <b>${b:.2f} USDT</b>",
  "confirm_btn":"✅ Подтвердить и оплатить","cancel_btn":"❌ Отмена",
  "wallet_title":"👛 Ваш кошелёк","wallet_balance":"💰 Баланс",
  "wallet_note":"Пополните баланс для покупок.\n<i>Мин. пополнение: $1.00 USDT</i>",
  "deposit_btn":"💳 Пополнить","deposit_title":"💳 Пополнение",
  "deposit_min":"Минимум: <b>$1.00 USDT</b>\n\nВыберите сеть:",
  "deposit_via": lambda l: f"💳 Пополнение через {l}",
  "send_to":"📬 Отправьте на этот адрес:","after_send":"⚠️ <i>После отправки нажмите кнопку ниже.</i>",
  "sent_btn":"✅ Отправил — Ввести TXN ID","change_net":"⬅️ Другая сеть",
  "txn_ask":"🔑 <b>Введите TXN ID</b>\n\nОтправьте ваш <b>TXN ID / хэш транзакции</b> текстом.\n\n<i>Необходимо для проверки платежа.</i>",
  "txn_ok":"✅ <b>Заявка на пополнение отправлена!</b>",
  "txn_pending":"⚡ TXN ID проверяется.\n📋 Статус: <b>Ожидание</b>\n⏳ Время: до 3 часов",
  "reference":"📌 Референс",
  "profile_title":"👤 Мой профиль","id":"🆔 ID","name_lbl":"👤 Имя","username_lbl":"📛 Username",
  "joined":"📅 Дата регистрации","balance":"💰 Баланс","orders_count":"📦 Заказов",
  "orders_title":"📋 Мои заказы","no_orders":"Заказов ещё нет.",
  "order_placed":"✅ Заказ оформлен!","product_lbl":"📦 Товар","qty_lbl":"🔢 Кол-во",
  "paid_lbl":"💰 Оплачено","ref_lbl":"📋 Референс","balance_lbl":"👛 Баланс",
  "deliver_note": lambda s: f"⏳ <b>Товар будет доставлен в течение 5–10 минут.</b>\nНе получили? Напишите {s}",
  "my_orders_btn":"📋 Мои заказы","continue_btn":"🛍 Продолжить",
  "insuf_bal":"❌ Недостаточно средств","price_lbl":"💰 Цена","bal_lbl":"👛 Баланс",
  "need_more": lambda n: f"⚠️ Не хватает <b>${n:.2f}</b>.",
  "redeem_title":"🎁 Промокод","redeem_send":"Введите ваш код:",
  "redeemed":"🎉 Активировано!","redeem_added": lambda a,b: f"💰 Начислено <b>${a:.2f} USDT</b>!\nБаланс: <b>${b:.2f} USDT</b>",
  "support_title":"🆘 Поддержка","support_body": lambda s: f"Напишите нам: {s}",
  "net_unavail":"Сеть недоступна.","not_found":"Не найдено.",
  "main_menu":"🏠 Главное меню","back_btn":"⬅️ Назад","refresh_btn":"🔄 Обновить","menu_btn":"🏠 Меню",
  "lang_btn":"🌐 Язык","products_btn":"🛍 Товары","redeem_btn":"🎁 Промокод",
  "profile_btn":"👤 Профиль","history_btn":"📋 Мои заказы","wallet_btn":"👛 Кошелёк","support_btn":"🆘 Поддержка",
},
"vi":{
  "welcome":     lambda n,b: f"🚀 <b>Chào mừng đến {b}, {n}!</b>\n\n1. Duyệt sản phẩm\n2. Chọn số lượng & xác nhận\n3. Thanh toán từ ví\n4. Nhận ngay lập tức!\n\nChọn bên dưới:",
  "products":"🛍 SẢN PHẨM","choose":"💡 Chọn sản phẩm:","no_products":"😔 Không có sản phẩm.",
  "in_stock":"✅ CÒN HÀNG","out_of_stock":"😔 Hết hàng.","price":"💰 Giá","stock":"📦 Kho","left":"còn",
  "qty_ask":     lambda n,p,s: f"🛒 <b>{n}</b>\n\n💰 Đơn giá  : <b>${p:.2f} USDT</b>\n📦 Còn lại  : <b>{s}</b>\n\nBạn muốn mua bao nhiêu?",
  "qty_custom":"✏️ Nhập số",
  "qty_enter":   lambda n,s: f"✏️ Bạn muốn mua bao nhiêu <b>{n}</b>?\nTối đa: <b>{s}</b>\n\nGửi một số:",
  "qty_invalid": lambda s: f"⚠️ Vui lòng gửi số từ 1 đến {s}.",
  "qty_exceed":  lambda s: f"⚠️ Chỉ còn <b>{s}</b> sản phẩm!",
  "confirm_order": lambda n,q,u,t,b: f"🛒 <b>Xác nhận đơn hàng</b>\n\n📦 Sản phẩm : <b>{n}</b>\n🔢 Số lượng : <b>{q}</b>\n💰 Đơn giá  : <b>${u:.2f} USDT</b>\n━━━━━━━━━━━━━━━━━━\n💵 Tổng     : <b>${t:.2f} USDT</b>\n👛 Số dư    : <b>${b:.2f} USDT</b>",
  "confirm_btn":"✅ Xác nhận & Thanh toán","cancel_btn":"❌ Hủy",
  "wallet_title":"👛 Ví của bạn","wallet_balance":"💰 Số dư",
  "wallet_note":"Nạp tiền để bắt đầu mua.\n<i>Nạp tối thiểu: $1.00 USDT</i>",
  "deposit_btn":"💳 Nạp tiền","deposit_title":"💳 Nạp tiền",
  "deposit_min":"Tối thiểu: <b>$1.00 USDT</b>\n\nChọn mạng thanh toán:",
  "deposit_via": lambda l: f"💳 Nạp qua {l}",
  "send_to":"📬 Gửi đến địa chỉ này:","after_send":"⚠️ <i>Sau khi gửi, nhấn nút bên dưới.</i>",
  "sent_btn":"✅ Đã gửi — Nhập TXN ID","change_net":"⬅️ Đổi mạng",
  "txn_ask":"🔑 <b>Nhập mã giao dịch (TXN ID)</b>\n\nGửi <b>TXN ID / mã hash</b> của bạn.\n\n<i>Bắt buộc để xác minh thanh toán.</i>",
  "txn_ok":"✅ <b>Yêu cầu nạp tiền đã được gửi!</b>",
  "txn_pending":"⚡ TXN ID đang được xác minh.\n📋 Trạng thái: <b>Đang chờ</b>\n⏳ Thời gian: tối đa 3 giờ",
  "reference":"📌 Mã tham chiếu",
  "profile_title":"👤 Hồ sơ","id":"🆔 ID","name_lbl":"👤 Tên","username_lbl":"📛 Username",
  "joined":"📅 Ngày tham gia","balance":"💰 Số dư","orders_count":"📦 Đơn hàng",
  "orders_title":"📋 Đơn hàng","no_orders":"Chưa có đơn hàng.",
  "order_placed":"✅ Đặt hàng thành công!","product_lbl":"📦 Sản phẩm","qty_lbl":"🔢 Số lượng",
  "paid_lbl":"💰 Đã trả","ref_lbl":"📋 Mã","balance_lbl":"👛 Số dư",
  "deliver_note": lambda s: f"⏳ <b>Sản phẩm sẽ giao trong 5–10 phút.</b>\nChưa nhận? Liên hệ {s}",
  "my_orders_btn":"📋 Đơn hàng","continue_btn":"🛍 Tiếp tục mua",
  "insuf_bal":"❌ Số dư không đủ","price_lbl":"💰 Giá","bal_lbl":"👛 Số dư",
  "need_more": lambda n: f"⚠️ Bạn cần thêm <b>${n:.2f}</b>.",
  "redeem_title":"🎁 Mã đổi thưởng","redeem_send":"Gửi mã của bạn:",
  "redeemed":"🎉 Đổi thưởng thành công!","redeem_added": lambda a,b: f"💰 Đã thêm <b>${a:.2f} USDT</b>!\nSố dư: <b>${b:.2f} USDT</b>",
  "support_title":"🆘 Hỗ trợ","support_body": lambda s: f"Liên hệ: {s}",
  "net_unavail":"Mạng không khả dụng.","not_found":"Không tìm thấy.",
  "main_menu":"🏠 Menu Chính","back_btn":"⬅️ Quay lại","refresh_btn":"🔄 Làm mới","menu_btn":"🏠 Menu",
  "lang_btn":"🌐 Ngôn ngữ","products_btn":"🛍 Sản phẩm","redeem_btn":"🎁 Mã đổi thưởng",
  "profile_btn":"👤 Hồ sơ","history_btn":"📋 Đơn hàng","wallet_btn":"👛 Ví","support_btn":"🆘 Hỗ trợ",
},
}

def tr(ctx, key, *args):
    lang = ctx.user_data.get("lang","en")
    val  = T.get(lang, T["en"]).get(key, T["en"].get(key, key))
    return val(*args) if callable(val) else val

# ── Keyboards ───────────────────────────────────────────────────────────────────
def kb_lang():
    return InlineKeyboardMarkup([[InlineKeyboardButton(v, callback_data=f"setlang_{k}")] for k,v in LANGS.items()])

def kb_main(ctx):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(tr(ctx,"products_btn"), callback_data="products"),
         InlineKeyboardButton(tr(ctx,"redeem_btn"),   callback_data="redeem")],
        [InlineKeyboardButton(tr(ctx,"profile_btn"),  callback_data="profile"),
         InlineKeyboardButton(tr(ctx,"history_btn"),  callback_data="history")],
        [InlineKeyboardButton(tr(ctx,"wallet_btn"),   callback_data="wallet")],
        [InlineKeyboardButton(tr(ctx,"support_btn"),  callback_data="support"),
         InlineKeyboardButton(tr(ctx,"lang_btn"),     callback_data="lang_menu")],
    ])

def kb_back(ctx):
    return InlineKeyboardMarkup([[InlineKeyboardButton(tr(ctx,"main_menu"), callback_data="main_menu")]])

def kb_products(ctx, prods):
    rows = [[InlineKeyboardButton(
        f"📦 {p['name']}  |  ${p['price']:.2f}  |  {p['stock']} {tr(ctx,'left')}",
        callback_data=f"acc_{p['id']}")] for p in prods]
    rows.append([InlineKeyboardButton(tr(ctx,"refresh_btn"), callback_data="products"),
                 InlineKeyboardButton(tr(ctx,"menu_btn"),    callback_data="main_menu")])
    return InlineKeyboardMarkup(rows)

def kb_qty(ctx, pid, stock):
    options = [q for q in [1,2,3,5,10] if q <= stock]
    rows = [[InlineKeyboardButton(str(q), callback_data=f"qty_{pid}_{q}") for q in options]] if options else []
    rows.append([InlineKeyboardButton(tr(ctx,"qty_custom"), callback_data=f"qty_custom_{pid}")])
    rows.append([InlineKeyboardButton(tr(ctx,"back_btn"),   callback_data="products"),
                 InlineKeyboardButton(tr(ctx,"menu_btn"),   callback_data="main_menu")])
    return InlineKeyboardMarkup(rows)

def kb_confirm(ctx, pid, qty):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(tr(ctx,"confirm_btn"), callback_data=f"confirm_{pid}_{qty}")],
        [InlineKeyboardButton(tr(ctx,"cancel_btn"),  callback_data=f"acc_{pid}")],
    ])

def kb_wallet(ctx):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(tr(ctx,"deposit_btn"), callback_data="deposit_menu")],
        [InlineKeyboardButton(tr(ctx,"main_menu"),   callback_data="main_menu")],
    ])

def kb_nets(ctx, wallets):
    rows = [[InlineKeyboardButton(label, callback_data=f"pay_net_{key}")] for key,(label,_) in wallets.items()]
    rows.append([InlineKeyboardButton(tr(ctx,"cancel_btn"), callback_data="wallet")])
    return InlineKeyboardMarkup(rows)

def kb_sent(ctx, key):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(tr(ctx,"sent_btn"),   callback_data=f"sent_{key}")],
        [InlineKeyboardButton(tr(ctx,"change_net"), callback_data="deposit_menu")],
    ])

async def safe_ans(q, text="", alert=False):
    try: await q.answer(text, show_alert=alert)
    except BadRequest: pass

# ── Handlers ────────────────────────────────────────────────────────────────────
async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db.ensure_user(user.id, user.first_name, user.username or "")
    if "lang" not in ctx.user_data:
        await update.message.reply_text(
            "🌐 <b>Choose your language / 选择语言 / Выберите язык / Chọn ngôn ngữ</b>",
            parse_mode=HTML, reply_markup=kb_lang())
        return
    await update.message.reply_text(tr(ctx,"welcome",user.first_name,BOT_NAME), parse_mode=HTML, reply_markup=kb_main(ctx))

async def on_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; data = q.data; user = update.effective_user
    db.ensure_user(user.id, user.first_name, user.username or "")
    await safe_ans(q)

    if data == "lang_menu":
        await q.edit_message_text("🌐 <b>Choose your language / 选择语言 / Выберите язык / Chọn ngôn ngữ</b>",
                                  parse_mode=HTML, reply_markup=kb_lang()); return
    if data.startswith("setlang_"):
        lang = data[8:]
        if lang in T: ctx.user_data["lang"] = lang
        await q.edit_message_text(tr(ctx,"welcome",user.first_name,BOT_NAME), parse_mode=HTML, reply_markup=kb_main(ctx)); return

    if data == "main_menu":
        await q.edit_message_text(f"🏠 <b>{tr(ctx,'main_menu')}</b>", parse_mode=HTML, reply_markup=kb_main(ctx))

    elif data == "products":
        prods = db.get_active_products()
        if not prods:
            await q.edit_message_text(tr(ctx,"no_products"), reply_markup=kb_back(ctx)); return
        await q.edit_message_text(f"🛍 <b>{tr(ctx,'products')}</b>\n\n{tr(ctx,'choose')}",
                                  parse_mode=HTML, reply_markup=kb_products(ctx, prods))

    elif data.startswith("acc_"):
        pid = int(data[4:]); p = db.get_product(pid)
        if not p: await safe_ans(q, tr(ctx,"not_found"), alert=True); return
        if p["stock"] <= 0:
            await q.edit_message_text(tr(ctx,"out_of_stock"), reply_markup=kb_back(ctx)); return
        await q.edit_message_text(tr(ctx,"qty_ask",p["name"],p["price"],p["stock"]),
                                  parse_mode=HTML, reply_markup=kb_qty(ctx, pid, p["stock"]))

    elif data.startswith("qty_") and not data.startswith("qty_custom_"):
        parts = data[4:].rsplit("_",1); pid = int(parts[0]); qty = int(parts[1])
        p = db.get_product(pid)
        if not p: await safe_ans(q, tr(ctx,"not_found"), alert=True); return
        if qty > p["stock"]: await safe_ans(q, tr(ctx,"qty_exceed",p["stock"]), alert=True); return
        total = round(p["price"]*qty, 2); bal = db.get_balance(user.id)
        await q.edit_message_text(tr(ctx,"confirm_order",p["name"],qty,p["price"],total,bal),
                                  parse_mode=HTML, reply_markup=kb_confirm(ctx,pid,qty))

    elif data.startswith("qty_custom_"):
        pid = int(data[11:]); p = db.get_product(pid)
        if not p: await safe_ans(q, tr(ctx,"not_found"), alert=True); return
        ctx.user_data["state"] = "awaiting_qty"; ctx.user_data["qty_pid"] = pid
        await q.edit_message_text(tr(ctx,"qty_enter",p["name"],p["stock"]), parse_mode=HTML,
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(tr(ctx,"cancel_btn"), callback_data=f"acc_{pid}")]]))

    elif data.startswith("confirm_"):
        parts = data[8:].rsplit("_",1); pid = int(parts[0]); qty = int(parts[1])
        await _place_order(q, ctx, user.id, pid, qty)

    elif data == "wallet":
        bal = db.get_balance(user.id)
        await q.edit_message_text(
            f"{tr(ctx,'wallet_title')}\n\n{tr(ctx,'wallet_balance')}: <b>${bal:.2f} USDT</b>\n\n{tr(ctx,'wallet_note')}",
            parse_mode=HTML, reply_markup=kb_wallet(ctx))

    elif data == "deposit_menu":
        wallets = db.get_active_wallets()
        await q.edit_message_text(f"💳 <b>{tr(ctx,'deposit_title')}</b>\n\n{tr(ctx,'deposit_min')}",
                                  parse_mode=HTML, reply_markup=kb_nets(ctx, wallets))

    elif data.startswith("pay_net_"):
        key = data[8:]; wallets = db.get_active_wallets()
        if key not in wallets: await safe_ans(q, tr(ctx,"net_unavail"), alert=True); return
        label, addr = wallets[key]
        ctx.user_data["dep_network"] = key; ctx.user_data["dep_network_label"] = label
        await q.edit_message_text(
            f"💳 <b>{tr(ctx,'deposit_via',label)}</b>\n\n{tr(ctx,'send_to')}\n<code>{addr}</code>\n\n{tr(ctx,'after_send')}",
            parse_mode=HTML, reply_markup=kb_sent(ctx, key))

    elif data.startswith("sent_"):
        ctx.user_data["state"]       = "awaiting_txn"
        ctx.user_data["dep_ref"]     = db.new_ref("DEP")
        ctx.user_data["dep_network"] = ctx.user_data.get("dep_network_label", ctx.user_data.get("dep_network","Unknown"))
        await q.edit_message_text(tr(ctx,"txn_ask"), parse_mode=HTML,
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(tr(ctx,"cancel_btn"), callback_data="wallet")]]))

    elif data == "profile":
        row = db.get_user_info(user.id); orders = db.get_orders(user.id)
        if row:
            name, username, created_at, balance = row
            txt = (f"{tr(ctx,'profile_title')}\n━━━━━━━━━━━━━━━━━━\n"
                   f"{tr(ctx,'id')}           : <code>{user.id}</code>\n"
                   f"{tr(ctx,'name_lbl')}     : <b>{name}</b>\n"
                   f"{tr(ctx,'username_lbl')} : {'@'+username if username else '—'}\n"
                   f"{tr(ctx,'joined')}       : {(created_at or '')[:10]}\n"
                   f"{tr(ctx,'balance')}      : <b>${balance:.2f} USDT</b>\n"
                   f"{tr(ctx,'orders_count')} : <b>{len(orders)}</b>")
            await q.edit_message_text(txt, parse_mode=HTML,
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton(tr(ctx,"deposit_btn"), callback_data="deposit_menu")],
                    [InlineKeyboardButton(tr(ctx,"main_menu"),   callback_data="main_menu")]]))

    elif data == "history":
        orders = db.get_orders(user.id)
        if not orders:
            txt = f"{tr(ctx,'orders_title')}\n\n{tr(ctx,'no_orders')}"
        else:
            lines = []
            for row in orders[:20]:
                ref,name,price,status,created = row[0],row[1],row[2],row[3],row[4]
                qty = row[5] if len(row)>5 else 1
                icon = "✅" if status=="delivered" else "⏳"
                lines.append(f"{icon} <code>{ref}</code>\n   📦 {name} x{qty} — ${price:.2f}\n   📅 {created}")
            txt = f"{tr(ctx,'orders_title')}\n\n" + "\n\n".join(lines)
        await q.edit_message_text(txt, parse_mode=HTML, reply_markup=kb_back(ctx))

    elif data == "redeem":
        ctx.user_data["state"] = "awaiting_redeem"
        await q.edit_message_text(f"🎁 <b>{tr(ctx,'redeem_title')}</b>\n\n{tr(ctx,'redeem_send')}",
            parse_mode=HTML,
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(tr(ctx,"cancel_btn"), callback_data="main_menu")]]))

    elif data == "support":
        await q.edit_message_text(f"🆘 <b>{tr(ctx,'support_title')}</b>\n\n{tr(ctx,'support_body',SUPPORT)}",
                                  parse_mode=HTML, reply_markup=kb_back(ctx))

async def _place_order(q, ctx, user_id, pid, qty):
    p = db.get_product(pid)
    if not p: await q.edit_message_text(tr(ctx,"not_found"), reply_markup=kb_back(ctx)); return
    if qty > p["stock"]:
        await q.edit_message_text(tr(ctx,"qty_exceed",p["stock"]), parse_mode=HTML,
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(tr(ctx,"back_btn"), callback_data=f"acc_{pid}")]])); return
    total = round(p["price"]*qty, 2); balance = db.get_balance(user_id)
    if balance < total:
        needed = total - balance
        await q.edit_message_text(
            f"❌ <b>{tr(ctx,'insuf_bal')}</b>\n\n"
            f"{tr(ctx,'price_lbl')} : <b>${total:.2f} USDT</b>\n"
            f"{tr(ctx,'bal_lbl')}   : <b>${balance:.2f} USDT</b>\n━━━━━━━━━━━━━━━━━━\n"
            f"{tr(ctx,'need_more',needed)}",
            parse_mode=HTML,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton(tr(ctx,"deposit_btn"), callback_data="deposit_menu")],
                [InlineKeyboardButton(tr(ctx,"main_menu"),   callback_data="main_menu")]])); return
    db.deduct_balance(user_id, total)
    order_ref = db.new_ref("TG")
    db.save_order(user_id, p, order_ref, quantity=qty)
    await q.edit_message_text(
        f"✅ <b>{tr(ctx,'order_placed')}</b>\n\n"
        f"{tr(ctx,'product_lbl')} : <b>{p['name']}</b>\n"
        f"{tr(ctx,'qty_lbl')}     : <b>{qty}</b>\n"
        f"{tr(ctx,'paid_lbl')}    : <b>${total:.2f} USDT</b>\n"
        f"{tr(ctx,'ref_lbl')}     : <code>{order_ref}</code>\n"
        f"{tr(ctx,'balance_lbl')} : <b>${db.get_balance(user_id):.2f} USDT</b>\n\n"
        f"{tr(ctx,'deliver_note',SUPPORT)}",
        parse_mode=HTML,
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton(tr(ctx,"my_orders_btn"), callback_data="history")],
            [InlineKeyboardButton(tr(ctx,"continue_btn"),  callback_data="products")]]))

async def on_text(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user; text = (update.message.text or "").strip()
    state = ctx.user_data.get("state")
    db.ensure_user(user.id, user.first_name, user.username or "")

    if state == "awaiting_txn":
        if not text: await update.message.reply_text(tr(ctx,"txn_ask"), parse_mode=HTML); return
        ref     = ctx.user_data.pop("dep_ref",    db.new_ref("DEP"))
        network = ctx.user_data.pop("dep_network","Unknown")
        ctx.user_data.pop("state", None)
        db.save_deposit_proof(user.id, ref, network, text)
        await update.message.reply_text(
            f"{tr(ctx,'txn_ok')}\n\n{tr(ctx,'txn_pending')}\n\n{tr(ctx,'reference')}: <code>{ref}</code>",
            parse_mode=HTML, reply_markup=kb_back(ctx))

    elif state == "awaiting_qty":
        pid = ctx.user_data.get("qty_pid"); p = db.get_product(pid) if pid else None
        if not p: ctx.user_data.pop("state",None); await update.message.reply_text(tr(ctx,"not_found")); return
        try:
            qty = int(text)
            if qty < 1: raise ValueError
        except ValueError:
            await update.message.reply_text(tr(ctx,"qty_invalid",p["stock"]), parse_mode=HTML); return
        if qty > p["stock"]:
            await update.message.reply_text(tr(ctx,"qty_exceed",p["stock"]), parse_mode=HTML); return
        ctx.user_data.pop("state",None); ctx.user_data.pop("qty_pid",None)
        total = round(p["price"]*qty,2); bal = db.get_balance(user.id)
        await update.message.reply_text(tr(ctx,"confirm_order",p["name"],qty,p["price"],total,bal),
            parse_mode=HTML, reply_markup=kb_confirm(ctx, pid, qty))

    elif state == "awaiting_redeem":
        ctx.user_data.pop("state",None)
        amount, msg = db.try_redeem(user.id, text)
        if amount:
            await update.message.reply_text(
                f"🎉 <b>{tr(ctx,'redeemed')}</b>\n\n{tr(ctx,'redeem_added',amount,db.get_balance(user.id))}",
                parse_mode=HTML, reply_markup=kb_back(ctx))
        else:
            await update.message.reply_text(msg, reply_markup=kb_back(ctx))

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
