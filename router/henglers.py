import math

from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, ReplyKeyboardRemove
from sqlalchemy.exc import IntegrityError

from config import VALID_REGIONS
from database import User, Choice, SessionLocal
from function import notify_match, run_match_flow, render_bot_message
from keyboard.reply import location_type_kb, PAGE_SIZE, build_regions_kb
from state import ProfileStates, MatchStates

router_hengler = Router()


# ====================== ВИБІР КРИТЕРІЮ МЕТЧУ ======================

# три хендлери під три критерії (по тексту кнопки)

@router_hengler.message(MatchStates.criteria, F.text == "📍 Місце проживання")
async def match_by_location(message: Message, state: FSMContext):
    """
    Старт метчингу за місцем проживання.
    """
    await run_match_flow(message, state, criterion="location")


@router_hengler.message(MatchStates.criteria, F.text == "📍Місце проживання + Інтереси 🧩")
async def match_by_location_interests(message: Message, state: FSMContext):
    """
    Старт метчингу за місцем проживання та спільними інтересами.
    """
    await run_match_flow(message, state, criterion="location_interests")


@router_hengler.message(MatchStates.criteria, F.text == "Інтереси 🧩")
async def match_by_interests(message: Message, state: FSMContext):
    """
    Старт метчингу тільки за спільними інтересами.
    """
    await run_match_flow(message, state, criterion="interests")


# ====================== ЛАЙК / ДИЗЛАЙК КАНДИДАТА ======================

@router_hengler.message(MatchStates.like_dislike, F.text == "👍 Лайк")
async def match_like_message(message: Message, state: FSMContext):
    """
    Обробка натискання "Лайк".

    Логіка:
    1. Дістаємо з FSM поточного кандидата та критерій.
    2. Зберігаємо лайк, якщо ще не збережений.
    3. Перевіряємо, чи є взаємний лайк.
       - якщо так → відправляємо обом повідомлення про метч (notify_match).
       - якщо ні → просто повідомляємо, що лайк збережено.
    4. Автоматично показуємо наступного кандидата за тим самим критерієм.
    """
    data = await state.get_data()
    candidate_id = data.get("current_candidate_id")
    criterion = data.get("current_criterion")

    session = SessionLocal()
    try:
        # Якщо щось не так з кандидатом / станом
        if not candidate_id:
            text_err = render_bot_message(
                session,
                "match_candidate_error",
                lang="uk",
            )
            # Наприклад: "Сталася помилка з кандидатом 😔"
            await message.answer(text_err, parse_mode="HTML")
            await state.clear()
            return

        me_id = message.from_user.id

        # Перевіряємо, чи вже є Choice для цієї пари
        existing = (
            session.query(Choice)
            .filter(
                Choice.chooser_id == me_id,
                Choice.chosen_id == candidate_id,
            )
            .one_or_none()
        )

        # Якщо ще не було вибору — зберігаємо лайк
        if existing is None:
            choice = Choice(
                chooser_id=me_id,
                chosen_id=candidate_id,
                choice_type="LIKE",
            )
            session.add(choice)
            session.commit()

        # Перевіряємо взаємний лайк
        mutual = (
            session.query(Choice)
            .filter(
                Choice.chooser_id == candidate_id,
                Choice.chosen_id == me_id,
                Choice.choice_type == "LIKE",
            )
            .one_or_none()
        )

        if mutual:
            # Є взаємний лайк → дістаємо обох користувачів
            user_me = session.get(User, me_id)
            user_other = session.get(User, candidate_id)

            if user_me and user_other:
                # Відправляємо обом красиве повідомлення про метч
                await notify_match(message.bot, user_me, user_other)

                text_mutual = render_bot_message(
                    session,
                    "match_mutual",
                    lang="uk",
                )
                # "Це взаємний лайк! 🎉"
                await message.answer(text_mutual, parse_mode="HTML")
            else:
                text_profiles_err = render_bot_message(
                    session,
                    "match_profiles_error",
                    lang="uk",
                )
                # "Метч, але щось пішло не так з профілями 🤔"
                await message.answer(text_profiles_err, parse_mode="HTML")
        else:
            # Просто зберегли лайк, але ще немає взаємного
            text_saved = render_bot_message(
                session,
                "match_like_saved",
                lang="uk",
            )
            # "Лайк збережено 💚"
            await message.answer(text_saved, parse_mode="HTML")

    except IntegrityError:
        # Якщо в БД стоїть унікальний індекс і лайк вже був
        session.rollback()
        text_exists = render_bot_message(
            session,
            "match_like_already_counted",
            lang="uk",
        )
        # "Цей лайк уже враховано 🙂"
        await message.answer(text_exists, parse_mode="HTML")
    finally:
        session.close()

    # 🔁 автоматично наступний кандидат за тим самим критерієм
    if criterion:
        await run_match_flow(message, state, criterion=criterion)
    else:
        # Немає критерію в стейті — завершуємо
        await state.clear()
        session = SessionLocal()
        try:
            text_again = render_bot_message(
                session,
                "match_run_again",
                lang="uk",
            )
            # "Щоб продовжити пошук, виконай /match ще раз 🙂"
        finally:
            session.close()

        await message.answer(text_again, parse_mode="HTML")


@router_hengler.message(MatchStates.like_dislike, F.text == "👎 Дизлайк")
async def match_dislike_message(message: Message, state: FSMContext):
    """
    Обробка натискання "Дизлайк".

    Зберігаємо вибір та переходимо до наступного кандидата.
    """
    data = await state.get_data()
    candidate_id = data.get("current_candidate_id")
    criterion = data.get("current_criterion")

    session = SessionLocal()
    try:
        if not candidate_id:
            text_err = render_bot_message(
                session,
                "match_candidate_error",
                lang="uk",
            )
            await message.answer(text_err, parse_mode="HTML")
            await state.clear()
            return

        me_id = message.from_user.id

        existing = (
            session.query(Choice)
            .filter(
                Choice.chooser_id == me_id,
                Choice.chosen_id == candidate_id,
            )
            .one_or_none()
        )

        # Якщо ще немає запису — додаємо DISLIKE
        if existing is None:
            choice = Choice(
                chooser_id=me_id,
                chosen_id=candidate_id,
                choice_type="DISLIKE",
            )
            session.add(choice)
            session.commit()

        text_saved = render_bot_message(
            session,
            "match_dislike_saved",
            lang="uk",
        )
        # "Дизлайк збережено 💔"
        await message.answer(text_saved, parse_mode="HTML")

    except IntegrityError:
        session.rollback()
        # Якщо хочеш, можна окреме повідомлення,
        # але зазвичай повторний дизлайк можна тихо ігнорити.
    finally:
        session.close()

    # 🔁 автоматично наступний кандидат за тим самим критерієм
    if criterion:
        await run_match_flow(message, state, criterion=criterion)
    else:
        await state.clear()
        session = SessionLocal()
        try:
            text_again = render_bot_message(
                session,
                "match_run_again",
                lang="uk",
            )
        finally:
            session.close()

        await message.answer(text_again, parse_mode="HTML")


@router_hengler.message(MatchStates.like_dislike, F.text == "⛔ Зупинити пошук")
async def match_stop_message(message: Message, state: FSMContext):
    """
    Зупиняє поточний пошук (метчинг) та очищає стан.
    """
    await state.clear()

    session = SessionLocal()
    try:
        text = render_bot_message(
            session,
            "match_stop",
            lang="uk",
        )
        # Наприклад:
        # "Зупиняю пошук мам 🤚\nЯкщо захочеш продовжити — просто надішли /match 💕"
    finally:
        session.close()

    await message.answer(
        text,
        reply_markup=ReplyKeyboardRemove(),
        parse_mode="HTML",
    )


# ====================== РЕЄСТРАЦІЯ: ОБЛАСТЬ (ДУБЛЬ ХЕНДЛЕР) ======================

@router_hengler.message(ProfileStates.region)
async def process_region(message: Message, state: FSMContext):
    """
    Обробка вибору області під час первинної реєстрації (ProfileStates.region).

    Цей хендлер дуже схожий на той, що в модулі анкети, але залишений тут,
    якщо ти спеціально розділяєш роутери.

    Підтримується:
    - пагінація (⬅️ Назад / Вперед ➡️)
    - скасувати
    - вибір області зі списку VALID_REGIONS
    """
    text = (message.text or "").strip()
    data = await state.get_data()
    page = data.get("regions_page", 0)

    session = SessionLocal()
    try:
        # пагінація назад
        if text == "⬅️ Назад":
            page = max(page - 1, 0)
            await state.update_data(regions_page=page)

            msg = render_bot_message(
                session,
                "profile_region_choose",
                lang="uk",
            )
            await message.answer(
                msg,
                reply_markup=build_regions_kb(page),
                parse_mode="HTML",
            )
            return

        # пагінація вперед
        if text == "Вперед ➡️":
            max_page = math.ceil(len(VALID_REGIONS) / PAGE_SIZE) - 1
            page = min(page + 1, max_page)
            await state.update_data(regions_page=page)

            msg = render_bot_message(
                session,
                "profile_region_choose",
                lang="uk",
            )
            await message.answer(
                msg,
                reply_markup=build_regions_kb(page),
                parse_mode="HTML",
            )
            return

        # скасувати реєстрацію
        if text == "Скасувати":
            await state.clear()
            cancel_text = render_bot_message(
                session,
                "profile_region_cancelled",
                lang="uk",
            )
            # "Добре, реєстрацію скасовано. Якщо захочеш — почни знову через /start 🙂"
            await message.answer(cancel_text, parse_mode="HTML")
            return

        # вибір області
        if text not in VALID_REGIONS:
            err_text = render_bot_message(
                session,
                "profile_region_not_found",
                lang="uk",
            )
            await message.answer(err_text, parse_mode="HTML")

            choose_text = render_bot_message(
                session,
                "profile_region_choose",
                lang="uk",
            )
            await message.answer(
                choose_text,
                reply_markup=build_regions_kb(page),
                parse_mode="HTML",
            )
            return

        # ✅ зберігаємо область у FSM
        await state.update_data(region=text)

        # повідомлення про обрану область (опційно)
        selected_text = render_bot_message(
            session,
            "profile_region_selected",
            lang="uk",
            region=text,
        )
        # "Область: {region}"
        await message.answer(selected_text, parse_mode="HTML")

        # далі — місто/село
        ask_loc_type = render_bot_message(
            session,
            "profile_ask_location_type",
            lang="uk",
        )
    finally:
        session.close()

    await message.answer(
        ask_loc_type,
        reply_markup=location_type_kb(),
        parse_mode="HTML",
    )
    await state.set_state(ProfileStates.location_type)
