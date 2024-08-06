import logging
import asyncio
from aiogram import Bot, Dispatcher
from aiogram.types import Message
from aiogram.filters import Command
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.strategy import FSMStrategy

import app.keyboard as kb
import config.config as conf
from app.handlers import router
from app.handlers import start_handler
from app.db import get_db
from app.bills import router as bills_router
from app.deposit import router as deposit_router

# Настройка логирования
logging.basicConfig(level=logging.INFO)

async def main():
    bot = Bot(token=conf.TOKEN)
    dp = Dispatcher(storage=MemoryStorage(), fsm_strategy=FSMStrategy.CHAT)
    dp.include_router(router)

    # Настройка MongoDB
    db = get_db()
    if db is None:
        logging.error("Не удалось установить соединение с базой данных. Завершение работы.")
        return

    # Подключите маршрутизатор для счетов и передайте объект базы данных
    dp.include_router(bills_router)
    dp.include_router(deposit_router)

    # Регистрация обработчика сообщений /start
    @dp.message(Command("start"))
    async def on_start_command(message: Message):
        await start_handler(message, db)

    await dp.start_polling(bot)

if __name__ == '__main__':
    try: asyncio.run(main())
    except KeyboardInterrupt:
        print('✯ Перезагрузка....')
