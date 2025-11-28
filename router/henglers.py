import math

from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, ReplyKeyboardRemove
from sqlalchemy.exc import IntegrityError

from config import VALID_REGIONS
from database import User, Choice, SessionLocal
from function import notify_match, run_match_flow
from keyboard.reply import location_type_kb, PAGE_SIZE, build_regions_kb
from state import ProfileStates, MatchStates

# send_edit_menu вже є у нас з /edit
router_hengler = Router()


# три хендлери під три критерії (по тексту кнопки)
@router_hengler.message(MatchStates.criteria, F.text == "📍 Місце проживання")
async def match_by_location(message: Message, state: FSMContext):
    await run_match_flow(message, state, criterion="location")


@router_hengler.message(MatchStates.criteria, F.text == "📍+🧩 Місце + інтереси")
async def match_by_status(message: Message, state: FSMContext):
    await run_match_flow(message, state, criterion="location_interests")


@router_hengler.message(MatchStates.criteria, F.text == "🧩 Інтереси")
async def match_by_interests(message: Message, state: FSMContext):
    await run_match_flow(message, state, criterion="interests")


@router_hengler.message(MatchStates.like_dislike, F.text == "👍 Лайк")
async def match_like_message(message: Message, state: FSMContext):
    data = await state.get_data()
    candidate_id = data.get("current_candidate_id")
    criterion = data.get("current_criterion")

    if not candidate_id:
        await message.answer("Сталася помилка з кандидатом 😔")
        await state.clear()
        return

    me_id = message.from_user.id

    session = SessionLocal()
    try:
        existing = (
            session.query(Choice)
            .filter(
                Choice.chooser_id == me_id,
                Choice.chosen_id == candidate_id,
            )
            .one_or_none()
        )

        if existing is None:
            choice = Choice(
                chooser_id=me_id,
                chosen_id=candidate_id,
                choice_type="LIKE",
            )
            session.add(choice)
            session.commit()

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
            user_me = session.get(User, me_id)
            user_other = session.get(User, candidate_id)

            if user_me and user_other:
                await notify_match(message.bot, user_me, user_other)
                await message.answer("Це взаємний лайк! 🎉")
            else:
                await message.answer("Метч, але щось пішло не так з профілями 🤔")
        else:
            await message.answer("Лайк збережено 💚")

    except IntegrityError:
        session.rollback()
        await message.answer("Цей лайк уже враховано 🙂")
    finally:
        session.close()

    # 🔁 автоматично наступний кандидат за тим самим критерієм
    if criterion:
        await run_match_flow(message, state, criterion=criterion)
    else:
        await state.clear()
        await message.answer("Щоб продовжити пошук, виконай /match ще раз 🙂")


@router_hengler.message(MatchStates.like_dislike, F.text == "👎 Дизлайк")
async def match_dislike_message(message: Message, state: FSMContext):
    data = await state.get_data()
    candidate_id = data.get("current_candidate_id")
    criterion = data.get("current_criterion")

    if not candidate_id:
        await message.answer("Сталася помилка з кандидатом 😔")
        await state.clear()
        return

    me_id = message.from_user.id

    session = SessionLocal()
    try:
        existing = (
            session.query(Choice)
            .filter(
                Choice.chooser_id == me_id,
                Choice.chosen_id == candidate_id,
            )
            .one_or_none()
        )

        if existing is None:
            choice = Choice(
                chooser_id=me_id,
                chosen_id=candidate_id,
                choice_type="DISLIKE",
            )
            session.add(choice)
            session.commit()

    except IntegrityError:
        session.rollback()
    finally:
        session.close()

    await message.answer("Дизлайк збережено 💔")

    # 🔁 автоматично наступний кандидат за тим самим критерієм
    if criterion:
        await run_match_flow(message, state, criterion=criterion)
    else:
        await state.clear()
        await message.answer("Щоб продовжити пошук, виконай /match ще раз 🙂")


@router_hengler.message(MatchStates.like_dislike, F.text == "⛔ Зупинити пошук")
async def match_stop_message(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(
        "Зупиняю пошук мам 🤚\n"
        "Якщо захочеш продовжити — просто надішли /match 💕",
        reply_markup=ReplyKeyboardRemove(),
    )


@router_hengler.message(ProfileStates.region)
async def process_region(message: Message, state: FSMContext):
    text = message.text.strip()
    data = await state.get_data()
    page = data.get("regions_page", 0)

    # пагінація
    if text == "⬅️ Назад":
        page = max(page - 1, 0)
        await state.update_data(regions_page=page)
        await message.answer(
            "Обери, будь ласка, область:",
            reply_markup=build_regions_kb(page),
        )
        return

    if text == "Вперед ➡️":
        max_page = math.ceil(len(VALID_REGIONS) / PAGE_SIZE) - 1
        page = min(page + 1, max_page)
        await state.update_data(regions_page=page)
        await message.answer(
            "Обери, будь ласка, область:",
            reply_markup=build_regions_kb(page),
        )
        return

    if text == "Скасувати":
        await state.clear()
        await message.answer("Добре, реєстрацію скасовано. Можеш почати знову через /start.")
        return

    # вибір області
    if text not in VALID_REGIONS:
        await message.answer(
            "Я не знайшла такої області 😔\n"
            "Будь ласка, обери область кнопкою зі списку."
        )
        await message.answer(
            "Обери, будь ласка, область:",
            reply_markup=build_regions_kb(page),
        )
        return

    await state.update_data(region=text)

    await message.answer(
        f"Область: {text}",
    )

    # далі — місто/село
    await message.answer(
        "Ти живеш у місті чи селі?",
        reply_markup=location_type_kb(),
    )
    await state.set_state(ProfileStates.location_type)
