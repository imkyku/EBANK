import logging
import config.config as conf
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure, ConfigurationError

def get_db():
    client = MongoClient(conf.MONGOURI)
    return client[conf.DBNAME]

class TransactionManager:
    def __init__(self, db):
        self.db = db
        self.collection_userdata = db['userdata']
        self.collection_bills = db['bills']
        self.collection_transactions = db['transactions']
        self.collection_stats = db['stats']

    def get_user(self, user_id):
        return self.collection_userdata.find_one({"userid": user_id})

    def handle_transaction(self, sender_id, recipient_id, transfer_amount):
        sender = self.collection_userdata.find_one({"userid": sender_id})
        recipient = self.collection_userdata.find_one({"userid": recipient_id})

        if sender is None:
            return "Отправитель не найден в системе.", False

        if recipient is None:
            return "Получатель не найден в системе.", False

        if sender_id == recipient_id:
            return "Вы не можете перевести деньги самому себе!", False

        if sender['balance'] < transfer_amount:
            transaction_id = self.collection_transactions.count_documents({}) + 1
            self.collection_transactions.insert_one({
                "transaction_id": transaction_id,
                "sender_id": sender_id,
                "recipient_id": recipient_id,
                "sender_balance": sender['balance'],
                "recipient_balance": recipient['balance'],
                "transfer_amount": transfer_amount,
                "status": "declined"
            })
            return "Недостаточно средств для перевода.", False

        # Балансы до перевода
        sender_balance_before = sender['balance']
        recipient_balance_before = recipient['balance']

        # Обновление балансов
        sender_new_balance = sender['balance'] - transfer_amount
        recipient_new_balance = recipient['balance'] + transfer_amount

        self.collection_userdata.update_one({"userid": sender_id}, {"$set": {"balance": sender_new_balance}})
        self.collection_userdata.update_one({"userid": recipient_id}, {"$set": {"balance": recipient_new_balance}})

        # Создание транзакции
        transaction_id = self.collection_transactions.count_documents({}) + 1
        self.collection_transactions.insert_one({
            "transaction_id": transaction_id,
            "sender_id": sender_id,
            "recipient_id": recipient_id,
            "sender_balance": sender_balance_before,
            "recipient_balance": recipient_balance_before,
            "transfer_amount": transfer_amount,
            "status": "accepted"
        })

        # Обновление статистики
        self.update_stats(sender_id, recipient_id, transfer_amount)

        return "Перевод совершен успешно", True

    def update_stats(self, sender_id, recipient_id, transfer_amount):
        # Обновление доходов получателя
        self.collection_stats.update_one(
            {"userid": recipient_id},
            {"$inc": {"income": transfer_amount, "profit": transfer_amount}},
            upsert=True
        )

        # Обновление расходов отправителя
        self.collection_stats.update_one(
            {"userid": sender_id},
            {"$inc": {"expenses": transfer_amount, "profit": -transfer_amount}},
            upsert=True
        )

    def initialize_stats(self, user_id):
        self.collection_stats.update_one(
            {"userid": user_id},
            {"$setOnInsert": {"income": 0, "expenses": 0, "profit": 0}},
            upsert=True
        )

    def get_stats(self, user_id):
        return self.collection_stats.find_one({"userid": user_id})

    def create_bill(self, bill_data):
        self.collection_bills.insert_one(bill_data)



