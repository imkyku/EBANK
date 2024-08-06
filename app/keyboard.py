from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton

main = ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text='👤 Профиль')],
                                     [KeyboardButton(text='🧶 Операции')],
                                     [KeyboardButton(text='Пополнение'),
                                      KeyboardButton(text='Вывод')]],
                           resize_keyboard=True,
                           input_field_placeholder='Выберите пункт меню...')

profile = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text='Статистика', callback_data='profilestats')],
                                                [InlineKeyboardButton(text='Рефералы', callback_data='referals')]])

trans = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text='Быстрый перевод', callback_data='trans')],
    [InlineKeyboardButton(text='Выставить счет', callback_data='bills')]
])

bill_actions = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text='Оплатить', callback_data='pay_bill'),
    InlineKeyboardButton(text='Отклонить', callback_data='decline_bill')]
])
