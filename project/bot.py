# bot.py
import asyncio
import json
import os
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart
from aiogram.types import Message, WebAppInfo, ReplyKeyboardMarkup, KeyboardButton
from db import db

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
BASE_URL = os.getenv("BASE_URL", "http://localhost:8000")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

@dp.message(CommandStart())
async def cmd_start(message: Message):
    user = message.from_user
    
    # Создаём/получаем студента в БД
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

@dp.message(F.web_app_data)
async def webapp_data(message: Message):
    data = json.loads(message.web_app_data.data)
    action = data.get('action')
    
    if action == 'buy_merch':
        success, msg = db.buy_merch(message.from_user.id, data['merch_id'])
        await message.answer(f"{'✅' if success else '❌'} {msg}")
    
    elif action == 'add_service':
        success = db.add_service(message.from_user.id, data['name'], data['price'], data.get('description', ''))
        await message.answer("✅ Услуга размещена!" if success else "❌ Ошибка")
    
    elif action == 'buy_service':
        success, msg = db.buy_service(message.from_user.id, data['service_id'])
        await message.answer(f"{'✅' if success else '❌'} {msg}")

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
