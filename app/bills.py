from aiogram import F, Router
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
import app.keyboard as kb
import logging
from app.transaction_manager import TransactionManager  # Импортируйте TransactionManager
from pymongo import MongoClient

router = Router()

# Настройка MongoDB
mongo_url = 'YOUR_MONGO_URI'
client = MongoClient(mongo_url)
db = client['data']  # Имя базы данных
transaction_manager = TransactionManager(db)


# Определяем состояния для выставления счета
class BillStates(StatesGroup):
    waiting_for_recipient_id = State()
    waiting_for_amount = State()
    waiting_for_comment = State()


async def cmd_bills(callback: CallbackQuery, state: FSMContext):
    logging.info("Кнопка 'Выставить счет' нажата")
    await handle_bills_command(callback, state)


async def handle_bills_command(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id

    # Проверка статуса пользователя
    user = transaction_manager.get_user(user_id)
    if user and user.get('status') == 'ИП':
        await callback.message.answer("Введите ID получателя счета:")
        await state.set_state(BillStates.waiting_for_recipient_id)
    else:
        await callback.answer("У вас нет статуса ИП.")


@router.callback_query(F.data == 'bills')
async def on_bills_command(callback: CallbackQuery, state: FSMContext):
    await cmd_bills(callback, state)


@router.message(BillStates.waiting_for_recipient_id, F.text.regexp(r'^\d+$'))
async def get_recipient_id(message: Message, state: FSMContext):
    recipient_id = int(message.text)
    user_id = message.from_user.id

    # Проверка существования получателя
    recipient = transaction_manager.get_user(recipient_id)
    if not recipient:
        await message.answer("Получатель не найден в системе.")
        await state.clear()
        return

    if recipient_id == user_id:
        await message.answer("Вы не можете выставить счет самому себе.")
        await state.clear()
        return

    await state.update_data(recipient_id=recipient_id)
    await message.answer("Введите сумму (не менее 0.01 и не более 10,000,000):")
    await state.set_state(BillStates.waiting_for_amount)


@router.message(BillStates.waiting_for_amount, F.text.regexp(r'^\d+(\.\d{1,2})?$'))
async def get_amount(message: Message, state: FSMContext):
    transfer_amount = float(message.text)

    if transfer_amount <= 0 or transfer_amount > 10000000:
        await message.answer("Сумма должна быть больше 0 и не превышать 10,000,000.")
        return

    await state.update_data(amount=transfer_amount)
    await message.answer("Введите комментарий, за что вы выставляете счет (от 3 до 25 символов):")
    await state.set_state(BillStates.waiting_for_comment)


@router.message(BillStates.waiting_for_comment, F.text)
async def get_comment(message: Message, state: FSMContext):
    comment = message.text.strip()

    if len(comment) < 3 or len(comment) > 25:
        await message.answer("Комментарий должен содержать от 3 до 25 символов.")
        return

    data = await state.get_data()
    recipient_id = data['recipient_id']
    amount = data['amount']
    user_id = message.from_user.id

    # Создание счета
    bill_id = transaction_manager.collection_bills.count_documents({}) + 1
    commission = amount * 0.03
    total_amount = amount + commission

    transaction_manager.create_bill({
        "bill_id": bill_id,
        "sender_id": user_id,
        "recipient_id": recipient_id,
        "amount": amount,
        "commission": commission,
        "total_amount": total_amount,
        "status": "pending",
        "comment": comment
    })

    await message.answer("Счет успешно выставлен.")
    await message.bot.send_message(recipient_id,
                                   f"Вам выставлен счет от ИП {user_id} за '{comment}'\n"
                                   f"Сумма: {total_amount}\n"
                                   f"Статус: Ожидает оплаты.",
                                   reply_markup=kb.bill_actions)

    await state.clear()


@router.callback_query(F.data == 'pay_bill')
async def pay_bill(callback: CallbackQuery):
    user_id = callback.from_user.id

    # Получение информации о счете
    bill = transaction_manager.collection_bills.find_one({"recipient_id": user_id, "status": "pending"})

    if bill:
        user_balance = transaction_manager.get_user(user_id)['balance']

        if user_balance >= bill['total_amount']:
            # Обновление балансов
            # Списываем средства с аккаунта пользователя
            transaction_manager.collection_userdata.update_one(
                {"userid": user_id},
                {"$inc": {"balance": -bill['total_amount']}}
            )
            # Начисляем средства отправителю
            transaction_manager.collection_userdata.update_one(
                {"userid": bill['sender_id']},
                {"$inc": {"balance": bill['amount']}}
            )
            # Начисляем комиссию на специальный аккаунт
            transaction_manager.collection_userdata.update_one(
                {"userid": 918230700},
                {"$inc": {"balance": bill['commission']}}
            )

            # Обновление статуса счета
            transaction_manager.collection_bills.update_one(
                {"bill_id": bill['bill_id']},
                {"$set": {"status": "accepted"}}
            )
            await callback.answer("Счет оплачен успешно!")
        else:
            transaction_manager.collection_bills.update_one(
                {"bill_id": bill['bill_id']},
                {"$set": {"status": "notenough"}}
            )
            await callback.answer("Недостаточно средств для оплаты счета.")
    else:
        await callback.answer("Нет активных счетов для оплаты.")


@router.callback_query(F.data == 'decline_bill')
async def decline_bill(callback: CallbackQuery):
    user_id = callback.from_user.id
    bill = transaction_manager.collection_bills.find_one({"recipient_id": user_id, "status": "pending"})

    if bill:
        # Обновление статуса счета
        transaction_manager.collection_bills.update_one(
            {"bill_id": bill['bill_id']},
            {"$set": {"status": "declined"}}
        )
        await callback.answer("Счет отклонен.")
    else:
        await callback.answer("Нет активных счетов для отклонения.")
