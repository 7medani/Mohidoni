import logging
from telegram import Update, Bot, ReplyKeyboardMarkup, InputMediaPhoto, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
from telegram.ext import JobQueue
import sqlite3
import os
import asyncio
from telegram.ext import ConversationHandler

# تنظیمات اولیه
TOKEN = '8112392981:AAHpNLBxxQtX3q0kuibuRrA8--EaXK_z-lc'
ADMIN_USERNAMES = ['admin1', 'admin2', 'hmedani1']  # نام کاربری ادمین‌ها را اینجا وارد کنید
DB_PATH = 'shop.db'

# مراحل گفتگو
ADD_PRODUCT, ADD_PHOTO, ADD_PRICE = range(3)

CATEGORIES = [
    'مانتو', 'لباس زیر', 'شومیز', 'شلوار', 'تاپ', 'دامن', 'پیراهن', 'کت و شلوار', 'ست زنانه', 'روسری', 'شال', 'پالتو', 'کاپشن', 'لباس مجلسی', 'لباس راحتی', 'لباس ورزشی', 'لباس بارداری', 'لباس خواب', 'جوراب', 'اکسسوری'
]

# راه‌اندازی دیتابیس
if not os.path.exists(DB_PATH):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''CREATE TABLE products (id INTEGER PRIMARY KEY, name TEXT, photo TEXT, price INTEGER, category TEXT)''')
    c.execute('''CREATE TABLE orders (id INTEGER PRIMARY KEY, user_id INTEGER, product_id INTEGER)''')
    conn.commit()
    conn.close()

# لاگ‌گیری
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logging.info('شروع اجرای فایل main.py')

# دکمه بازگشت برای همه عملیات‌ها
BACK_BUTTON = InlineKeyboardMarkup([[InlineKeyboardButton('بازگشت', callback_data='back_to_panel')]])

# تابع حذف پیام بعد از 10 دقیقه
async def delete_message_later(context, chat_id, message_id, delay=600):
    await asyncio.sleep(delay)
    try:
        await context.bot.delete_message(chat_id=chat_id, message_id=message_id)
    except Exception:
        pass

# ذخیره پیام‌های رسانه‌ای ارسالی برای حذف هنگام استارت
user_media_messages = {}

# متغیرهای موقت برای عملیات مدیریتی
admin_states = {}

# دستورات ربات
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    await delete_all_user_media(context, user.id)
    keyboard = [[InlineKeyboardButton('مشاهده محصولات', callback_data='choose_category_user')]]
    welcome = 'خوش آمدید به فروشگاه دینا شاپ!'
    if user.username in ADMIN_USERNAMES:
        keyboard = [[InlineKeyboardButton('پنل مدیریت', callback_data='admin_panel')]]
        welcome = 'خوش آمدید ادمین عزیز!'
    if update.callback_query:
        await update.callback_query.edit_message_text(welcome, reply_markup=InlineKeyboardMarkup(keyboard))
    else:
        await update.message.reply_text(welcome, reply_markup=InlineKeyboardMarkup(keyboard))

# تابع حذف همه پیام‌های رسانه‌ای کاربر و ربات
async def delete_all_user_media(context, user_id):
    msgs = user_media_messages.get(user_id, [])
    for chat_id, message_id in msgs:
        try:
            await context.bot.delete_message(chat_id=chat_id, message_id=message_id)
        except Exception:
            pass
    user_media_messages[user_id] = []
    # حذف همه پیام‌های رسانه‌ای در چت کاربر (چه از ربات چه از کاربر)
    # اگر پیام‌های رسانه‌ای دیگر کاربران هم باید حذف شوند، می‌توانید همه user_media_messages را پاک کنید
    for uid in list(user_media_messages.keys()):
        if uid != user_id:
            for chat_id, message_id in user_media_messages[uid]:
                try:
                    await context.bot.delete_message(chat_id=chat_id, message_id=message_id)
                except Exception:
                    pass
            user_media_messages[uid] = []

# انتخاب دسته بندی برای کاربر
async def choose_category_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # فقط دسته‌هایی که محصول فعال دارند نمایش داده شود
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('SELECT category, COUNT(*) FROM products GROUP BY category HAVING COUNT(*) > 0')
    categories_with_products = [row[0] for row in c.fetchall() if row[0]]
    conn.close()
    if not categories_with_products:
        await update.callback_query.edit_message_text('هیچ دسته‌بندی فعالی وجود ندارد.')
        return
    keyboard = [[InlineKeyboardButton(cat, callback_data=f'user_category_{cat}')] for cat in categories_with_products]
    await update.callback_query.edit_message_text('لطفاً دسته بندی مورد نظر را انتخاب کنید:', reply_markup=InlineKeyboardMarkup(keyboard))

# انتخاب دسته بندی برای ادمین هنگام افزودن محصول
async def choose_category_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [[InlineKeyboardButton(cat, callback_data=f'admin_category_{cat}')] for cat in CATEGORIES]
    await update.callback_query.edit_message_text('لطفاً دسته بندی محصول را انتخاب کنید:', reply_markup=InlineKeyboardMarkup(keyboard))

# بروزرسانی button_handler برای هندل دسته بندی‌ها و افزودن محصول با دسته بندی
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user = query.from_user
    await query.answer()
    if query.data == 'start':
        await start(update, context)
    elif query.data == 'admin_panel':
        if user.username in ADMIN_USERNAMES:
            await admin_panel(update, context, is_query=True)
        else:
            await query.edit_message_text('دسترسی فقط برای ادمین‌ها مجاز است.')
    elif query.data == 'choose_category_user':
        await choose_category_user(update, context)
    elif query.data.startswith('user_category_'):
        category = query.data.replace('user_category_', '')
        await products_by_category(update, context, category)
    elif query.data == 'add_product':
        if user.username in ADMIN_USERNAMES:
            await choose_category_admin(update, context)
    elif query.data.startswith('admin_category_'):
        category = query.data.replace('admin_category_', '')
        admin_states[user.id] = {'step': 'add_product_name', 'category': category}
        await query.edit_message_text(f'نام محصول را وارد کنید برای دسته بندی "{category}":', reply_markup=BACK_BUTTON)
    elif query.data == 'add_admin':
        if user.username in ADMIN_USERNAMES:
            await add_admin_start(update, context)
        else:
            await query.edit_message_text('دسترسی فقط برای ادمین‌ها مجاز است.')
    elif query.data == 'edit_product':
        # نمایش لیست محصولات به صورت دکمه‌های شناور برای انتخاب جهت ویرایش
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute('SELECT id, name, price FROM products')
        products = c.fetchall()
        conn.close()
        if not products:
            await query.edit_message_text('هیچ محصولی برای ویرایش وجود ندارد.', reply_markup=BACK_BUTTON)
            return
        keyboard = [[InlineKeyboardButton(f'{p[1]} | {p[2]} تومان', callback_data=f'edit_product_{p[0]}')] for p in products]
        keyboard.append([InlineKeyboardButton('بازگشت', callback_data='back_to_panel')])
        await query.edit_message_text('محصول مورد نظر برای ویرایش را انتخاب کنید:', reply_markup=InlineKeyboardMarkup(keyboard))
    elif query.data.startswith('edit_product_'):
        product_id = query.data.replace('edit_product_', '')
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute('SELECT id, name, description, price, category, photo FROM products WHERE id=?', (product_id,))
        product = c.fetchone()
        conn.close()
        if not product:
            await query.edit_message_text('محصول مورد نظر یافت نشد.', reply_markup=BACK_BUTTON)
            return
        msg = f'نام: {product[1]}\nقیمت: {product[3]} تومان\nدسته‌بندی: {product[4]}\nتوضیحات: {product[2]}'
        keyboard = [
            [InlineKeyboardButton('ویرایش نام', callback_data=f'edit_name_{product[0]}'), InlineKeyboardButton('ویرایش قیمت', callback_data=f'edit_price_{product[0]}')],
            [InlineKeyboardButton('ویرایش توضیحات', callback_data=f'edit_desc_{product[0]}')],
            [InlineKeyboardButton('حذف محصول', callback_data=f'delete_product_{product[0]}')],
            [InlineKeyboardButton('بازگشت', callback_data='edit_product')]
        ]
        sent = await query.message.reply_photo(product[5], caption=msg, reply_markup=InlineKeyboardMarkup(keyboard))
        user_media_messages.setdefault(user.id, []).append((sent.chat_id, sent.message_id))
        context.application.create_task(delete_message_later(context, sent.chat_id, sent.message_id))
        admin_states[user.id] = {'step': 'edit_product', 'product_id': product[0]}
        await query.delete_message()
    elif query.data.startswith('edit_name_'):
        product_id = query.data.replace('edit_name_', '')
        admin_states[user.id] = {'step': 'edit_name', 'product_id': product_id}
        await query.message.reply_text('نام جدید محصول را وارد کنید:', reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton('بازگشت', callback_data=f'edit_product_{product_id}')]]))
        await query.delete_message()
    elif query.data.startswith('edit_price_'):
        product_id = query.data.replace('edit_price_', '')
        admin_states[user.id] = {'step': 'edit_price', 'product_id': product_id}
        await query.message.reply_text('قیمت جدید محصول را وارد کنید:', reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton('بازگشت', callback_data=f'edit_product_{product_id}')]]))
        await query.delete_message()
    elif query.data.startswith('edit_desc_'):
        product_id = query.data.replace('edit_desc_', '')
        admin_states[user.id] = {'step': 'edit_desc', 'product_id': product_id}
        await query.message.reply_text('توضیحات جدید محصول را وارد کنید:', reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton('بازگشت', callback_data=f'edit_product_{product_id}')]]))
        await query.delete_message()
    elif query.data.startswith('delete_product_'):
        product_id = query.data.replace('delete_product_', '')
        admin_states[user.id] = {'step': 'delete_product', 'product_id': product_id}
        await query.message.reply_text('آیا مطمئن هستید که می‌خواهید این محصول را حذف کنید؟ اگر مطمئن هستید "حذف" را تایپ کنید یا بازگشت را بزنید.', reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton('بازگشت', callback_data=f'edit_product_{product_id}')]]))
        await query.delete_message()
    elif query.data == 'back_to_panel' or query.data == 'edit_product':
        # بازگشت به صفحه اصلی برای همه کاربران
        await start(update, context)

# تعریف توابع مورد نیاز برای هندلرها
async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE, is_query=False):
    user = update.effective_user if not is_query else update.callback_query.from_user
    if user.username not in ADMIN_USERNAMES:
        if is_query:
            await update.callback_query.edit_message_text('دسترسی فقط برای ادمین‌ها مجاز است.')
        else:
            await update.message.reply_text('دسترسی فقط برای ادمین‌ها مجاز است.')
        return
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('SELECT id, name, price FROM products')
    products = c.fetchall()
    conn.close()
    msg = 'پنل مدیریت دینا شاپ\n\nلیست محصولات:\n'
    for p in products:
        msg += f"شناسه: {p[0]} | نام: {p[1]} | قیمت: {p[2]} تومان\n"
    keyboard = [
        [InlineKeyboardButton('افزودن محصول', callback_data='add_product')],
        [InlineKeyboardButton('ویرایش محصول', callback_data='edit_product')],
        [InlineKeyboardButton('افزودن ادمین', callback_data='add_admin')],
        [InlineKeyboardButton('مشاهده محصولات', callback_data='choose_category_user')]
    ]
    if is_query:
        await update.callback_query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(keyboard))
    else:
        await update.message.reply_text(msg, reply_markup=InlineKeyboardMarkup(keyboard))

async def products_by_category(update: Update, context: ContextTypes.DEFAULT_TYPE, category):
    if not category:
        await admin_panel(update, context, is_query=False)
        return
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('SELECT id, name, description, photo, price FROM products WHERE category=?', (category,))
    rows = c.fetchall()
    conn.close()
    if not rows:
        await update.callback_query.edit_message_text('هیچ محصولی در این دسته بندی موجود نیست.')
        return
    user_id = update.effective_user.id
    user_media_messages.setdefault(user_id, [])
    for row in rows:
        caption = f'{row[1]}\nقیمت: {row[4]} تومان\nتوضیحات: {row[2]}'
        sent = await update.callback_query.message.reply_photo(row[3], caption=caption)
        user_media_messages[user_id].append((sent.chat_id, sent.message_id))
        context.application.create_task(delete_message_later(context, sent.chat_id, sent.message_id))
    await update.callback_query.answer()

async def add_admin_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if user.username not in ADMIN_USERNAMES:
        await update.callback_query.edit_message_text('دسترسی فقط برای ادمین‌ها مجاز است.')
        return
    admin_states[user.id] = {'step': 'add_admin'}
    await update.callback_query.edit_message_text('یوزرنیم ادمین جدید را وارد کنید:', reply_markup=BACK_BUTTON)

# Message handler for admin actions (edit name, price, desc, add admin, etc)
async def admin_message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    state = admin_states.get(user.id)
    if not state:
        return
    step = state.get('step')
    if step == 'add_product_name':
        admin_states[user.id]['name'] = update.message.text
        await update.message.reply_text('توضیحات محصول را وارد کنید:', reply_markup=BACK_BUTTON)
        admin_states[user.id]['step'] = 'add_product_desc'
    elif step == 'add_product_desc':
        admin_states[user.id]['description'] = update.message.text
        await update.message.reply_text('قیمت محصول را وارد کنید:', reply_markup=BACK_BUTTON)
        admin_states[user.id]['step'] = 'add_product_price'
    elif step == 'add_product_price':
        try:
            price = int(update.message.text)
        except ValueError:
            await update.message.reply_text('قیمت باید عدد باشد. دوباره وارد کنید:', reply_markup=BACK_BUTTON)
            return
        admin_states[user.id]['price'] = price
        await update.message.reply_text('عکس محصول را ارسال کنید:', reply_markup=BACK_BUTTON)
        admin_states[user.id]['step'] = 'add_product_photo'
    elif step == 'add_product_photo':
        if update.message.photo:
            photo_file_id = update.message.photo[-1].file_id
            s = admin_states[user.id]
            conn = sqlite3.connect(DB_PATH)
            c = conn.cursor()
            c.execute('''INSERT INTO products (name, description, price, category, photo) VALUES (?, ?, ?, ?, ?)''', (s['name'], s['description'], s['price'], s['category'], photo_file_id))
            conn.commit()
            conn.close()
            await update.message.reply_text('محصول با موفقیت افزوده شد.', reply_markup=BACK_BUTTON)
            admin_states.pop(user.id)
        else:
            await update.message.reply_text('لطفاً عکس محصول را ارسال کنید.', reply_markup=BACK_BUTTON)
    elif step == 'edit_name':
        new_name = update.message.text
        product_id = state['product_id']
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute('UPDATE products SET name=? WHERE id=?', (new_name, product_id))
        conn.commit()
        conn.close()
        await update.message.reply_text('نام محصول با موفقیت ویرایش شد.', reply_markup=BACK_BUTTON)
        admin_states.pop(user.id)
        # نمایش مجدد پنل ویرایش محصول
        await show_edit_product_panel(update, context, product_id)
    elif step == 'edit_price':
        try:
            new_price = int(update.message.text)
        except ValueError:
            await update.message.reply_text('قیمت باید عدد باشد. دوباره وارد کنید:', reply_markup=BACK_BUTTON)
            return
        product_id = state['product_id']
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute('UPDATE products SET price=? WHERE id=?', (new_price, product_id))
        conn.commit()
        conn.close()
        await update.message.reply_text('قیمت محصول با موفقیت ویرایش شد.', reply_markup=BACK_BUTTON)
        admin_states.pop(user.id)
        await show_edit_product_panel(update, context, product_id)
    elif step == 'edit_desc':
        new_desc = update.message.text
        product_id = state['product_id']
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute('UPDATE products SET description=? WHERE id=?', (new_desc, product_id))
        conn.commit()
        conn.close()
        await update.message.reply_text('توضیحات محصول با موفقیت ویرایش شد.', reply_markup=BACK_BUTTON)
        admin_states.pop(user.id)
        await show_edit_product_panel(update, context, product_id)
    elif step == 'delete_product':
        if update.message.text.strip() == 'حذف':
            product_id = state['product_id']
            conn = sqlite3.connect(DB_PATH)
            c = conn.cursor()
            c.execute('DELETE FROM products WHERE id=?', (product_id,))
            conn.commit()
            conn.close()
            await update.message.reply_text('محصول با موفقیت حذف شد.', reply_markup=BACK_BUTTON)
            admin_states.pop(user.id)
            # نمایش مجدد لیست محصولات برای ویرایش
            await show_products_for_edit(update, context)
        else:
            await update.message.reply_text('حذف لغو شد.', reply_markup=BACK_BUTTON)
            admin_states.pop(user.id)
            await show_edit_product_panel(update, context, state['product_id'])
    elif step == 'add_admin':
        new_admin = update.message.text.strip().replace('@', '')
        if new_admin and new_admin not in ADMIN_USERNAMES:
            ADMIN_USERNAMES.append(new_admin)
            await update.message.reply_text(f'ادمین جدید {new_admin} اضافه شد.', reply_markup=BACK_BUTTON)
        else:
            await update.message.reply_text('یوزرنیم معتبر وارد کنید یا ادمین قبلاً اضافه شده است.', reply_markup=BACK_BUTTON)
        admin_states.pop(user.id)

# نمایش مجدد پنل ویرایش محصول پس از هر عملیات
async def show_edit_product_panel(update, context, product_id):
    # حذف همه پیام‌های رسانه‌ای قبلی کاربر قبل از ارسال عکس جدید
    await delete_all_user_media(context, update.effective_user.id)
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('SELECT id, name, description, price, category, photo FROM products WHERE id=?', (product_id,))
    product = c.fetchone()
    conn.close()
    if not product:
        await update.message.reply_text('محصول مورد نظر یافت نشد.', reply_markup=BACK_BUTTON)
        return
    msg = f'نام: {product[1]}\nقیمت: {product[3]} تومان\nدسته‌بندی: {product[4]}\nتوضیحات: {product[2]}'
    keyboard = [
        [InlineKeyboardButton('ویرایش نام', callback_data=f'edit_name_{product[0]}'), InlineKeyboardButton('ویرایش قیمت', callback_data=f'edit_price_{product[0]}')],
        [InlineKeyboardButton('ویرایش توضیحات', callback_data=f'edit_desc_{product[0]}')],
        [InlineKeyboardButton('حذف محصول', callback_data=f'delete_product_{product[0]}')],
        [InlineKeyboardButton('بازگشت', callback_data='edit_product')]
    ]
    sent = await update.message.reply_photo(product[5], caption=msg, reply_markup=InlineKeyboardMarkup(keyboard))
    user_media_messages.setdefault(update.effective_user.id, []).append((sent.chat_id, sent.message_id))
    context.application.create_task(delete_message_later(context, sent.chat_id, sent.message_id))

# نمایش مجدد لیست محصولات برای ویرایش
async def show_products_for_edit(update, context):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('SELECT id, name, price FROM products')
    products = c.fetchall()
    conn.close()
    if not products:
        await update.message.reply_text('هیچ محصولی برای ویرایش وجود ندارد.', reply_markup=BACK_BUTTON)
        return
    keyboard = [[InlineKeyboardButton(f'{p[1]} | {p[2]} تومان', callback_data=f'edit_product_{p[0]}')] for p in products]
    keyboard.append([InlineKeyboardButton('بازگشت', callback_data='back_to_panel')])
    await update.message.reply_text('محصول مورد نظر برای ویرایش را انتخاب کنید:', reply_markup=InlineKeyboardMarkup(keyboard))

if __name__ == "__main__":
    logging.info("Bot is starting...")
    application = ApplicationBuilder().token(TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(button_handler))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, admin_message_handler))
    application.run_polling()
    logging.info('Bot started!')