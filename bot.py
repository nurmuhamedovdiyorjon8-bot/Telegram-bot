import os
import logging
import time
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import (
    Application, CommandHandler, MessageHandler, CallbackQueryHandler,
    ContextTypes, ConversationHandler, filters
)
from datetime import datetime
import data_manager as dm

# ===================== SOZLAMALAR =====================
BOT_TOKEN = "8737542268:AAFnjoONYCWIWzpjSp2qFe8Ux1OXy3LTQ-o"
ADMIN_GROUP_ID = -100000000000  # Telegram guruh ID (manfiy son)
ADMIN_IDS = [5239156029]  # Admin Telegram ID lari

# ===================== LOGGING =====================
logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

# ===================== HOLAT KONSTANTALARI =====================
(
    MAIN_MENU, CATALOG, CART, PHONE, ADDRESS, FLOOR, PAYMENT, CONFIRM,
    ADMIN_MENU, BROADCAST_MSG
) = range(10)

# ===================== KLAVIATURALAR =====================
def main_keyboard():
    return ReplyKeyboardMarkup([
        ["🛒 Buyurtma berish", "📋 Mening buyurtmalarim"],
        ["📞 Bog'lanish", "ℹ️ Ma'lumot"],
    ], resize_keyboard=True)

def admin_keyboard():
    return ReplyKeyboardMarkup([
        ["📦 Buyurtmalar", "👥 Mijozlar"],
        ["📣 Xabar yuborish", "📊 Statistika"],
        ["⚙️ Sozlamalar", "🔙 Orqaga"],
    ], resize_keyboard=True)

def payment_keyboard():
    return ReplyKeyboardMarkup([
        ["💵 Naqt", "💳 Plastik karta"],
        ["📱 Payme", "🏦 Bank o'tkazma"],
        ["🔙 Orqaga"],
    ], resize_keyboard=True)

def catalog_inline(products):
    buttons = []
    for p in products:
        buttons.append([InlineKeyboardButton(
            f"{p['image']} {p['name']} — {int(p['price']):,} so'm",
            callback_data=f"add_{p['id']}"
        )])
    buttons.append([InlineKeyboardButton("🛒 Savatni ko'rish", callback_data="view_cart")])
    buttons.append([InlineKeyboardButton("🏠 Bosh sahifa", callback_data="home")])
    return InlineKeyboardMarkup(buttons)

def cart_inline(cart_items):
    buttons = []
    for item in cart_items:
        buttons.append([
            InlineKeyboardButton("➖", callback_data=f"dec_{item['id']}"),
            InlineKeyboardButton(f"{item['name']} x{item['qty']}", callback_data="noop"),
            InlineKeyboardButton("➕", callback_data=f"inc_{item['id']}"),
        ])
    buttons.append([InlineKeyboardButton("✅ Buyurtma berish", callback_data="checkout")])
    buttons.append([InlineKeyboardButton("🗑 Savatni tozalash", callback_data="clear_cart")])
    buttons.append([InlineKeyboardButton("🔙 Katalogga qaytish", callback_data="catalog")])
    return InlineKeyboardMarkup(buttons)

# ===================== YORDAMCHI FUNKSIYALAR =====================
def format_cart(cart):
    if not cart:
        return "🛒 Savat bo'sh"
    lines = ["🛒 *Sizning savatingiz:*\n"]
    total = 0
    for item in cart:
        subtotal = item['price'] * item['qty']
        total += subtotal
        lines.append(f"• {item['image']} {item['name']} x {item['qty']} = *{subtotal:,} so'm*")
    lines.append(f"\n💰 *Jami: {total:,} so'm*")
    return "\n".join(lines)

def format_order_for_group(order, customer):
    products = dm.get_products()
    prod_map = {p['id']: p for p in products}
    items_text = "\n".join([
        f"  • {prod_map.get(i['id'], {}).get('image','📦')} {i['name']} x {i['qty']} = {i['price']*i['qty']:,} so'm"
        for i in order['items']
    ])
    total = sum(i['price'] * i['qty'] for i in order['items'])
    return (
        f"🆕 *YANGI BUYURTMA #{order['id']}*\n\n"
        f"👤 Mijoz: {customer['name']}\n"
        f"📱 Telefon: `{customer['phone']}`\n"
        f"🏠 Manzil: {order['address']}\n"
        f"🏢 Qavat: {order['floor']}\n"
        f"💳 To'lov: {order['payment']}\n\n"
        f"📦 *Mahsulotlar:*\n{items_text}\n\n"
        f"💰 *Jami: {total:,} so'm*\n"
        f"🕐 Vaqt: {order['date']}"
    )

# ===================== START =====================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    dm.get_or_create_customer(user.id, user.full_name)
    context.user_data.clear()
    context.user_data['cart'] = []

    settings = dm.get_settings()
    welcome = settings.get('welcome_text',
        f"💧 Salom, *{user.first_name}*!\n\nMarkiz Premium botiga xush kelibsiz!\n"
        f"Toza suv va aksessuarlarni qulay narxda buyurtma qiling. 🚚"
    )
    await update.message.reply_text(welcome, parse_mode="Markdown", reply_markup=main_keyboard())
    return MAIN_MENU

# ===================== ADMIN =====================
async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("❌ Ruxsat yo'q.")
        return MAIN_MENU
    await update.message.reply_text("👨‍💼 *Admin panel*", parse_mode="Markdown", reply_markup=admin_keyboard())
    return ADMIN_MENU

async def admin_menu_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text

    if text == "📦 Buyurtmalar":
        orders = dm.get_orders()
        if not orders:
            await update.message.reply_text("📦 Hozircha buyurtma yo'q.")
            return ADMIN_MENU
        last_orders = orders[-10:][::-1]
        msg = "📦 *So'nggi 10 buyurtma:*\n\n"
        for o in last_orders:
            total = sum(i['price'] * i['qty'] for i in o.get('items', []))
            msg += f"#{o['id']} | {o.get('customer_name','?')} | {total:,} so'm | {o['status']}\n"
        await update.message.reply_text(msg, parse_mode="Markdown")

    elif text == "👥 Mijozlar":
        customers = dm.get_customers()
        msg = f"👥 *Jami mijozlar: {len(customers)} ta*\n\n"
        for c in customers[-10:][::-1]:
            msg += f"• {c['name']} — {c['phone']} — {c['orders_count']} buyurtma\n"
        await update.message.reply_text(msg, parse_mode="Markdown")

    elif text == "📊 Statistika":
        orders = dm.get_orders()
        customers = dm.get_customers()
        total_rev = sum(sum(i['price'] * i['qty'] for i in o.get('items', [])) for o in orders)
        today = datetime.now().strftime("%Y-%m-%d")
        today_orders = [o for o in orders if o.get('date', '').startswith(today)]
        today_rev = sum(sum(i['price'] * i['qty'] for i in o.get('items', [])) for o in today_orders)
        msg = (
            f"📊 *Statistika*\n\n"
            f"📦 Jami buyurtmalar: *{len(orders)}*\n"
            f"📦 Bugungi buyurtmalar: *{len(today_orders)}*\n"
            f"👥 Jami mijozlar: *{len(customers)}*\n"
            f"💰 Bugungi daromad: *{today_rev:,} so'm*\n"
            f"💰 Jami daromad: *{total_rev:,} so'm*"
        )
        await update.message.reply_text(msg, parse_mode="Markdown")

    elif text == "📣 Xabar yuborish":
        await update.message.reply_text(
            "📣 Barcha mijozlarga yuboriladigan xabarni yozing:\n\n"
            "(Bekor qilish uchun /cancel)"
        )
        return BROADCAST_MSG

    elif text == "⚙️ Sozlamalar":
        settings = dm.get_settings()
        products = dm.get_products()
        prod_text = "\n".join([f"• {p['image']} {p['name']}: {int(p['price']):,} so'm" for p in products])
        msg = (
            f"⚙️ *Sozlamalar*\n\n"
            f"📍 Manzil: {settings.get('location', 'samarqand')}\n"
            f"🕐 Ish vaqti: {settings.get('work_start', '08:00')}–{settings.get('work_end', '17:00')}\n"
            f"🚚 Min buyurtma: {int(settings.get('min_order', 45000)):,} so'm\n\n"
            f"🛍 *Mahsulotlar:*\n{prod_text}\n\n"
            f"Narx o'zgartirish uchun boshqaruv panelidan foydalaning."
        )
        await update.message.reply_text(msg, parse_mode="Markdown")

    elif text == "🔙 Orqaga":
        await update.message.reply_text("🏠 Bosh sahifa", reply_markup=main_keyboard())
        return MAIN_MENU

    return ADMIN_MENU

async def broadcast_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg_text = update.message.text
    if msg_text == "/cancel":
        await update.message.reply_text("❌ Bekor qilindi.", reply_markup=admin_keyboard())
        return ADMIN_MENU

    customers = dm.get_customers()
    sent = 0
    failed = 0
    for c in customers:
        try:
            await context.bot.send_message(
                chat_id=c['telegram_id'],
                text=f"📢 *Xabar:*\n\n{msg_text}",
                parse_mode="Markdown"
            )
            sent += 1
        except Exception:
            failed += 1

    await update.message.reply_text(
        f"✅ Xabar yuborildi!\n✓ Muvaffaqiyatli: {sent}\n✗ Xato: {failed}",
        reply_markup=admin_keyboard()
    )
    return ADMIN_MENU

# ===================== KATALOG =====================
async def show_catalog(update: Update, context: ContextTypes.DEFAULT_TYPE):
    products = dm.get_products()
    if not update.message:
        query = update.callback_query
        await query.answer()
        cart = context.user_data.get('cart', [])
        cart_count = sum(i['qty'] for i in cart)
        text = "🛍 *Katalog*\n\nMahsulot tanlang:\n\n"
        for p in products:
            text += f"{p['image']} *{p['name']}* — {int(p['price']):,} so'm\n"
        text += f"\n🛒 Savatingizda: {cart_count} ta mahsulot"
        await query.edit_message_text(text, parse_mode="Markdown", reply_markup=catalog_inline(products))
        return CATALOG

    cart = context.user_data.get('cart', [])
    cart_count = sum(i['qty'] for i in cart)
    text = "🛍 *Katalog*\n\nMahsulot tanlang:\n\n"
    for p in products:
        text += f"{p['image']} *{p['name']}* — {int(p['price']):,} so'm\n"
    text += f"\n🛒 Savatingizda: {cart_count} ta mahsulot"
    await update.message.reply_text(text, parse_mode="Markdown", reply_markup=catalog_inline(products))
    return CATALOG

async def catalog_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    products = dm.get_products()
    prod_map = {p['id']: p for p in products}

    if data.startswith("add_"):
        prod_id = int(data.split("_")[1])
        product = prod_map.get(prod_id)
        if not product:
            return CATALOG
        cart = context.user_data.setdefault('cart', [])
        existing = next((i for i in cart if i['id'] == prod_id), None)
        if existing:
            existing['qty'] += 1
        else:
            cart.append({
                'id': prod_id,
                'name': product['name'],
                'image': product['image'],
                'price': product['price'],
                'qty': 1
            })
        await query.answer(f"✅ {product['name']} savatga qo'shildi!")
        cart_count = sum(i['qty'] for i in cart)
        text = "🛍 *Katalog*\n\nMahsulot tanlang:\n\n"
        for p in products:
            text += f"{p['image']} *{p['name']}* — {int(p['price']):,} so'm\n"
        text += f"\n🛒 Savatingizda: {cart_count} ta mahsulot"
        await query.edit_message_text(text, parse_mode="Markdown", reply_markup=catalog_inline(products))

    elif data == "view_cart":
        cart = context.user_data.get('cart', [])
        if not cart:
            await query.answer("🛒 Savat bo'sh!", show_alert=True)
            return CATALOG
        await query.edit_message_text(format_cart(cart), parse_mode="Markdown", reply_markup=cart_inline(cart))
        return CART

    elif data == "home":
        await query.edit_message_text("🏠 Bosh sahifaga qaytdingiz.")
        await query.message.reply_text("Kerakli bo'limni tanlang:", reply_markup=main_keyboard())
        return MAIN_MENU

    return CATALOG

async def cart_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    cart = context.user_data.setdefault('cart', [])

    if data.startswith("inc_"):
        prod_id = int(data.split("_")[1])
        for item in cart:
            if item['id'] == prod_id:
                item['qty'] += 1
                break

    elif data.startswith("dec_"):
        prod_id = int(data.split("_")[1])
        for item in cart:
            if item['id'] == prod_id:
                item['qty'] -= 1
                if item['qty'] <= 0:
                    cart.remove(item)
                break

    elif data == "clear_cart":
        context.user_data['cart'] = []
        await query.edit_message_text("🗑 Savat tozalandi.")
        products = dm.get_products()
        await query.message.reply_text("🛍 Katalog:", parse_mode="Markdown", reply_markup=catalog_inline(products))
        return CATALOG

    elif data == "catalog":
        products = dm.get_products()
        text = "🛍 *Katalog*\n\nMahsulot tanlang:"
        await query.edit_message_text(text, parse_mode="Markdown", reply_markup=catalog_inline(products))
        return CATALOG

    elif data == "checkout":
        cart = context.user_data.get('cart', [])
        if not cart:
            await query.answer("🛒 Savat bo'sh!", show_alert=True)
            return CART
        await query.edit_message_text(
            "📱 *Telefon raqamingizni yuboring:*\n\nQuyidagi tugmani bosing yoki qo'lda kiriting (+998xxxxxxxxx)",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[]])
        )
        kb = ReplyKeyboardMarkup(
            [[KeyboardButton("📱 Raqamni yuborish", request_contact=True)], ["🔙 Orqaga"]],
            resize_keyboard=True, one_time_keyboard=True
        )
        await query.message.reply_text("👇", reply_markup=kb)
        return PHONE

    if cart:
        await query.edit_message_text(format_cart(cart), parse_mode="Markdown", reply_markup=cart_inline(cart))
    else:
        products = dm.get_products()
        await query.edit_message_text("🛒 Savat bo'sh.", reply_markup=catalog_inline(products))
        return CATALOG

    return CART

# ===================== CHECKOUT JARAYONI =====================
async def get_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.contact:
        phone = update.message.contact.phone_number
        if not phone.startswith("+"):
            phone = "+" + phone
    else:
        phone = update.message.text.strip()
        if update.message.text == "🔙 Orqaga":
            cart = context.user_data.get('cart', [])
            await update.message.reply_text(format_cart(cart), parse_mode="Markdown", reply_markup=cart_inline(cart))
            return CART
    context.user_data['phone'] = phone
    await update.message.reply_text(
        "🏠 *Manzilingizni kiriting:*\n\n_(Ko'cha nomi, uy raqami)_\nMasalan: Chilonzor ko'chasi, 12-uy",
        parse_mode="Markdown",
        reply_markup=ReplyKeyboardMarkup([["🔙 Orqaga"]], resize_keyboard=True)
    )
    return ADDRESS

async def get_address(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text == "🔙 Orqaga":
        kb = ReplyKeyboardMarkup(
            [[KeyboardButton("📱 Raqamni yuborish", request_contact=True)], ["🔙 Orqaga"]],
            resize_keyboard=True
        )
        await update.message.reply_text("📱 Telefon raqamingizni yuboring:", reply_markup=kb)
        return PHONE
    context.user_data['address'] = update.message.text
    await update.message.reply_text(
        "🏢 *Necha-nchi qavatdasiz?*\n\nMasalan: 1-qavat",
        parse_mode="Markdown",
        reply_markup=ReplyKeyboardMarkup(
            [["1-qavat", "2-qavat", "3-qavat"], ["4-qavat", "5-qavat+", "🔙 Orqaga"]],
            resize_keyboard=True
        )
    )
    return FLOOR

async def get_floor(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text == "🔙 Orqaga":
        await update.message.reply_text(
            "🏠 Manzilingizni kiriting:",
            reply_markup=ReplyKeyboardMarkup([["🔙 Orqaga"]], resize_keyboard=True)
        )
        return ADDRESS
    context.user_data['floor'] = update.message.text
    await update.message.reply_text(
        "💳 *To'lov usulini tanlang:*",
        parse_mode="Markdown",
        reply_markup=payment_keyboard()
    )
    return PAYMENT

async def get_payment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text == "🔙 Orqaga":
        await update.message.reply_text(
            "🏢 Qavatni tanlang:",
            reply_markup=ReplyKeyboardMarkup(
                [["1-qavat", "2-qavat", "3-qavat"], ["4-qavat", "5-qavat+", "🔙 Orqaga"]],
                resize_keyboard=True
            )
        )
        return FLOOR
    context.user_data['payment'] = update.message.text
    cart = context.user_data.get('cart', [])
    total = sum(i['price'] * i['qty'] for i in cart)
    confirm_text = (
        f"✅ *Buyurtmani tasdiqlang:*\n\n"
        f"{format_cart(cart)}\n\n"
        f"📱 Telefon: {context.user_data['phone']}\n"
        f"🏠 Manzil: {context.user_data['address']}\n"
        f"🏢 Qavat: {context.user_data['floor']}\n"
        f"💳 To'lov: {context.user_data['payment']}\n\n"
        f"💰 *Jami: {total:,} so'm*"
    )
    await update.message.reply_text(
        confirm_text,
        parse_mode="Markdown",
        reply_markup=ReplyKeyboardMarkup([["✅ Tasdiqlash"], ["🔙 Orqaga"]], resize_keyboard=True)
    )
    return CONFIRM

async def confirm_order(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text == "🔙 Orqaga":
        await update.message.reply_text("💳 To'lov usulini tanlang:", reply_markup=payment_keyboard())
        return PAYMENT

    user = update.effective_user
    cart = context.user_data.get('cart', [])
    phone = context.user_data.get('phone', '')
    address = context.user_data.get('address', '')
    floor = context.user_data.get('floor', '')
    payment = context.user_data.get('payment', '')

    dm.get_or_create_customer(user.id, user.full_name, phone)
    dm.update_customer_phone(user.id, phone)

    order = dm.save_order(
        customer_id=user.id,
        customer_name=user.full_name,
        items=cart,
        address=address,
        floor=floor,
        payment=payment,
        phone=phone
    )

    total = sum(i['price'] * i['qty'] for i in cart)

    try:
        group_msg = format_order_for_group(order, {'name': user.full_name, 'phone': phone})
        order_kb = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("✅ Qabul qilindi", callback_data=f"status_accept_{order['id']}"),
                InlineKeyboardButton("❌ Bekor qilish", callback_data=f"status_cancel_{order['id']}")
            ],
            [InlineKeyboardButton("🚚 Yetkazilmoqda", callback_data=f"status_delivery_{order['id']}")],
        ])
        await context.bot.send_message(ADMIN_GROUP_ID, group_msg, parse_mode="Markdown", reply_markup=order_kb)
    except Exception as e:
        logger.error(f"Guruhga xabar yuborishda xato: {e}")

    await update.message.reply_text(
        f"🎉 *Buyurtmangiz qabul qilindi!*\n\n"
        f"📋 Buyurtma raqami: *#{order['id']}*\n"
        f"💰 Summa: *{total:,} so'm*\n\n"
        f"⏳ Tez orada siz bilan bog'lanamiz.\n"
        f"Rahmat! 🙏",
        parse_mode="Markdown",
        reply_markup=main_keyboard()
    )
    context.user_data['cart'] = []
    return MAIN_MENU

# ===================== GURUH CALLBACK (STATUS) =====================
async def group_order_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data.startswith("status_"):
        parts = data.split("_")
        action = parts[1]
        order_id = int(parts[2])

        status_map = {
            "accept": ("✅ Qabul qilindi", "✅ Buyurtmangiz qabul qilindi! Tez orada yetkazamiz. 🚚"),
            "cancel": ("❌ Bekor qilindi", "❌ Afsuski, buyurtmangiz bekor qilindi. Iltimos, qaytadan urinib ko'ring."),
            "delivery": ("🚚 Yetkazilmoqda", "🚚 Buyurtmangiz yo'lda! Tez orada yetib boramiz."),
        }

        if action in status_map:
            status_text, customer_msg = status_map[action]
            order = dm.update_order_status(order_id, status_text)
            if order:
                try:
                    await context.bot.send_message(
                        chat_id=order['customer_id'],
                        text=f"📦 *Buyurtma #{order_id} holati:*\n\n{customer_msg}",
                        parse_mode="Markdown"
                    )
                except Exception as e:
                    logger.error(f"Mijozga xabar yuborishda xato: {e}")

            await query.edit_message_reply_markup(reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton(f"✓ {status_text}", callback_data="done")]
            ]))

# ===================== ODDIY XABARLAR =====================
async def main_menu_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text

    if text == "📋 Mening buyurtmalarim":
        orders = dm.get_customer_orders(update.effective_user.id)
        if not orders:
            await update.message.reply_text(
                "📋 Sizda hali buyurtma yo'q.\n\n🛒 Buyurtma berish uchun tugmani bosing!",
                reply_markup=main_keyboard()
            )
            return MAIN_MENU
        msg = "📋 *Sizning buyurtmalaringiz:*\n\n"
        for o in orders[-5:][::-1]:
            total = sum(i['price'] * i['qty'] for i in o.get('items', []))
            msg += f"#{o['id']} | {total:,} so'm | {o['status']}\n"
            msg += f"  📅 {o['date'][:10]}\n\n"
        await update.message.reply_text(msg, parse_mode="Markdown", reply_markup=main_keyboard())

    elif text == "📞 Bog'lanish":
        settings = dm.get_settings()
        await update.message.reply_text(
            f"📞 *Bog'lanish*\n\n"
            f"📍 Manzil: {settings.get('location', 'Samarqand')}\n"
            f"🕐 Ish vaqti: {settings.get('work_start', '08:00')}–{settings.get('work_end', '17:00')}\n"
            f"📱 Telefon: {settings.get('phone', '+998 77 285 01 10')}\n\n"
            f"🚚 Minimal buyurtma: {int(settings.get('min_order', 45000)):,} so'm\n"
            f"🎁 {int(settings.get('free_delivery_from', 100000)):,} so'mdan bepul yetkazish!",
            parse_mode="Markdown",
            reply_markup=main_keyboard()
        )

    elif text == "ℹ️ Ma'lumot":
        await update.message.reply_text(
            "ℹ️ *Bizning haqimizda*\n\n"
            "💧 Toza ichimlik suvi yetkazib berish xizmati\n\n"
            "✅ Sifatli mahsulotlar\n"
            "✅ Tez yetkazib berish\n"
            "✅ Qulay narxlar\n"
            "✅ Ishonchli xizmat",
            parse_mode="Markdown",
            reply_markup=main_keyboard()
        )

    return MAIN_MENU

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['cart'] = []
    await update.message.reply_text("❌ Bekor qilindi.", reply_markup=main_keyboard())
    return MAIN_MENU

# ===================== BOTNI ISHGA TUSHIRISH =====================
def main():
    app = Application.builder().token(BOT_TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler("start", start),
            MessageHandler(filters.Regex("^🛒 Buyurtma berish$"), show_catalog),
        ],
        states={
            MAIN_MENU: [
                MessageHandler(filters.Regex("^🛒 Buyurtma berish$"), show_catalog),
                MessageHandler(filters.TEXT & ~filters.COMMAND, main_menu_handler),
            ],
            CATALOG: [
                CallbackQueryHandler(catalog_callback),
            ],
            CART: [
                CallbackQueryHandler(cart_callback),
            ],
            PHONE: [
                MessageHandler(filters.CONTACT | filters.TEXT, get_phone),
            ],
            ADDRESS: [
                MessageHandler(filters.TEXT, get_address),
            ],
            FLOOR: [
                MessageHandler(filters.TEXT, get_floor),
            ],
            PAYMENT: [
                MessageHandler(filters.TEXT, get_payment),
            ],
            CONFIRM: [
                MessageHandler(filters.TEXT, confirm_order),
            ],
            ADMIN_MENU: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, admin_menu_handler),
            ],
            BROADCAST_MSG: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, broadcast_handler),
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        per_message=False,
    )

    app.add_handler(conv_handler)
    app.add_handler(CommandHandler("admin", admin_command))
    app.add_handler(CallbackQueryHandler(group_order_callback, pattern="^status_"))

    print("🤖 Bot ishga tushdi!")
    app.run_polling(
        allowed_updates=Update.ALL_TYPES,
        drop_pending_updates=True,
        timeout=30,
        read_timeout=30,
        write_timeout=30,
        connect_timeout=30,
        pool_timeout=30,
    )

if __name__ == "__main__":
    while True:
        try:
            print("🚀 Bot ishga tushmoqda...")
            main()
        except Exception as e:
            print(f"❌ Xato: {e}")
            print("⏳ 5 sekunddan keyin qayta uriniladi...")
            time.sleep(5)
