from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from config import STATUS_OPTIONS
def location_type_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Місто"), KeyboardButton(text="Село")],
        ],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


def status_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=s)] for s in STATUS_OPTIONS],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


def edit_menu_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Ім'я"), KeyboardButton(text="Нікнейм")],
            [KeyboardButton(text="Місце проживання")],
            [KeyboardButton(text="Вік"), KeyboardButton(text="Статус")],
            [KeyboardButton(text="Інтереси"), KeyboardButton(text="BIO")],
            [KeyboardButton(text="Почати метчінг")],
        ],
        resize_keyboard=True,
    )