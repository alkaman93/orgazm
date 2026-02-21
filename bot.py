import asyncio
import logging
import re
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
                  admin_answer TEXT,
                  admin_response_text TEXT)''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS complaints
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  user_id INTEGER,
                  complaint_text TEXT,
                  status TEXT DEFAULT 'pending',
                  complaint_date TEXT,
                  admin_response_text TEXT)''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS buy_requests
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  user_id INTEGER,
                  amount REAL,
                  currency TEXT,
                  status TEXT DEFAULT 'pending',
                  request_date TEXT,
                  admin_response_text TEXT)''')
    
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
        [InlineKeyboardButton(text="❓ Уточнить ручение", callback_data="vouch_check")],
        [InlineKeyboardButton(text="⚠️ Подать жалобу", callback_data="complaint")],
        [InlineKeyboardButton(text="💼 Купить ручение", callback_data="buy_vouch")],
        [InlineKeyboardButton(text="ℹ️ Информация", callback_data="info")]
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
        f"<b>/pending</b> - все ожидающие заявки\n"
        f"<b>/заявка № текст</b> - ответить на заявку\n"
        f"<b>/setbanner</b> - установить баннер\n"
        f"<b>/removebanner</b> - удалить баннер\n\n"
        f"💡 <b>Пример ответа:</b>\n"
        f"/заявка 5 ✅ Ручаюсь, человек надёжный!\n"
        f"/заявка 12 ❌ Не ручаюсь, были проблемы"
    )
    
    await message.answer(admin_text, parse_mode="HTML")

# ============ КОМАНДА ДЛЯ ПРОСМОТРА ВСЕХ ЗАЯВОК ============
@dp.message(Command("pending"))
async def cmd_pending(message: Message):
    if message.from_user.id != ADMIN_ID:
        return
    
    conn = sqlite3.connect('bot_database.db')
    c = conn.cursor()
    
    # Заявки на ручение
    c.execute('''SELECT id, user_id, target_username, amount, currency, request_date 
                 FROM vouch_requests WHERE status="pending" ORDER BY id''')
    vouches = c.fetchall()
    
    # Жалобы
    c.execute('''SELECT id, user_id, complaint_text, complaint_date 
                 FROM complaints WHERE status="pending" ORDER BY id''')
    complaints = c.fetchall()
    
    # Заявки на покупку
    c.execute('''SELECT id, user_id, amount, currency, request_date 
                 FROM buy_requests WHERE status="pending" ORDER BY id''')
    buys = c.fetchall()
    
    conn.close()
    
    if not vouches and not complaints and not buys:
        await message.answer("✅ <b>Нет ожидающих заявок</b>", parse_mode="HTML")
        return
    
    text = "📋 <b>ОЖИДАЮЩИЕ ЗАЯВКИ</b>\n"
    text += "═══════════════════\n\n"
    
    if vouches:
        text += "🔔 <b>Ручения:</b>\n"
        for v in vouches:
            text += f"<code>┌─ #ЗАЯВКА {v[0]}</code>\n"
            text += f"<code>├─ От: @{v[2]}</code>\n"
            text += f"<code>├─ Сумма: {v[3]} {v[4]}</code>\n"
            text += f"<code>└─ Дата: {v[5]}</code>\n\n"
    
    if complaints:
        text += "⚠️ <b>Жалобы:</b>\n"
        for c in complaints:
            short_text = c[2][:50] + "..." if len(c[2]) > 50 else c[2]
            text += f"<code>┌─ #ЖАЛОБА {c[0]}</code>\n"
            text += f"<code>├─ {short_text}</code>\n"
            text += f"<code>└─ Дата: {c[3]}</code>\n\n"
    
    if buys:
        text += "💰 <b>Покупки ручения:</b>\n"
        for b in buys:
            text += f"<code>┌─ #ЗАЯВКА {b[0]}</code>\n"
            text += f"<code>├─ Сумма: {b[2]} {b[3]}</code>\n"
            text += f"<code>└─ Дата: {b[4]}</code>\n\n"
    
    text += "═══════════════════\n"
    text += "💡 <b>Как ответить:</b>\n"
    text += "<code>/заявка 5 ✅ Ручаюсь!</code>\n"
    text += "<code>/жалоба 3 ❌ Отклонено</code>\n"
    text += "<code>/покупка 2 ✅ Оплачено</code>"
    
    await message.answer(text, parse_mode="HTML")

# ============ КОМАНДА ДЛЯ ОТВЕТА НА ЗАЯВКИ ============
@dp.message(Command("заявка"))
async def cmd_answer_vouch(message: Message):
    if message.from_user.id != ADMIN_ID:
        return
    
    try:
        # Парсим команду: /заявка 5 Текст ответа
        text = message.text.replace("/заявка", "").strip()
        match = re.match(r"^(\d+)\s+(.+)$", text)
        
        if not match:
            await message.answer(
                "❌ <b>Неверный формат!</b>\n"
                "Используй: <code>/заявка НОМЕР ТЕКСТ</code>\n"
                "Пример: <code>/заявка 5 ✅ Ручаюсь, человек надёжный!</code>",
                parse_mode="HTML"
            )
            return
        
        request_id = int(match.group(1))
        response_text = match.group(2)
        
        conn = sqlite3.connect('bot_database.db')
        c = conn.cursor()
        
        # Ищем заявку
        c.execute('''SELECT user_id, target_username, amount, currency 
                     FROM vouch_requests WHERE id=? AND status="pending"''', (request_id,))
        request = c.fetchone()
        
        if not request:
            await message.answer(f"❌ <b>Заявка #{request_id} не найдена или уже обработана</b>", parse_mode="HTML")
            conn.close()
            return
        
        user_id, target, amount, currency = request
        
        # Обновляем статус
        c.execute('''UPDATE vouch_requests 
                     SET status="answered", admin_response_text=?, admin_answer=?
                     WHERE id=?''', 
                  (response_text, response_text, request_id))
        conn.commit()
        conn.close()
        
        # Отправляем ответ пользователю
        user_text = (
            f"📬 <b>Ответ на ваш запрос о ручении</b>\n\n"
            f"<code>┌─ ЗАЯВКА #{request_id}</code>\n"
            f"<code>├─ Проверяли: {target}</code>\n"
            f"<code>├─ Сумма: {amount} {currency}</code>\n"
            f"<code>└─ Время: {datetime.now().strftime('%d.%m.%Y %H:%M')}</code>\n\n"
            f"<b>Ответ от @{OWNER_USERNAME}:</b>\n"
            f"{response_text}"
        )
        
        await bot.send_message(user_id, user_text, parse_mode="HTML")
        
        await message.answer(
            f"✅ <b>Ответ на заявку #{request_id} отправлен!</b>\n\n"
            f"<b>Текст ответа:</b>\n{response_text}",
            parse_mode="HTML"
        )
        
    except Exception as e:
        await message.answer(f"❌ <b>Ошибка:</b> {e}", parse_mode="HTML")

# ============ КОМАНДА ДЛЯ ОТВЕТА НА ЖАЛОБЫ ============
@dp.message(Command("жалоба"))
async def cmd_answer_complaint(message: Message):
    if message.from_user.id != ADMIN_ID:
        return
    
    try:
        text = message.text.replace("/жалоба", "").strip()
        match = re.match(r"^(\d+)\s+(.+)$", text)
        
        if not match:
            await message.answer(
                "❌ <b>Неверный формат!</b>\n"
                "Используй: <code>/жалоба НОМЕР ТЕКСТ</code>",
                parse_mode="HTML"
            )
            return
        
        complaint_id = int(match.group(1))
        response_text = match.group(2)
        
        conn = sqlite3.connect('bot_database.db')
        c = conn.cursor()
        
        c.execute('''SELECT user_id, complaint_text 
                     FROM complaints WHERE id=? AND status="pending"''', (complaint_id,))
        complaint = c.fetchone()
        
        if not complaint:
            await message.answer(f"❌ <b>Жалоба #{complaint_id} не найдена или уже обработана</b>", parse_mode="HTML")
            conn.close()
            return
        
        user_id, complaint_text = complaint
        
        c.execute('''UPDATE complaints 
                     SET status="answered", admin_response_text=?
                     WHERE id=?''', (response_text, complaint_id))
        conn.commit()
        conn.close()
        
        user_text = (
            f"📬 <b>Ответ на вашу жалобу</b>\n\n"
            f"<code>┌─ ЖАЛОБА #{complaint_id}</code>\n"
            f"<code>└─ Время: {datetime.now().strftime('%d.%m.%Y %H:%M')}</code>\n\n"
            f"<b>Ответ от @{OWNER_USERNAME}:</b>\n"
            f"{response_text}"
        )
        
        await bot.send_message(user_id, user_text, parse_mode="HTML")
        
        await message.answer(
            f"✅ <b>Ответ на жалобу #{complaint_id} отправлен!</b>\n\n"
            f"<b>Текст ответа:</b>\n{response_text}",
            parse_mode="HTML"
        )
        
    except Exception as e:
        await message.answer(f"❌ <b>Ошибка:</b> {e}", parse_mode="HTML")

# ============ КОМАНДА ДЛЯ ОТВЕТА НА ПОКУПКИ ============
@dp.message(Command("покупка"))
async def cmd_answer_buy(message: Message):
    if message.from_user.id != ADMIN_ID:
        return
    
    try:
        text = message.text.replace("/покупка", "").strip()
        match = re.match(r"^(\d+)\s+(.+)$", text)
        
        if not match:
            await message.answer(
                "❌ <b>Неверный формат!</b>\n"
                "Используй: <code>/покупка НОМЕР ТЕКСТ</code>",
                parse_mode="HTML"
            )
            return
        
        request_id = int(match.group(1))
        response_text = match.group(2)
        
        conn = sqlite3.connect('bot_database.db')
        c = conn.cursor()
        
        c.execute('''SELECT user_id, amount, currency 
                     FROM buy_requests WHERE id=? AND status="pending"''', (request_id,))
        request = c.fetchone()
        
        if not request:
            await message.answer(f"❌ <b>Заявка #{request_id} не найдена или уже обработана</b>", parse_mode="HTML")
            conn.close()
            return
        
        user_id, amount, currency = request
        
        c.execute('''UPDATE buy_requests 
                     SET status="answered", admin_response_text=?
                     WHERE id=?''', (response_text, request_id))
        conn.commit()
        conn.close()
        
        user_text = (
            f"📬 <b>Ответ на заявку о покупке ручения</b>\n\n"
            f"<code>┌─ ЗАЯВКА #{request_id}</code>\n"
            f"<code>├─ Сумма: {amount} {currency}</code>\n"
            f"<code>└─ Время: {datetime.now().strftime('%d.%m.%Y %H:%M')}</code>\n\n"
            f"<b>Ответ от @{OWNER_USERNAME}:</b>\n"
            f"{response_text}"
        )
        
        await bot.send_message(user_id, user_text, parse_mode="HTML")
        
        await message.answer(
            f"✅ <b>Ответ на заявку #{request_id} отправлен!</b>\n\n"
            f"<b>Текст ответа:</b>\n{response_text}",
            parse_mode="HTML"
        )
        
    except Exception as e:
        await message.answer(f"❌ <b>Ошибка:</b> {e}", parse_mode="HTML")

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
        [InlineKeyboardButton(text="🔙 Назад в меню", callback_data="back_to_menu")]
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
        [InlineKeyboardButton(text="🔙 Назад в меню", callback_data="back_to_menu")]
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
            [InlineKeyboardButton(text="🔙 Назад в меню", callback_data="back_to_menu")]
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
        f"🔔 <b>НОВАЯ ЗАЯВКА НА РУЧЕНИЕ</b>\n\n"
        f"<code>┌─ #ЗАЯВКА {request_id}</code>\n"
        f"<code>├─ От: @{username}</code>\n"
        f"<code>├─ Проверить: {target}</code>\n"
        f"<code>├─ Сумма: {amount} {currency}</code>\n"
        f"<code>└─ Время: {datetime.now().strftime('%d.%m.%Y %H:%M')}</code>\n\n"
        f"<b>Чтобы ответить:</b>\n"
        f"<code>/заявка {request_id} ТЕКСТ ОТВЕТА</code>"
    )
    
    await bot.send_message(ADMIN_ID, admin_text, parse_mode="HTML")
    
    await message.answer(
        f"✅ <b>Запрос отправлен!</b>\n\n"
        f"📋 <b>Детали:</b>\n"
        f"<code>┌─ ЗАЯВКА #{request_id}</code>\n"
        f"<code>├─ Человек: {target}</code>\n"
        f"<code>├─ Сумма: {amount} {currency}</code>\n"
        f"<code>└─ Статус: Ожидает ответа</code>\n\n"
        f"⏳ <b>Ожидайте ответа от @{OWNER_USERNAME}</b>",
        parse_mode="HTML"
    )
    
    await state.clear()

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
        [InlineKeyboardButton(text="🔙 Назад в меню", callback_data="back_to_menu")]
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
        f"⚠️ <b>НОВАЯ ЖАЛОБА</b>\n\n"
        f"<code>┌─ #ЖАЛОБА {complaint_id}</code>\n"
        f"<code>├─ От: @{username}</code>\n"
        f"<code>├─ Текст: {complaint_text[:100]}...</code>\n"
        f"<code>└─ Время: {datetime.now().strftime('%d.%m.%Y %H:%M')}</code>\n\n"
        f"<b>Чтобы ответить:</b>\n"
        f"<code>/жалоба {complaint_id} ТЕКСТ ОТВЕТА</code>"
    )
    
    await bot.send_message(ADMIN_ID, admin_text, parse_mode="HTML")
    
    await message.answer(
        f"✅ <b>Жалоба отправлена!</b>\n\n"
        f"<code>┌─ ЖАЛОБА #{complaint_id}</code>\n"
        f"<code>└─ Статус: Рассматривается</code>\n\n"
        f"📨 <b>@{OWNER_USERNAME} ответит в ближайшее время.</b>",
        parse_mode="HTML"
    )
    
    await state.clear()

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
        [InlineKeyboardButton(text="🔙 Назад в меню", callback_data="back_to_menu")]
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
            [InlineKeyboardButton(text="🔙 Назад в меню", callback_data="back_to_menu")]
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
        f"💰 <b>НОВАЯ ЗАЯВКА НА ПОКУПКУ РУЧЕНИЯ</b>\n\n"
        f"<code>┌─ #ЗАЯВКА {request_id}</code>\n"
        f"<code>├─ От: @{username}</code>\n"
        f"<code>├─ Сумма: {amount} {currency}</code>\n"
        f"<code>└─ Время: {datetime.now().strftime('%d.%m.%Y %H:%M')}</code>\n\n"
        f"<b>Чтобы ответить:</b>\n"
        f"<code>/покупка {request_id} ТЕКСТ ОТВЕТА</code>"
    )
    
    await bot.send_message(ADMIN_ID, admin_text, parse_mode="HTML")
    
    await message.answer(
        f"✅ <b>Заявка принята!</b>\n\n"
        f"<code>┌─ ЗАЯВКА #{request_id}</code>\n"
        f"<code>├─ Сумма: {amount} {currency}</code>\n"
        f"<code>└─ Статус: Ожидает ответа</code>\n\n"
        f"📨 <b>@{OWNER_USERNAME} свяжется с вами.</b>",
        parse_mode="HTML"
    )
    
    await state.clear()

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
        [InlineKeyboardButton(text="🔙 Назад в меню", callback_data="back_to_menu")]
    ])
    
    await bot.send_message(call.from_user.id, info_text, reply_markup=keyboard, parse_mode="HTML")
    await call.answer()

# ============ НАЗАД В МЕНЮ ============
@dp.callback_query(F.data == "back_to_menu")
async def back_to_menu(call: CallbackQuery, state: FSMContext):
    await state.clear()
    await call.message.delete()
    await show_main_menu(call.from_user.id, call.from_user.id)

# ============ ЗАПУСК ============
async def main():
    print("🤖 Бот запущен!")
    print(f"👑 Админ: @{OWNER_USERNAME}")
    print(f"📱 Бот: @{BOT_USERNAME}")
    print(f"🖼️ Баннер: {'есть' if os.path.exists(BANNER_PATH) else 'нет'}")
    print("\n📋 Доступные команды:")
    print("/pending - все ожидающие заявки")
    print("/заявка НОМЕР ТЕКСТ - ответ на ручение")
    print("/жалоба НОМЕР ТЕКСТ - ответ на жалобу")
    print("/покупка НОМЕР ТЕКСТ - ответ на покупку")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
