from sqlalchemy.orm import Session
from sqlalchemy.exc import NoResultFound
from database import User 
from aiogram.types import Message
from keyboard.reply import edit_menu_kb
def get_user_by_telegram_id(session: Session, telegram_id: int):
    """
    Повертає користувача за telegram_id або None, якщо не існує.
    """
    return session.query(User).filter(User.telegram_id == telegram_id).one_or_none()


async def send_edit_menu(message: Message):
    await message.answer(
        "Що хочеш змінити? Обери параметр нижче 👇",
        reply_markup=edit_menu_kb(),
    )

def get_status_emoji(status: str) -> str:
    if not status:
        return "👶"
    status = status.lower()
    if "мама" in status:
        return "👩‍👧‍👦"
    if "вагіт" in status:
        return "🤰"
    return "👶"
