import asyncio
import logging
from datetime import datetime
from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, FSInputFile
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
import sqlite3
import os
from dotenv import load_dotenv

# ============ ЗАГРУЗКА .env ============
load_dotenv()

# ============ ТВОИ ДАННЫЕ ИЗ .env ============
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID"))
OWNER_USERNAME = os.getenv("OWNER_USERNAME")
TON_WALLET = os.getenv("TON_WALLET")
CARD_NUMBER = os.getenv("CARD_NUMBER")
CARD_HOLDER = os.getenv("CARD_HOLDER")
BANK_NAME = os.getenv("BANK_NAME")

BOT_USERNAME = "OrgazmDeals_Bot"
SUPPORT_USERNAME = OWNER_USERNAME
BANNER_PATH = "banner.jpg"

# ============ НАСТРОЙКИ ============
logging.basicConfig(level=logging.INFO)
storage = MemoryStorage()
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=storage)

# Для отслеживания последнего баннера
last_banner = {}

# ============ БАЗА ДАННЫХ ============
def init_db():
    conn = sqlite3.connect('bot_database.db')
    c = conn.cursor()
    
    c.execute('''CREATE TABLE IF NOT EXISTS users
                 (user_id INTEGER PRIMARY KEY, 
                  username TEXT,
                  first_name TEXT,
                  reg_date TEXT,
                  status TEXT DEFAULT 'user')''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS vouch_requests
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  user_id INTEGER,
                  target_username TEXT,
                  amount REAL,
                  currency TEXT,
                  status TEXT DEFAULT 'pending',
                  request_date TEXT,
                  admin_answer TEXT)''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS complaints
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  user_id INTEGER,
                  complaint_text TEXT,
                  status TEXT DEFAULT 'pending',
                  complaint_date TEXT)''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS buy_requests
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  user_id INTEGER,
                  amount REAL,
                  currency TEXT,
                  status TEXT DEFAULT 'pending',
                  request_date TEXT)''')
    
    conn.commit()
    conn.close()

init_db()

# ============ СОСТОЯНИЯ ============
class VouchStates(StatesGroup):
    waiting_for_target = State()
    waiting_for_amount = State()
    waiting_for_currency = State()

class ComplaintStates(StatesGroup):
    waiting_for_complaint = State()

class BuyVouchStates(StatesGroup):
    waiting_for_amount = State()
    waiting_for_currency = State()

# ============ ФУНКЦИЯ ОТПРАВКИ С БАННЕРОМ ============
async def send_with_banner(chat_id: int, text: str, keyboard=None):
    try:
        if chat_id in last_banner:
            try:
                await bot.delete_message(chat_id, last_banner[chat_id])
            except:
                pass
        
        if os.path.exists(BANNER_PATH):
            photo = FSInputFile(BANNER_PATH)
            msg = await bot.send_photo(chat_id, photo)
            last_banner[chat_id] = msg.message_id
        
        await bot.send_message(chat_id, text, reply_markup=keyboard, parse_mode="HTML")
    except Exception as e:
        print(f"Ошибка: {e}")
        await bot.send_message(chat_id, text, reply_markup=keyboard, parse_mode="HTML")

# ============ ФУНКЦИЯ СОЗДАНИЯ ЖИРНЫХ КНОПОК ============
def create_bold_button(text: str, callback_data: str):
    """Создает кнопку с жирным текстом"""
    return InlineKeyboardButton(text=f"<b>{text}</b>", callback_data=callback_data)

# ============ ГЛАВНОЕ МЕНЮ ============
async def show_main_menu(chat_id: int, user_id: int = None):
    """Показывает главное меню с полным описанием"""
    menu_text = (
        "👋 <b>Приветствую!</b>\n\n"
        "Это <b>единственный официальный проект ручений</b>\n"
        "от <b>@orgazm</b>\n\n"
        "‼️ <b>НЕ ВЕДИТЕСЬ НА ФЕЙКОВ!</b>\n"
        "✅ <b>Официальный бот — @OrgazmDeals_Bot</b>\n\n"
        "👇 <b>Выберите действие:</b>"
    )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [create_bold_button("❓ Уточнить ручение", "vouch_check")],
        [create_bold_button("⚠️ Подать жалобу", "complaint")],
        [create_bold_button("💼 Купить ручение", "buy_vouch")],
        [create_bold_button("ℹ️ Информация", "info")]
    ])
    
    await send_with_banner(chat_id, menu_text, keyboard)

# ============ КОМАНДЫ ============
@dp.message(Command("start"))
async def cmd_start(message: Message):
    user_id = message.from_user.id
    username = message.from_user.username or "нет юзернейма"
    first_name = message.from_user.first_name or "Пользователь"
    
    conn = sqlite3.connect('bot_database.db')
    c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO users (user_id, username, first_name, reg_date) VALUES (?, ?, ?, ?)",
              (user_id, username, first_name, datetime.now().strftime("%d.%m.%Y %H:%M")))
    conn.commit()
    conn.close()
    
    await show_main_menu(message.chat.id, user_id)

@dp.message(Command("admin"))
async def cmd_admin(message: Message):
    if message.from_user.id != ADMIN_ID:
        await message.answer("❌ <b>У тебя нет доступа к админке</b>", parse_mode="HTML")
        return
    
    conn = sqlite3.connect('bot_database.db')
    c = conn.cursor()
    
    c.execute("SELECT COUNT(*) FROM users")
    users_count = c.fetchone()[0]
    
    c.execute("SELECT COUNT(*) FROM vouch_requests WHERE status='pending'")
    pending_vouches = c.fetchone()[0]
    
    c.execute("SELECT COUNT(*) FROM complaints WHERE status='pending'")
    pending_complaints = c.fetchone()[0]
    
    c.execute("SELECT COUNT(*) FROM buy_requests WHERE status='pending'")
    pending_buys = c.fetchone()[0]
    
    conn.close()
    
    admin_text = (
        "👑 <b>Админ-панель</b>\n\n"
        f"📊 <b>Статистика:</b>\n"
        f"👥 <b>Пользователей:</b> {users_count}\n"
        f"⏳ <b>Ожидают ручения:</b> {pending_vouches}\n"
        f"⚠️ <b>Жалоб:</b> {pending_complaints}\n"
        f"💰 <b>Заявок на покупку:</b> {pending_buys}\n\n"
        f"📋 <b>Команды:</b>\n"
        f"<b>/pending_vouches</b> - заявки на ручение\n"
        f"<b>/pending_complaints</b> - жалобы\n"
        f"<b>/pending_buys</b> - заявки на покупку\n"
        f"<b>/setbanner</b> - установить баннер\n"
        f"<b>/removebanner</b> - удалить баннер"
    )
    
    await message.answer(admin_text, parse_mode="HTML")

# ============ УПРАВЛЕНИЕ БАННЕРОМ ============
@dp.message(Command("setbanner"))
async def set_banner(message: Message):
    if message.from_user.id != ADMIN_ID:
        await message.answer("❌ <b>Нет доступа</b>", parse_mode="HTML")
        return
    await message.answer("📸 <b>Отправьте фото для баннера</b>", parse_mode="HTML")

@dp.message(F.photo)
async def save_banner(message: Message):
    if message.from_user.id != ADMIN_ID:
        return
    try:
        file_id = message.photo[-1].file_id
        file = await bot.get_file(file_id)
        await bot.download_file(file.file_path, BANNER_PATH)
        await message.answer("✅ <b>Баннер установлен!</b>", parse_mode="HTML")
    except Exception as e:
        await message.answer(f"❌ <b>Ошибка:</b> {e}", parse_mode="HTML")

@dp.message(Command("removebanner"))
async def remove_banner(message: Message):
    if message.from_user.id != ADMIN_ID:
        await message.answer("❌ <b>Нет доступа</b>", parse_mode="HTML")
        return
    try:
        if os.path.exists(BANNER_PATH):
            os.remove(BANNER_PATH)
            await message.answer("✅ <b>Баннер удален</b>", parse_mode="HTML")
        else:
            await message.answer("❌ <b>Баннер не найден</b>", parse_mode="HTML")
    except Exception as e:
        await message.answer(f"❌ <b>Ошибка:</b> {e}", parse_mode="HTML")

# ============ УТОЧНИТЬ РУЧЕНИЕ ============
@dp.callback_query(F.data == "vouch_check")
async def vouch_check(call: CallbackQuery, state: FSMContext):
    await call.message.delete()
    
    text = (
        "❓ <b>Уточнение ручения</b>\n\n"
        "<b>Введите @юзернейм человека:</b>\n"
        "👉 Например: @durov"
    )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [create_bold_button("🔙 Назад в меню", "back_to_menu")]
    ])
    
    await bot.send_message(call.from_user.id, text, reply_markup=keyboard, parse_mode="HTML")
    await state.set_state(VouchStates.waiting_for_target)
    await call.answer()

@dp.message(VouchStates.waiting_for_target)
async def process_target(message: Message, state: FSMContext):
    target = message.text.strip()
    if not target.startswith('@'):
        target = '@' + target
    
    await state.update_data(target=target)
    
    text = (
        "💰 <b>Введите сумму сделки:</b>\n"
        "👉 <b>Только цифры</b>, например: 500"
    )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [create_bold_button("🔙 Назад в меню", "back_to_menu")]
    ])
    
    await message.answer(text, reply_markup=keyboard, parse_mode="HTML")
    await state.set_state(VouchStates.waiting_for_amount)

@dp.message(VouchStates.waiting_for_amount)
async def process_amount(message: Message, state: FSMContext):
    try:
        amount = float(message.text.strip())
        await state.update_data(amount=amount)
        
        text = (
            "💱 <b>Введите валюту:</b>\n"
            "👉 Например: <b>$, ₽, €, грн, тенге</b>"
        )
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [create_bold_button("🔙 Назад в меню", "back_to_menu")]
        ])
        
        await message.answer(text, reply_markup=keyboard, parse_mode="HTML")
        await state.set_state(VouchStates.waiting_for_currency)
    except ValueError:
        await message.answer("❌ <b>Введите число (только цифры)</b>", parse_mode="HTML")

@dp.message(VouchStates.waiting_for_currency)
async def process_currency(message: Message, state: FSMContext):
    currency = message.text.strip()
    data = await state.get_data()
    target = data['target']
    amount = data['amount']
    user_id = message.from_user.id
    username = message.from_user.username or "нет юзернейма"
    
    # Сохраняем в БД
    conn = sqlite3.connect('bot_database.db')
    c = conn.cursor()
    c.execute('''INSERT INTO vouch_requests 
                 (user_id, target_username, amount, currency, request_date) 
                 VALUES (?, ?, ?, ?, ?)''',
              (user_id, target, amount, currency, datetime.now().strftime("%d.%m.%Y %H:%M")))
    request_id = c.lastrowid
    conn.commit()
    conn.close()
    
    # Отправляем админу
    admin_text = (
        f"🔔 <b>НОВЫЙ ЗАПРОС НА РУЧЕНИЕ</b> #{request_id}\n\n"
        f"👤 <b>От:</b> @{username} (ID: {user_id})\n"
        f"🎯 <b>Проверить:</b> {target}\n"
        f"💰 <b>Сумма:</b> {amount} {currency}\n"
        f"📅 <b>Время:</b> {datetime.now().strftime('%d.%m.%Y %H:%M')}\n\n"
        f"<b>Чтобы ответить:</b>\n"
        f"<b>/answer_vouch {request_id} да/нет</b>"
    )
    
    await bot.send_message(ADMIN_ID, admin_text, parse_mode="HTML")
    
    await message.answer(
        f"✅ <b>Запрос отправлен!</b>\n\n"
        f"📋 <b>Детали:</b>\n"
        f"• <b>Человек:</b> {target}\n"
        f"• <b>Сумма:</b> {amount} {currency}\n\n"
        f"⏳ <b>Ожидайте ответа от @{OWNER_USERNAME}</b>",
        parse_mode="HTML"
    )
    
    await state.clear()
    await show_main_menu(message.chat.id, user_id)

# ============ ПОДАТЬ ЖАЛОБУ ============
@dp.callback_query(F.data == "complaint")
async def complaint(call: CallbackQuery, state: FSMContext):
    await call.message.delete()
    
    text = (
        "⚠️ <b>Подача жалобы</b>\n\n"
        "📝 <b>Опишите ситуацию подробно:</b>\n"
        "• <b>Кто обманул</b> (@юзернейм)\n"
        "• <b>На какую сумму</b>\n"
        "• <b>Что обещали и что получили</b>\n"
        "• <b>Ссылки на скриншоты</b>\n\n"
        "📨 <b>Я передам @orgazm для рассмотрения.</b>"
    )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [create_bold_button("🔙 Назад в меню", "back_to_menu")]
    ])
    
    await bot.send_message(call.from_user.id, text, reply_markup=keyboard, parse_mode="HTML")
    await state.set_state(ComplaintStates.waiting_for_complaint)
    await call.answer()

@dp.message(ComplaintStates.waiting_for_complaint)
async def process_complaint(message: Message, state: FSMContext):
    complaint_text = message.text
    user_id = message.from_user.id
    username = message.from_user.username or "нет юзернейма"
    
    # Сохраняем в БД
    conn = sqlite3.connect('bot_database.db')
    c = conn.cursor()
    c.execute('''INSERT INTO complaints 
                 (user_id, complaint_text, complaint_date) 
                 VALUES (?, ?, ?)''',
              (user_id, complaint_text, datetime.now().strftime("%d.%m.%Y %H:%M")))
    complaint_id = c.lastrowid
    conn.commit()
    conn.close()
    
    # Отправляем админу
    admin_text = (
        f"⚠️ <b>НОВАЯ ЖАЛОБА</b> #{complaint_id}\n\n"
        f"👤 <b>От:</b> @{username} (ID: {user_id})\n"
        f"📝 <b>Текст:</b>\n{complaint_text}\n\n"
        f"📅 <b>Время:</b> {datetime.now().strftime('%d.%m.%Y %H:%M')}"
    )
    
    await bot.send_message(ADMIN_ID, admin_text, parse_mode="HTML")
    
    await message.answer(
        f"✅ <b>Жалоба отправлена!</b>\n\n"
        f"📨 <b>@{OWNER_USERNAME} рассмотрит её в ближайшее время.</b>\n\n"
        f"⚠️ <b>Важно:</b> Если обман подтвердится — вам <b>ВОЗМЕСТЯТ полную сумму!</b>",
        parse_mode="HTML"
    )
    
    await state.clear()
    await show_main_menu(message.chat.id, user_id)

# ============ КУПИТЬ РУЧЕНИЕ ============
@dp.callback_query(F.data == "buy_vouch")
async def buy_vouch(call: CallbackQuery, state: FSMContext):
    await call.message.delete()
    
    text = (
        "💼 <b>Покупка ручения</b>\n\n"
        "💰 <b>Введите сумму</b>, которую хотите внести:\n"
        "👉 <b>Только цифры</b>, например: 1000"
    )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [create_bold_button("🔙 Назад в меню", "back_to_menu")]
    ])
    
    await bot.send_message(call.from_user.id, text, reply_markup=keyboard, parse_mode="HTML")
    await state.set_state(BuyVouchStates.waiting_for_amount)
    await call.answer()

@dp.message(BuyVouchStates.waiting_for_amount)
async def buy_amount(message: Message, state: FSMContext):
    try:
        amount = float(message.text.strip())
        if amount < 100:
            await message.answer("❌ <b>Минимальная сумма - 100</b>", parse_mode="HTML")
            return
        
        await state.update_data(amount=amount)
        
        text = (
            "💱 <b>Введите валюту:</b>\n"
            "👉 Например: <b>$, ₽, €, грн, тенге, TON</b>"
        )
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [create_bold_button("🔙 Назад в меню", "back_to_menu")]
        ])
        
        await message.answer(text, reply_markup=keyboard, parse_mode="HTML")
        await state.set_state(BuyVouchStates.waiting_for_currency)
    except ValueError:
        await message.answer("❌ <b>Введите число (только цифры)</b>", parse_mode="HTML")

@dp.message(BuyVouchStates.waiting_for_currency)
async def buy_currency(message: Message, state: FSMContext):
    currency = message.text.strip()
    data = await state.get_data()
    amount = data['amount']
    user_id = message.from_user.id
    username = message.from_user.username or "нет юзернейма"
    
    # Сохраняем в БД
    conn = sqlite3.connect('bot_database.db')
    c = conn.cursor()
    c.execute('''INSERT INTO buy_requests 
                 (user_id, amount, currency, request_date) 
                 VALUES (?, ?, ?, ?)''',
              (user_id, amount, currency, datetime.now().strftime("%d.%m.%Y %H:%M")))
    request_id = c.lastrowid
    conn.commit()
    conn.close()
    
    # Отправляем админу
    admin_text = (
        f"💰 <b>ЗАЯВКА НА ПОКУПКУ РУЧЕНИЯ</b> #{request_id}\n\n"
        f"👤 <b>От:</b> @{username} (ID: {user_id})\n"
        f"💰 <b>Сумма:</b> {amount} {currency}\n"
        f"📅 <b>Время:</b> {datetime.now().strftime('%d.%m.%Y %H:%M')}"
    )
    
    await bot.send_message(ADMIN_ID, admin_text, parse_mode="HTML")
    
    await message.answer(
        f"✅ <b>Заявка принята!</b>\n\n"
        f"💰 <b>Сумма:</b> {amount} {currency}\n\n"
        f"📨 <b>Свяжитесь со мной в личные сообщения:</b>\n"
        f"👉 <b>@{OWNER_USERNAME}</b>\n\n"
        f"<b>Я рассмотрю вашу заявку и отвечу на все вопросы.</b>",
        parse_mode="HTML"
    )
    
    await state.clear()
    await show_main_menu(message.chat.id, user_id)

# ============ ИНФОРМАЦИЯ ============
@dp.callback_query(F.data == "info")
async def info(call: CallbackQuery):
    await call.message.delete()
    
    info_text = (
        "ℹ️ <b>О боте</b>\n\n"
        "🤝 <b>Это единственный официальный проект ручений</b>\n"
        "от <b>@orgazm</b>\n\n"
        "❓ <b>Как уточнить ручение?</b>\n"
        "1️⃣ <b>Нажмите кнопку «Уточнить ручение»</b>\n"
        "2️⃣ <b>Введите @юзернейм человека</b>\n"
        "3️⃣ <b>Введите сумму сделки</b>\n"
        "4️⃣ <b>Введите валюту</b>\n"
        "5️⃣ <b>Ожидайте ответа от @orgazm</b>\n\n"
        "✅ <b>Если я РУЧНУСЬ</b> — человек надёжный, можете смело проводить сделку!\n\n"
        "❌ <b>Если обманули:</b>\n"
        "• <b>Напишите мне в ЛС @orgazm</b>\n"
        "• <b>Приложите ВСЕ доказательства</b>\n"
        "• <b>Я сниму ручение с мошенника</b>\n"
        "• <b>ВОЗМЕЩУ вам полную сумму!</b>\n\n"
        "‼️ <b>Остерегайтесь фейков!</b>\n"
        "✅ <b>Официальный бот — @OrgazmDeals_Bot</b>"
    )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [create_bold_button("🔙 Назад в меню", "back_to_menu")]
    ])
    
    await bot.send_message(call.from_user.id, info_text, reply_markup=keyboard, parse_mode="HTML")
    await call.answer()

# ============ НАЗАД В МЕНЮ ============
@dp.callback_query(F.data == "back_to_menu")
async def back_to_menu(call: CallbackQuery, state: FSMContext):
    await state.clear()
    await call.message.delete()
    await show_main_menu(call.from_user.id, call.from_user.id)

# ============ АДМИН КОМАНДЫ ============
@dp.message(Command("pending_vouches"))
async def pending_vouches(message: Message):
    if message.from_user.id != ADMIN_ID:
        return
    
    conn = sqlite3.connect('bot_database.db')
    c = conn.cursor()
    c.execute('''SELECT * FROM vouch_requests WHERE status="pending" ORDER BY id DESC''')
    requests = c.fetchall()
    conn.close()
    
    if not requests:
        await message.answer("✅ <b>Нет ожидающих заявок на ручение</b>", parse_mode="HTML")
        return
    
    text = "⏳ <b>Ожидающие заявки на ручение:</b>\n\n"
    for req in requests:
        text += f"<b>#{req[0]}</b> | От @{req[2]} | <b>{req[3]} {req[4]}</b> | {req[5]}\n"
        text += f"<b>Ответ:</b> /answer_vouch {req[0]} да/нет\n\n"
    
    await message.answer(text, parse_mode="HTML")

@dp.message(Command("answer_vouch"))
async def answer_vouch(message: Message):
    if message.from_user.id != ADMIN_ID:
        return
    
    try:
        parts = message.text.split()
        request_id = int(parts[1])
        answer = parts[2].lower()
        
        conn = sqlite3.connect('bot_database.db')
        c = conn.cursor()
        c.execute('''SELECT user_id, target_username, amount, currency FROM vouch_requests WHERE id=?''', (request_id,))
        req = c.fetchone()
        
        if not req:
            await message.answer("❌ <b>Заявка не найдена</b>", parse_mode="HTML")
            return
        
        user_id, target, amount, currency = req
        
        if answer in ['да', 'yes']:
            result_text = (
                f"✅ <b>РУЧАЮСЬ!</b>\n\n"
                f"<b>@{OWNER_USERNAME} подтверждает надёжность</b> @{target}\n"
                f"💰 <b>Сумма:</b> {amount} {currency}\n\n"
                f"<b>Можете смело проводить сделку!</b>"
            )
            new_status = "approved"
        else:
            result_text = (
                f"❌ <b>НЕ РУЧАЮСЬ</b>\n\n"
                f"<b>@{OWNER_USERNAME} НЕ подтверждает надёжность</b> @{target}\n\n"
                f"<b>Будьте осторожны!</b>"
            )
            new_status = "rejected"
        
        c.execute('''UPDATE vouch_requests SET status=?, admin_answer=? WHERE id=?''',
                  (new_status, result_text, request_id))
        conn.commit()
        
        await bot.send_message(user_id, result_text, parse_mode="HTML")
        
        conn.close()
        await message.answer("✅ <b>Ответ отправлен пользователю</b>", parse_mode="HTML")
        
    except Exception as e:
        await message.answer(f"❌ <b>Ошибка:</b> {e}. Используй: <b>/answer_vouch ID да/нет</b>", parse_mode="HTML")

@dp.message(Command("pending_complaints"))
async def pending_complaints(message: Message):
    if message.from_user.id != ADMIN_ID:
        return
    
    conn = sqlite3.connect('bot_database.db')
    c = conn.cursor()
    c.execute('''SELECT * FROM complaints WHERE status="pending" ORDER BY id DESC''')
    complaints = c.fetchall()
    conn.close()
    
    if not complaints:
        await message.answer("✅ <b>Нет ожидающих жалоб</b>", parse_mode="HTML")
        return
    
    text = "⚠️ <b>Ожидающие жалобы:</b>\n\n"
    for comp in complaints:
        text += f"<b>#{comp[0]}</b> | От ID {comp[1]} | {comp[4]}\n"
        text += f"📝 {comp[2][:100]}...\n\n"
    
    await message.answer(text, parse_mode="HTML")

@dp.message(Command("pending_buys"))
async def pending_buys(message: Message):
    if message.from_user.id != ADMIN_ID:
        return
    
    conn = sqlite3.connect('bot_database.db')
    c = conn.cursor()
    c.execute('''SELECT * FROM buy_requests WHERE status="pending" ORDER BY id DESC''')
    buys = c.fetchall()
    conn.close()
    
    if not buys:
        await message.answer("✅ <b>Нет ожидающих заявок на покупку</b>", parse_mode="HTML")
        return
    
    text = "💰 <b>Ожидающие заявки на покупку ручения:</b>\n\n"
    for buy in buys:
        text += f"<b>#{buy[0]}</b> | От ID {buy[1]} | <b>{buy[2]} {buy[3]}</b> | {buy[4]}\n"
    
    await message.answer(text, parse_mode="HTML")

# ============ ЗАПУСК ============
async def main():
    print("🤖 Бот запущен!")
    print(f"👑 Админ: @{OWNER_USERNAME}")
    print(f"📱 Бот: @{BOT_USERNAME}")
    print(f"🖼️ Баннер: {'есть' if os.path.exists(BANNER_PATH) else 'нет'}")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
