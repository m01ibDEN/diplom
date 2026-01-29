# bot.py
import asyncio
import json
import os
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, WebAppInfo, ReplyKeyboardMarkup, KeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from db import db

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
BASE_URL = os.getenv("BASE_URL", "http://localhost:8000")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# --- FSM для админки ---
class AdminStates(StatesGroup):
    waiting_for_merch_name = State()
    waiting_for_merch_price = State()
    waiting_for_merch_stock = State()
    
    waiting_for_student_id_points = State()
    waiting_for_points_amount = State()

# --- Стартовая команда ---
@dp.message(CommandStart())
async def cmd_start(message: Message):
    user = message.from_user
    db.get_or_create_student(
        telegram_user_id=user.id,
        first_name=user.first_name,
        last_name=user.last_name or '',
        username=user.username or ''
    )
    
    webapp_url = f"{BASE_URL}/miniapp?user_id={user.id}"
    kb = ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="🎮 Student Coins", web_app=WebAppInfo(url=webapp_url))]],
        resize_keyboard=True
    )
    await message.answer(f"👋 Привет, {user.first_name}!\n\n🚀 Открой Student Coins:", reply_markup=kb)

# --- АДМИН ПАНЕЛЬ ---
@dp.message(Command("admin"))
async def cmd_admin(message: Message):
    if not db.is_admin(message.from_user.id):
        await message.answer("⛔ У вас нет прав администратора.")
        return

    kb = types.ReplyKeyboardMarkup(
        keyboard=[
            [types.KeyboardButton(text="➕ Добавить Мерч")],
            [types.KeyboardButton(text="💰 Начислить баллы")],
            [types.KeyboardButton(text="🔙 Выход")]
        ],
        resize_keyboard=True
    )
    await message.answer("🔧 Панель администратора:", reply_markup=kb)

@dp.message(F.text == "🔙 Выход")
async def admin_exit(message: Message, state: FSMContext):
    await state.clear()
    await cmd_start(message)

# --- 1. Добавление Мерча ---
@dp.message(F.text == "➕ Добавить Мерч")
async def start_add_merch(message: Message, state: FSMContext):
    if not db.is_admin(message.from_user.id): return
    await message.answer("Введите название товара:", reply_markup=types.ReplyKeyboardRemove())
    await state.set_state(AdminStates.waiting_for_merch_name)

@dp.message(AdminStates.waiting_for_merch_name)
async def process_merch_name(message: Message, state: FSMContext):
    await state.update_data(name=message.text)
    await message.answer("Введите цену в баллах (число):")
    await state.set_state(AdminStates.waiting_for_merch_price)

@dp.message(AdminStates.waiting_for_merch_price)
async def process_merch_price(message: Message, state: FSMContext):
    if not message.text.isdigit():
        await message.answer("❌ Введите число!")
        return
    await state.update_data(price=int(message.text))
    await message.answer("Введите количество на складе (число):")
    await state.set_state(AdminStates.waiting_for_merch_stock)

@dp.message(AdminStates.waiting_for_merch_stock)
async def process_merch_stock(message: Message, state: FSMContext):
    if not message.text.isdigit():
        await message.answer("❌ Введите число!")
        return
    data = await state.get_data()
    
    success = db.admin_add_merch(data['name'], data['price'], int(message.text))
    if success:
        await message.answer(f"✅ Товар '{data['name']}' добавлен!")
    else:
        await message.answer("❌ Ошибка при добавлении.")
    
    await state.clear()
    await cmd_admin(message)

# --- 2. Начисление баллов ---
@dp.message(F.text == "💰 Начислить баллы")
async def start_add_points(message: Message, state: FSMContext):
    if not db.is_admin(message.from_user.id): return
    await message.answer("Введите Telegram ID студента:", reply_markup=types.ReplyKeyboardRemove())
    await state.set_state(AdminStates.waiting_for_student_id_points)

@dp.message(AdminStates.waiting_for_student_id_points)
async def process_student_id(message: Message, state: FSMContext):
    if not message.text.isdigit():
        await message.answer("❌ ID должен состоять из цифр.")
        return
    await state.update_data(target_id=int(message.text))
    await message.answer("Введите сумму баллов:")
    await state.set_state(AdminStates.waiting_for_points_amount)

@dp.message(AdminStates.waiting_for_points_amount)
async def process_points_amount(message: Message, state: FSMContext):
    try:
        amount = int(message.text)
        data = await state.get_data()
        
        success, msg = db.admin_add_points(data['target_id'], amount, "Бонус от админа")
        await message.answer(f"{'✅' if success else '❌'} {msg}")
        
    except ValueError:
        await message.answer("❌ Введите число.")
    
    await state.clear()
    await cmd_admin(message)

# --- WebApp Data ---
@dp.message(F.web_app_data)
async def webapp_data(message: Message):
    data = json.loads(message.web_app_data.data)
    action = data.get('action')
    user_id = message.from_user.id
    
    if action == 'buy_merch':
        success, msg = db.buy_merch(user_id, data['merch_id'])
        await message.answer(f"{'✅' if success else '❌'} {msg}")
    
    elif action == 'add_service':
        success = db.add_service(
            user_id, 
            data['name'], 
            data['price'], 
            data.get('description', '')
        )
        if success:
            await message.answer(f"✅ Услуга '{data['name']}' размещена!\n\n💰 Цена: {data['price']} баллов")
        else:
            await message.answer("❌ Ошибка при размещении услуги")
    
    elif action == 'buy_service':
        success, msg = db.buy_service(user_id, data['service_id'])
        await message.answer(f"{'✅' if success else '❌'} {msg}")

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())