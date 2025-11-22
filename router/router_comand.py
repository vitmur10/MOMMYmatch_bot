from aiogram import Router
from aiogram.filters import CommandStart
from function import get_user_by_telegram_id
from aiogram.types import Message
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from config import SessionLocal
from state import ProfileStates, EditProfileStates
from function import send_edit_menu, get_status_emoji
from keyboard.inline import view_after_kb
router_comand = Router()

@router_comand.message(CommandStart())
async def process_start_command(message: Message, state: FSMContext):
    session = SessionLocal()
    try:
        user = get_user_by_telegram_id(session, message.from_user.id)

        if user is None:
            # ❌ Немає в БД → запускаємо анкету
            await state.set_state(ProfileStates.name)
            await message.answer(
                "Привіт! 👋\n"
                "Давай заповнимо анкету, щоб я могла підбирати тобі мам 🫶\n\n"
                "Спочатку — як тебе звати? Напиши, будь ласка, своє ім’я."
            )
        else:
            # ✅ Є в БД → просто вітаємо
            await message.answer(
                "Ти вже зареєстрована в системі 🌸\n\n"
                "Можеш скористатися командами:\n"
                "• /view — переглянути свій профіль\n"
                "• /edit — змінити дані анкети\n"
                "• /match — почати пошук мам (коли реалізуємо метчінг)\n"
            )
    finally:
        session.close()


@router_comand.message(Command("help"))
async def cmd_help(message: Message):
    text = (
        "📘 *Допомога — доступні команди*\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "👋 /start — почати роботу з ботом\n"
        "📇 /view — переглянути свій профіль\n"
        "✏️ /edit — змінити дані анкети\n"
        "🤝 /match — почати пошук мам (метчінг)\n"
        "ℹ️ /help — переглянути список команд\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "Якщо ти ще не зареєстрована — бот автоматично запропонує заповнити анкету ❤️"
    )

    await message.answer(text, parse_mode="Markdown")


@router_comand.message(Command("edit"))
async def cmd_edit(message: Message, state: FSMContext):
    session = SessionLocal()
    try:
        user = get_user_by_telegram_id(session, message.from_user.id)
    finally:
        session.close()

    if user is None:
        await message.answer(
            "Тебе ще немає в базі 🧐\n"
            "Спочатку заповни анкету через /start, а потім зможемо її редагувати."
        )
        return

    await state.set_state(EditProfileStates.menu)
    await send_edit_menu(message)



@router_comand.message(Command("view"))
async def cmd_view(message: Message, state: FSMContext):
    session = SessionLocal()
    try:
        user = get_user_by_telegram_id(session, message.from_user.id)
    finally:
        session.close()

    if user is None:
        await message.answer(
            "Тебе ще немає в базі 🧐\n"
            "Спочатку заповни анкету через /start, а потім зможеш її переглядати."
        )
        return

    # Нормалізація даних
    name = user.name or "не вказано"
    nickname = user.nickname or "не вказано"
    region = user.region or "не вказано"

    if user.city:
        place = f"🏙 {user.city}"
    elif user.village:
        place = f"🌿 {user.village}"
    else:
        place = "не вказано"

    age = str(user.age) if user.age is not None else "не вказано"
    status = user.status or "не вказано"

    if user.interests:
        interests_lines = "\n".join(f"   • {i}" for i in user.interests)
        interests_block = f"\n{interests_lines}"
    else:
        interests_block = " не вказано"

    bio = user.bio or "не вказано"

    status_emoji = get_status_emoji(user.status)

    # Картка профілю
    text = (
        f"{status_emoji} *Твій профіль*\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"👩 *Ім'я:* {name}\n"
        f"✨ *Нікнейм:* {nickname}\n"
        f"📍 *Область:* {region}\n"
        f"📌 *Місто / село:* {place}\n"
        f"🎂 *Вік:* {age}\n"
        f"👶 *Статус:* {status}\n"
        f"🧩 *Інтереси:*{interests_block}\n"
        f"📜 *BIO:*\n{bio}\n"
        f"━━━━━━━━━━━━━━━━━━━━"
    )

    # Одне красиве повідомлення-картка
    await message.answer(text, parse_mode="Markdown")

    # Пропозиція оновити / почати метчінг
    await message.answer(
        "Хочеш щось змінити чи почати метчінг?",
        reply_markup=view_after_kb(),
    )
