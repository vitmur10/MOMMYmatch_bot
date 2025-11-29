from aiogram import Router
from aiogram.filters import CommandStart, Command
from aiogram.types import Message
from aiogram.fsm.context import FSMContext
import asyncio
from database import SessionLocal
from state import ProfileStates, EditProfileStates, MatchStates
from function import (
    get_user_by_telegram_id,
    send_edit_menu,
    get_status_emoji,
    render_bot_message,
)
from keyboard.reply import build_match_criteria_kb
import html

router_comand = Router()


# ====================== /start ======================

@router_comand.message(CommandStart())
async def process_start_command(message: Message, state: FSMContext):
    """
    /start

    NEW user (нема в БД):
      1) Повідомлення з привітанням (start_r2_c0)
      2) Затримка 10 секунд
      3) Повідомлення з представленням бота + питанням "А як тебе звати?" (start_r4_c0)
      4) Стан ProfileStates.name

    REGISTERED user (є в БД):
      1) Повідомлення з колонки REGISTERED (start_r2_c1)
    """
    session = SessionLocal()
    try:
        user = get_user_by_telegram_id(session, message.from_user.id)

        # 🔹 Новий користувач
        if user is None:
            # 1) Перше вітальне повідомлення
            text_intro = render_bot_message(session, "start_r2_c0", lang="uk")
            await message.answer(text_intro, parse_mode="HTML")

            # 2) Затримка 10 секунд (згідно CSV: "затримка 10 секунд")
            await asyncio.sleep(10)

            # 3) Друге повідомлення: представлення бота + "А як тебе звати?"
            text_ask_name = render_bot_message(session, "start_r4_c0", lang="uk")

            # 4) Ставимо стан "name" і задаємо питання
            await state.set_state(ProfileStates.name)
            await message.answer(text_ask_name, parse_mode="HTML")

        # 🔹 Користувач уже є в базі
        else:
            # Текст з колонки REGISTERED user → row2, col1
            text_existing = render_bot_message(session, "start_r2_c1", lang="uk")
            await message.answer(text_existing, parse_mode="HTML")

    finally:
        session.close()

# ====================== /help ======================

@router_comand.message(Command("help"))
async def cmd_help(message: Message):
    """
    Обробка команди /help.

    Витягуємо з БД текст з описом доступних команд (BotMessage.key = "help_text").
    """
    session = SessionLocal()
    try:
        # Приклад шаблону:
        # key="help_text"
        # text="📘 <b>Допомога — доступні команди</b>\n━━━━━━━━━━━━..."
        text = render_bot_message(session, "help_text", lang="uk")
    finally:
        session.close()

    await message.answer(text, parse_mode="HTML")


# ====================== /edit ======================

@router_comand.message(Command("edit"))
async def cmd_edit(message: Message, state: FSMContext):
    """
    Обробка команди /edit.

    - якщо користувача ще немає в БД → пояснюємо, що треба спочатку пройти /start
      (BotMessage.key = "edit_user_not_found").
    - якщо користувач є → показуємо меню редагування (send_edit_menu).
    """
    session = SessionLocal()
    try:
        user = get_user_by_telegram_id(session, message.from_user.id)

        if user is None:
            # Текст при відсутності профілю
            # key="edit_user_not_found"
            text = render_bot_message(session, "edit_user_not_found", lang="uk")
            await message.answer(text, parse_mode="HTML")
            return

    finally:
        session.close()

    # Є користувач → показуємо меню редагування
    await state.set_state(EditProfileStates.menu)
    await send_edit_menu(message)


# ====================== /view ======================

@router_comand.message(Command("view"))
async def cmd_view(message: Message, state: FSMContext):
    """
    Обробка команди /view (перегляд власного профілю).

    - якщо профілю немає → показуємо повідомлення (BotMessage.key = "view_user_not_found").
    - якщо є → будуємо картку профілю та показуємо її (BotMessage.key = "view_profile_card"),
      а також окремим повідомленням підказуємо про /edit та /match
      (BotMessage.key = "view_suggest_edit_match").
    """
    session = SessionLocal()
    try:
        user = get_user_by_telegram_id(session, message.from_user.id)

        if user is None:
            # Повідомлення, якщо профіль ще не створений
            # key="view_user_not_found"
            text = render_bot_message(session, "view_user_not_found", lang="uk")
            await message.answer(text, parse_mode="HTML")
            return

        # -------- Нормалізація полів профілю --------
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

        # Інтереси в кілька рядків
        if user.interests:
            interests_lines = "\n".join(
                f"   • {html.escape(i)}" for i in user.interests
            )
            interests_block = f"\n{interests_lines}"
        else:
            interests_block = " не вказано"

        bio = user.bio or "не вказано"

        status_emoji = get_status_emoji(user.status)

        # Екрануємо текстові поля, щоб не зламати HTML
        name_safe = html.escape(name)
        nickname_safe = html.escape(nickname)
        region_safe = html.escape(region)
        place_safe = html.escape(place)
        status_safe = html.escape(status)
        bio_safe = html.escape(bio)

        # -------- Картка профілю з BotMessage --------
        # Приклад шаблону для key="view_profile_card":
        #
        # "<b>{status_emoji} Твій профіль</b>\n"
        # "━━━━━━━━━━━━━━━━━━━━\n"
        # "👩 <b>Ім'я:</b> {name}\n"
        # "✨ <b>Нікнейм:</b> {nickname}\n"
        # "📍 <b>Область:</b> {region}\n"
        # "📌 <b>Місто / село:</b> {place}\n"
        # "🎂 <b>Вік:</b> {age}\n"
        # "👶 <b>Статус:</b> {status}\n"
        # "🧩 <b>Інтереси:</b>{interests_block}\n"
        # "📜 <b>BIO:</b>\n{bio}\n"
        # "━━━━━━━━━━━━━━━━━━━━"
        text_profile = render_bot_message(
            session,
            "view_profile_card",
            lang="uk",
            status_emoji=status_emoji,
            name=name_safe,
            nickname=nickname_safe,
            region=region_safe,
            place=place_safe,
            age=age,
            status=status_safe,
            interests_block=interests_block,
            bio=bio_safe,
        )

        # Друге повідомлення з пропозицією /edit та /match
        # key="view_suggest_edit_match"
        # Наприклад:
        # "Хочеш щось змінити чи почати метчінг?\n"
        # "✏️ /edit — змінити дані анкети\n"
        # "🤝 /match — почати пошук мам (метчінг)\n"
        text_followup = render_bot_message(
            session,
            "view_suggest_edit_match",
            lang="uk",
        )

    finally:
        session.close()

    # Надсилаємо картку профілю
    await message.answer(text_profile, parse_mode="HTML")

    # Надсилаємо фоллоу-ап із підказками
    await message.answer(text_followup, parse_mode="HTML")


# ====================== /match ======================

@router_comand.message(Command("match"))
async def cmd_match(message: Message, state: FSMContext):
    """
    Обробка команди /match (початок метчингу).

    - якщо профілю немає → показуємо повідомлення (BotMessage.key = "match_user_not_found")
      і не пускаємо далі.
    - якщо профіль є → питаємо, за яким критерієм шукати (кнопки) +
      текст (BotMessage.key = "match_choose_criteria").
    """
    me_id = message.from_user.id
    session = SessionLocal()
    try:
        me = get_user_by_telegram_id(session, me_id)

        if me is None:
            # Повідомлення, якщо користувача немає в базі.
            # Цей же ключ використовується в run_match_flow.
            # key="match_user_not_found"
            text = render_bot_message(session, "match_user_not_found", lang="uk")
            await message.answer(text, parse_mode="HTML")
            return

        # Є користувач → питаємо критерій пошуку
        # Приклад шаблону:
        # key="match_choose_criteria"
        # text="Окей, давай підберемо тобі мам 🤝\nЗа яким критерієм хочеш шукати?"
        text_criteria = render_bot_message(
            session,
            "match_choose_criteria",
            lang="uk",
        )

    finally:
        session.close()

    await message.answer(
        text_criteria,
        reply_markup=build_match_criteria_kb(),
        parse_mode="HTML",
    )
    await state.set_state(MatchStates.criteria)
