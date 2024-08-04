from pymongo import MongoClient

class TransactionManager:
    def __init__(self, db):
        self.db = db
        self.collection_userdata = db['userdata']  # Название коллекции пользователей
        self.collection_bills = db['bills']  # Название коллекции счетов

    def get_user(self, user_id):
        return self.collection_userdata.find_one({"userid": user_id})

    def create_bill(self, bill_data):
        self.collection_bills.insert_one(bill_data)
