import logging
import asyncio
from aiogram import F, Router, Bot, Dispatcher
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from yoomoney import Quickpay, Client
from app.db import get_db
import config.config as conf

router = Router()
db = get_db()
if db is None: raise Exception("Не удалось установить соединение с базой данных")


# Состояния FSM для пополнения баланса
class DepositStates(StatesGroup):
    waiting_for_amount = State()
    waiting_for_payment = State()


# Обработчик команды "Пополнение"
@router.message(F.text == 'Пополнение')
async def handle_deposit(message: Message, state: FSMContext):
    await message.answer("Введите сумму пополнения:")
    await state.set_state(DepositStates.waiting_for_amount)


# Обработчик ввода суммы пополнения
@router.message(DepositStates.waiting_for_amount, F.text.regexp(r'^\d+(\.\d{1,2})?$'))
async def process_amount(message: Message, state: FSMContext):
    amount = float(message.text)
    user_id = message.from_user.id
    transaction_id = db['income'].count_documents({}) + 1

    # Получение текущего баланса пользователя из БД
    user_data = db['userdata'].find_one({"userid": user_id})
    if not user_data:
        await message.answer("Не удалось найти данные пользователя.")
        return
    current_balance = user_data.get("balance", 0)

    # Создание записи о транзакции в БД
    db['income'].insert_one({
        "id": transaction_id,
        "user_id": user_id,
        "balance": current_balance,
        "amount": amount,
        "status": "pending"
    })

    # Создание ссылки на оплату
    quickpay = Quickpay(
        receiver="4100118777598383",
        quickpay_form="shop",
        targets="Пополнение баланса",
        paymentType="SB",
        sum=amount,
        label=f"{user_id}_{transaction_id}"
    )

    # Создание Inline кнопки с ссылкой на оплату
    keyboard = InlineKeyboardBuilder()
    keyboard.button(text="Оплатить", url=quickpay.base_url)
    await message.answer(f"Для пополнения баланса на {amount} руб., нажмите кнопку 'Оплатить' ниже.",
                         reply_markup=keyboard.as_markup())

    # Переход к состоянию ожидания оплаты
    await state.update_data(transaction_id=transaction_id)
    await state.set_state(DepositStates.waiting_for_payment)


# Проверка статуса оплаты
async def check_payment_status(user_id, transaction_id):
    client = Client(conf.YOOMONEY)
    label = f"{user_id}_{transaction_id}"
    history = client.operation_history(label=label)

    if not history.operations:
        return "pending"

    for operation in history.operations:
        if operation.status == 'success':
            return "success"

    return "declined"


# Обработчик завершения оплаты
@router.message(DepositStates.waiting_for_payment)
async def handle_payment(message: Message, state: FSMContext):
    user_id = message.from_user.id
    data = await state.get_data()
    transaction_id = data['transaction_id']

    # Проверка статуса оплаты
    status = await check_payment_status(user_id, transaction_id)
    if status == "success":
        amount = db['income'].find_one({"id": transaction_id})["amount"]
        db['income'].update_one({"id": transaction_id}, {"$set": {"status": "success"}})

        # Обновление баланса пользователя в БД
        db['userdata'].update_one({"userid": user_id}, {"$inc": {"balance": amount}})
        await message.answer(f"Пополнение баланса №{transaction_id} успешно завершено.")
    elif status == "pending":
        await message.answer("Оплата еще не поступила. Пожалуйста, попробуйте позже.")
    elif status == "declined":
        db['income'].update_one({"id": transaction_id}, {"$set": {"status": "declined"}})
        await message.answer(f"Пополнение баланса №{transaction_id} отменено.")

    await state.clear()


# Фоновая задача для проверки статусов платежей
async def payment_status_checker(bot: Bot):
    while True:
        transactions = db['income'].find({"status": "pending"})
        for transaction in transactions:
            user_id = transaction["user_id"]
            transaction_id = transaction["id"]
            status = await check_payment_status(user_id, transaction_id)
            if status == "success":
                amount = transaction["amount"]
                db['income'].update_one({"id": transaction_id}, {"$set": {"status": "success"}})

                # Обновление баланса пользователя в БД
                db['userdata'].update_one({"userid": user_id}, {"$inc": {"balance": amount}})
                await bot.send_message(user_id, f"Пополнение баланса №{transaction_id} успешно завершено.")
            elif status == "declined":
                db['income'].update_one({"id": transaction_id}, {"$set": {"status": "declined"}})
                await bot.send_message(user_id, f"Пополнение баланса №{transaction_id} отменено.")

        await asyncio.sleep(10)  # Проверка каждые 10 секунд


# Запуск фоновой задачи
async def start_payment_status_checker(dispatcher: Dispatcher):
    await asyncio.create_task(payment_status_checker(dispatcher.bot))


# Включение маршрутизатора и запуск проверки статусов
def setup_deposit_handlers(dispatcher: Dispatcher):
    dispatcher.include_router(router)
    dispatcher.startup.register(start_payment_status_checker)
