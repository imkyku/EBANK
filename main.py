import logging
from aiogram import Bot, Dispatcher
from aiogram.types import Message
from aiogram.filters import Command
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.strategy import FSMStrategy
import asyncio
from app.handlers import router, start_handler
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure, ConfigurationError
import app.keyboard as kb

# Настройка логирования
logging.basicConfig(level=logging.INFO)

def setup_mongo():
    try:
        # Обновление строки подключения MongoDB
        mongo_url = 'YOUR_MONGO_URI'
        client = MongoClient(mongo_url)
        db = client['data']  # Имя базы данных
        return db
    except (ConnectionFailure, ConfigurationError) as e:
        logging.error(f"Ошибка подключения к MongoDB: {e}")
        return None

async def main():
    bot = Bot(token='YOUR_BOT_TOKEN')
    dp = Dispatcher(storage=MemoryStorage(), fsm_strategy=FSMStrategy.CHAT)
    dp.include_router(router)

    # Настройка MongoDB
    db = setup_mongo()
    if db is None:
        logging.error("Не удалось установить соединение с базой данных. Завершение работы.")
        return

    # Регистрация обработчика сообщений /start
    @dp.message(Command("start"))
    async def on_start_command(message: Message):
        await start_handler(message, db)

    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())
