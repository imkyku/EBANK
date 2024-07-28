from aiogram import F, Router
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
import app.keyboard as kb
from app.transactions import TransactionManager
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure, ConfigurationError
import logging

router = Router()

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

db = setup_mongo()
if db is None:
    raise Exception("Не удалось установить соединение с базой данных")

class TransferStates(StatesGroup):
    waiting_for_recipient_id = State()
    waiting_for_transfer_amount = State()

async def start_handler(message: Message, db):
    user_id = message.from_user.id
    username = message.from_user.username
    user_data = {
        "userid": user_id,
        "balance": 0,
        "referals": 0,
        "status": "user",
        "username": username if username else None
    }

    collection = db['userdata']
    existing_user = collection.find_one({"userid": user_id})
    if not existing_user:
        collection.insert_one(user_data)
        transaction_manager = TransactionManager(db)
        transaction_manager.initialize_stats(user_id)
        await message.answer("Вы успешно зарегистрированы в системе.", reply_markup=kb.main)
    else:
        transaction_manager = TransactionManager(db)
        transaction_manager.initialize_stats(user_id)
        await message.answer("Вы уже зарегистрированы в системе.", reply_markup=kb.main)

@router.message(Command('zighalal1488mednibichok'))
async def cmd_zighalal(message: Message):
    await message.reply('Вы открыли посхалко 14/88')

@router.message(F.text == '👤 Профиль')
async def profile(message: Message):
    user_id = message.from_user.id
    transaction_manager = TransactionManager(db)
    user = transaction_manager.get_user(user_id)

    if user:
        profile_text = (f"<b>💸 Ваш профиль:</b>\n\n"
                        f"🪁 Ваше имя: {user.get('username', 'N/A')}\n"
                        f"🏮 Ваш ID: {user['userid']}\n"
                        f"🔮 Ваш баланс: {user['balance']}")
        await message.reply(profile_text, reply_markup=kb.profile, parse_mode='HTML')
    else:
        await message.reply("Пользователь не найден в системе.")

@router.callback_query(F.data == 'profilestats')
async def profilestats(callback: CallbackQuery):
    user_id = callback.from_user.id
    transaction_manager = TransactionManager(db)
    stats = transaction_manager.get_stats(user_id)

    if stats:
        stats_text = (f"<b>🎀 Статистика:</b>\n\n"
                      f"Доходы: {stats['income']}\n"
                      f"Расходы: {stats['expenses']}\n"
                      f"Профит: {stats['profit']}")
        await callback.message.answer(stats_text, parse_mode='HTML')
    else:
        await callback.message.answer("Статистика не найдена.")

@router.message(F.text == '🧶 Операции')
async def operations(message: Message):
    await message.answer("Выберите операцию:", reply_markup=kb.trans)

@router.callback_query(F.data == 'trans')
async def handle_trans(callback: CallbackQuery, state: FSMContext):
    await callback.message.answer("Введите ID получателя:")
    await state.set_state(TransferStates.waiting_for_recipient_id)
    await callback.answer()

@router.message(TransferStates.waiting_for_recipient_id, F.text.regexp(r'^\d+$'))
async def get_recipient_id(message: Message, state: FSMContext):
    recipient_id = int(message.text)
    await state.update_data(recipient_id=recipient_id)
    await message.answer("Введите сумму перевода:")
    await state.set_state(TransferStates.waiting_for_transfer_amount)

@router.message(TransferStates.waiting_for_transfer_amount, F.text.regexp(r'^\d+(\.\d{1,2})?$'))
async def get_transfer_amount(message: Message, state: FSMContext):
    transfer_amount = float(message.text)
    sender_id = message.from_user.id
    data = await state.get_data()
    recipient_id = data['recipient_id']

    transaction_manager = TransactionManager(db)
    result_message, success = transaction_manager.handle_transaction(sender_id, recipient_id, transfer_amount)

    await message.answer(result_message)
    if success:
        await message.bot.send_message(recipient_id, f"Пополнение средств от {sender_id}. Сумма: {transfer_amount}. Ваш баланс: {transaction_manager.get_user(recipient_id)['balance']}")
    await state.clear()
