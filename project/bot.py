import asyncio
import os
import json
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, WebAppInfo, ReplyKeyboardMarkup, KeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from db import db

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
BASE_URL = os.getenv("BASE_URL", "https://gigglingly-putrid-walter.ngrok-free.dev/miniapp")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# Добавь состояние регистрации
class Registration(StatesGroup):
    waiting_for_student_card = State()

@dp.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    user = message.from_user
    
    # 1. Проверяем, есть ли пользователь уже в базе
    existing_student = db.get_student_by_tg_id(user.id)
    
    if existing_student:
        # Если уже зарегистрирован — показываем кнопку приложения
        webapp_url = f"{BASE_URL}/miniapp?user_id={user.id}"
        kb = ReplyKeyboardMarkup(
            keyboard=[[KeyboardButton(text="Открыть приложение", web_app=WebAppInfo(url=webapp_url))]],
            resize_keyboard=True
        )
        await message.answer(f"С возвращением, {existing_student['first_name']}!", reply_markup=kb)
    else:
        # 2. Если нет — начинаем регистрацию
        await message.answer(
            "Привет! Я бот Student Coins.\n"
            "Чтобы начать, введите номер вашего студенческого билета (например, 23У001):"
        )
        await state.set_state(Registration.waiting_for_student_card)

@dp.message(Registration.waiting_for_student_card)
async def process_student_card(message: Message, state: FSMContext):
    card_number = message.text.strip().upper() # Убираем пробелы, делаем капсом
    user = message.from_user

    # 3. Пытаемся зарегистрировать
    # Метод db.register_student должен проверить, свободен ли номер
    success, msg = db.register_student_by_card(
        telegram_id=user.id,
        card_number=card_number,
        first_name=user.first_name,
        last_name=user.last_name or ""
    )

    if success:
        await message.answer("Регистрация успешна! Теперь вам доступно приложение.")
        # Вызываем cmd_start снова, чтобы показать кнопку
        await state.clear()
        await cmd_start(message, state)
    else:
        await message.answer(f"Ошибка: {msg}\nПопробуйте ввести номер еще раз:")


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
    # Регистрируем пользователя, если его нет
    db.get_or_create_student(
        telegram_user_id=user.id,
        first_name=user.first_name,
        last_name=user.last_name or '',
        username=user.username or ''
    )
    
    # Ссылка на Mini App
    webapp_url = f"{BASE_URL}/miniapp?user_id={user.id}"
    
    kb = ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="Student Coins", web_app=WebAppInfo(url=webapp_url))]],
        resize_keyboard=True
    )
    await message.answer(f"Привет, {user.first_name}.\n\nНажмите кнопку ниже, чтобы открыть приложение.", reply_markup=kb)

# --- АДМИН ПАНЕЛЬ ---
@dp.message(Command("admin"))
async def cmd_admin(message: Message):
    # Проверка прав (предполагаем наличие метода is_admin в db)
    # Если метода нет, добавьте его в db.py или уберите проверку
    if hasattr(db, 'is_admin') and not db.is_admin(message.from_user.id):
        await message.answer("У вас нет прав администратора.")
        return

    kb = types.ReplyKeyboardMarkup(
        keyboard=[
            [types.KeyboardButton(text="Добавить товар")],
            [types.KeyboardButton(text="Начислить баллы")],
            [types.KeyboardButton(text="Выход")]
        ],
        resize_keyboard=True
    )
    await message.answer("Панель администратора:", reply_markup=kb)

@dp.message(F.text == "Выход")
async def admin_exit(message: Message, state: FSMContext):
    await state.clear()
    await cmd_start(message)

# --- 1. Добавление Товара (Мерч) ---
@dp.message(F.text == "Добавить товар")
async def start_add_merch(message: Message, state: FSMContext):
    if hasattr(db, 'is_admin') and not db.is_admin(message.from_user.id): return
    
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
        await message.answer("Введите корректное число.")
        return
    await state.update_data(price=int(message.text))
    await message.answer("Введите количество на складе (число):")
    await state.set_state(AdminStates.waiting_for_merch_stock)

@dp.message(AdminStates.waiting_for_merch_stock)
async def process_merch_stock(message: Message, state: FSMContext):
    if not message.text.isdigit():
        await message.answer("Введите корректное число.")
        return
    
    data = await state.get_data()
    # Предполагаем наличие метода admin_add_merch
    if hasattr(db, 'add_new_merch'):
        # Используем существующий метод add_new_merch(name, desc, price, stock)
        # Описание пустой строкой, так как в боте не спрашиваем
        success, msg = db.add_new_merch(data['name'], "", data['price'], int(message.text))
    else:
        success, msg = False, "Метод добавления не найден в БД"

    if success:
        await message.answer(f"Товар '{data['name']}' добавлен.")
    else:
        await message.answer(f"Ошибка при добавлении: {msg}")
    
    await state.clear()
    await cmd_admin(message)

# --- 2. Начисление баллов ---
@dp.message(F.text == "Начислить баллы")
async def start_add_points(message: Message, state: FSMContext):
    if hasattr(db, 'is_admin') and not db.is_admin(message.from_user.id): return
    
    await message.answer("Введите Telegram ID студента:", reply_markup=types.ReplyKeyboardRemove())
    await state.set_state(AdminStates.waiting_for_student_id_points)

@dp.message(AdminStates.waiting_for_student_id_points)
async def process_student_id(message: Message, state: FSMContext):
    if not message.text.isdigit():
        await message.answer("ID должен состоять из цифр.")
        return
    
    # Проверяем, существует ли студент
    student = db.get_student_by_tg_id(int(message.text))
    if not student:
        await message.answer("Студент с таким ID не найден.")
        return

    await state.update_data(target_tg_id=int(message.text))
    await state.update_data(target_uuid=student['id']) # Сохраняем UUID для начисления
    
    await message.answer("Введите сумму баллов:")
    await state.set_state(AdminStates.waiting_for_points_amount)

@dp.message(AdminStates.waiting_for_points_amount)
async def process_points_amount(message: Message, state: FSMContext):
    try:
        amount = int(message.text)
        data = await state.get_data()
        
        # Используем наш новый метод add_points, который принимает UUID
        success, msg = db.add_points(data['target_uuid'], amount, "Начисление администратором")
        
        if success:
            await message.answer(f"Успешно начислено {amount} баллов.")
        else:
            await message.answer(f"Ошибка: {msg}")
        
    except ValueError:
        await message.answer("Введите корректное число.")
    
    await state.clear()
    await cmd_admin(message)

# --- Обработка данных из WebApp (если приходят) ---
@dp.message(F.web_app_data)
async def webapp_data(message: Message):
    # Этот хендлер срабатывает, если Mini App отправляет данные обратно в бот методом sendData
    # В текущей версии API мы работаем через HTTP запросы, поэтому сюда данные могут не приходить
    try:
        data = json.loads(message.web_app_data.data)
        await message.answer(f"Получены данные: {data}")
    except:
        pass

async def main():
    # Удаляем вебхук и запускаем поллинг
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
