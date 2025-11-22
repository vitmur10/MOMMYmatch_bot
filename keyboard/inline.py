from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from config import INTEREST_OPTIONS


def build_interests_kb(selected: list[str]) -> InlineKeyboardMarkup:
    """
    Інлайн-клавіатура з інтересами.
    Обрані інтереси позначаємо "✅".
    """
    rows = []
    for interest in INTEREST_OPTIONS:
        is_selected = interest in selected
        text = f"✅ {interest}" if is_selected else interest
        rows.append(
            [InlineKeyboardButton(
                text=text,
                callback_data=f"interest:{interest}",
            )]
        )

    rows.append([
        InlineKeyboardButton(
            text="Готово ✅",
            callback_data="interests_done",
        )
    ])

    return InlineKeyboardMarkup(inline_keyboard=rows)


def confirm_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="Все ок ✅", callback_data="confirm_yes"),
                InlineKeyboardButton(text="Змінити ❌", callback_data="confirm_no"),
            ]
        ]
    )


def build_edit_interests_kb(selected: list[str]) -> InlineKeyboardMarkup:
    rows = []
    for interest in INTEREST_OPTIONS:
        is_selected = interest in selected
        text = f"✅ {interest}" if is_selected else interest
        rows.append(
            [InlineKeyboardButton(
                text=text,
                callback_data=f"edit_interest:{interest}",
            )]
        )

    rows.append([
        InlineKeyboardButton(
            text="Готово ✅",
            callback_data="edit_interests_done",
        )
    ])

    return InlineKeyboardMarkup(inline_keyboard=rows)



def view_after_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="Оновити дані ✏️", callback_data="view_edit"),
                InlineKeyboardButton(text="Почати метчінг 🤝", callback_data="view_match"),
            ]
        ]
    )