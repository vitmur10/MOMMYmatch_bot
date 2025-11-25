from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from config import STATUS_OPTIONS, VALID_REGIONS, INTEREST_OPTIONS
import math


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
        ],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


# 1️⃣ Інтереси (з можливістю вибору кількох)
def build_interests_kb(selected: list[str]) -> ReplyKeyboardMarkup:
    rows = []

    for interest in INTEREST_OPTIONS:
        mark = "✅ " if interest in selected else ""
        rows.append([KeyboardButton(text=f"{mark}{interest}")])

    rows.append([KeyboardButton(text="Готово")])

    return ReplyKeyboardMarkup(
        keyboard=rows,
        resize_keyboard=True,
        one_time_keyboard=False
    )


# 2️⃣ Підтвердження анкети
def confirm_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Все ок"), KeyboardButton(text="Змінити")],
        ],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


# 3️⃣ Інтереси в режимі редагування
def build_edit_interests_kb(selected: list[str]) -> ReplyKeyboardMarkup:
    rows = []

    for interest in INTEREST_OPTIONS:
        mark = "✅ " if interest in selected else ""
        rows.append([KeyboardButton(text=f"{mark}{interest}")])

    rows.append([KeyboardButton(text="Готово")])

    return ReplyKeyboardMarkup(
        keyboard=rows,
        resize_keyboard=True,
        one_time_keyboard=True
    )


# 5️⃣ Лайк / Дизлайк
def build_match_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="👍 Лайк"), KeyboardButton(text="👎 Дизлайк")],
        ],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


# 6️⃣ Вибір критеріїв метчингу
def build_match_criteria_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📍 Місце проживання")],
            [KeyboardButton(text="📍+🧩 Місце + інтереси")],
            [KeyboardButton(text="🧩 Інтереси")],
        ],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


# 7️⃣ Пагінація областей
PAGE_SIZE = 6


def build_regions_kb(page: int = 0) -> ReplyKeyboardMarkup:
    total = len(VALID_REGIONS)
    total_pages = math.ceil(total / PAGE_SIZE)

    if page < 0:
        page = 0
    if page > total_pages - 1:
        page = total_pages - 1

    start = page * PAGE_SIZE
    end = start + PAGE_SIZE
    regions_slice = VALID_REGIONS[start:end]

    rows = [[KeyboardButton(text=region)] for region in regions_slice]

    nav_row = []
    if total_pages > 1:
        if page > 0:
            nav_row.append(KeyboardButton(text="⬅️ Назад"))
        if page < total_pages - 1:
            nav_row.append(KeyboardButton(text="Вперед ➡️"))

    if nav_row:
        rows.append(nav_row)

    rows.append([KeyboardButton(text="Скасувати")])

    return ReplyKeyboardMarkup(
        keyboard=rows,
        resize_keyboard=True,
        one_time_keyboard=False,
    )
