import math
import re

from aiogram import Router, F
from aiogram.types import Message, ReplyKeyboardMarkup, ReplyKeyboardRemove, CallbackQuery
from aiogram.fsm.context import FSMContext

from database import SessionLocal
from function import get_user_by_telegram_id, send_edit_menu, render_bot_message
from keyboard.reply import (
    status_kb,
    location_type_kb,
    build_edit_interests_kb,
    build_regions_kb,
    PAGE_SIZE,
    edit_menu_kb,
)
from state import EditProfileStates
from config import VALID_REGIONS, STATUS_OPTIONS

edit_router = Router()


# ====================== СТАРТ МЕНЮ РЕДАГУВАННЯ ======================

@edit_router.message(EditProfileStates.menu, F.text == "Ім'я")
async def edit_name_start(message: Message, state: FSMContext):
    """
    Початок редагування імені.
    """
    session = SessionLocal()
    try:
        text = render_bot_message(session, "edit_name_start", lang="uk")
        # Приклад шаблону:
        # "Введи нове ім'я 🥰"
    finally:
        session.close()

    await message.answer(text, parse_mode="HTML")
    await state.set_state(EditProfileStates.name)


@edit_router.message(EditProfileStates.menu, F.text == "Нікнейм")
async def edit_nickname_start(message: Message, state: FSMContext):
    """
    Початок редагування нікнейму.
    """
    session = SessionLocal()
    try:
        text = render_bot_message(session, "edit_nickname_start", lang="uk")
        # "Введи новий нікнейм, який будуть бачити інші мами ✨"
    finally:
        session.close()

    await message.answer(text, parse_mode="HTML")
    await state.set_state(EditProfileStates.nickname)


@edit_router.message(EditProfileStates.menu, F.text == "Місце проживання")
async def edit_location_start(message: Message, state: FSMContext):
    """
    Початок редагування місця проживання.
    Перший крок — вибір області.
    """
    session = SessionLocal()
    try:
        text = render_bot_message(session, "edit_location_start", lang="uk")
        # Наприклад: "Тепер обери свою область зі списку нижче:"
    finally:
        session.close()

    await message.answer(
        text,
        reply_markup=build_regions_kb(page=0),
        parse_mode="HTML",
    )
    await state.set_state(EditProfileStates.region)


@edit_router.message(EditProfileStates.menu, F.text == "Вік")
async def edit_age_start(message: Message, state: FSMContext):
    """
    Початок редагування віку.
    """
    session = SessionLocal()
    try:
        text = render_bot_message(session, "edit_age_start", lang="uk")
        # "Напиши новий вік (лише число) 🎂"
    finally:
        session.close()

    await message.answer(text, parse_mode="HTML")
    await state.set_state(EditProfileStates.age)


@edit_router.message(EditProfileStates.menu, F.text == "Статус")
async def edit_status_start(message: Message, state: FSMContext):
    """
    Початок редагування статусу (мама / вагітна / інше).
    """
    session = SessionLocal()
    try:
        text = render_bot_message(session, "edit_status_start", lang="uk")
        # "Обери свій новий статус 👶"
    finally:
        session.close()

    await message.answer(
        text,
        reply_markup=status_kb(),
        parse_mode="HTML",
    )
    await state.set_state(EditProfileStates.status)


@edit_router.message(EditProfileStates.menu, F.text == "Інтереси")
async def edit_interests_start(message: Message, state: FSMContext):
    """
    Початок редагування інтересів.
    Підтягуємо поточні інтереси користувачки з БД.
    """
    session = SessionLocal()
    try:
        user = get_user_by_telegram_id(session, message.from_user.id)
        current_interests = user.interests or []

        text = render_bot_message(session, "edit_interests_start", lang="uk")
        # Наприклад:
        # "Оновимо інтереси 🧩\n"
        # "Натискай на пункти, щоб додати / прибрати.\n"
        # "Коли закінчиш — натисни «Готово ✅»."
    finally:
        session.close()

    await state.update_data(interests=current_interests)

    await message.answer(
        text,
        reply_markup=build_edit_interests_kb(current_interests),
        parse_mode="HTML",
    )
    await state.set_state(EditProfileStates.interests)


@edit_router.message(EditProfileStates.menu, F.text == "BIO")
async def edit_bio_start(message: Message, state: FSMContext):
    """
    Початок редагування BIO.
    """
    session = SessionLocal()
    try:
        text = render_bot_message(session, "edit_bio_start", lang="uk")
        # "Напиши новий BIO 📝\nТе, що будуть бачити інші мами:"
    finally:
        session.close()

    await message.answer(text, parse_mode="HTML")
    await state.set_state(EditProfileStates.bio)


@edit_router.message(EditProfileStates.menu)
async def edit_menu_fallback(message: Message, state: FSMContext):
    """
    Якщо користувач у меню редагування відправив щось незрозуміле.

    - Якщо це команда (/view, /match, /help, ...) — виходимо з режиму редагування.
    - Інакше — просимо обрати пункт з меню.
    """
    text = (message.text or "").strip()
    session = SessionLocal()

    try:
        # Якщо прийшла команда — виходимо з режиму редагування
        if text.startswith("/"):
            await state.clear()
            msg = render_bot_message(session, "edit_menu_exit", lang="uk")
            # "Вийшла з режиму редагування ✅\nМожеш користуватися командами далі 🙂"
            await message.answer(
                msg,
                reply_markup=ReplyKeyboardRemove(),
                parse_mode="HTML",
            )
            return

        # Будь-який інший текст — просимо обрати з меню
        msg = render_bot_message(session, "edit_menu_invalid", lang="uk")
        # "Будь ласка, обери, що хочеш змінити, з кнопок нижче ✏️"
        await message.answer(
            msg,
            reply_markup=edit_menu_kb(),
            parse_mode="HTML",
        )
    finally:
        session.close()


# ======================================================================
#  ЗБЕРЕЖЕННЯ ВВЕДЕНИХ ДАНИХ (ІМ'Я, НІКНЕЙМ, ВІК, СТАТУС, BIO, ЛОКАЦІЯ)
# ======================================================================

# ---------- ІМ'Я ----------

@edit_router.message(EditProfileStates.name)
async def edit_name_save(message: Message, state: FSMContext):
    """
    Збереження нового імені з валідацією.

    Використовуємо ті ж самі тексти, що й при первинній реєстрації:
    - profile_name_empty
    - profile_name_no_letter
    - profile_name_digits_only
    - profile_name_too_short
    """
    new_name = (message.text or "").strip()

    session = SessionLocal()
    try:
        # ❌ Порожній текст
        if not new_name:
            text = render_bot_message(session, "profile_name_empty", lang="uk")
            await message.answer(text, parse_mode="HTML")
            return

        # ❌ Має містити хоча б одну літеру
        if not re.search(r"[A-Za-zА-Яа-яЇїЄєІіҐґ]", new_name):
            text = render_bot_message(session, "profile_name_no_letter", lang="uk")
            await message.answer(text, parse_mode="HTML")
            return

        # ❌ Лише цифри
        if new_name.isdigit():
            text = render_bot_message(session, "profile_name_digits_only", lang="uk")
            await message.answer(text, parse_mode="HTML")
            return

        # ❌ Занадто коротке
        if len(new_name) < 2:
            text = render_bot_message(session, "profile_name_too_short", lang="uk")
            await message.answer(text, parse_mode="HTML")
            return

        # ✅ Зберігаємо в БД
        user = get_user_by_telegram_id(session, message.from_user.id)
        if user:
            user.name = new_name
            session.commit()

        # Повідомлення про успішне оновлення
        success_text = render_bot_message(
            session,
            "edit_name_saved",
            lang="uk",
            name=new_name,
        )
        # Наприклад: "Ім'я оновлено на: {name} ✅"
    finally:
        session.close()

    await message.answer(success_text, parse_mode="HTML")
    await state.set_state(EditProfileStates.menu)
    await send_edit_menu(message)


# ---------- НІКНЕЙМ ----------

@edit_router.message(EditProfileStates.nickname)
async def edit_nickname_save(message: Message, state: FSMContext):
    """
    Збереження нового нікнейму.
    """
    new_nickname = (message.text or "").strip()

    session = SessionLocal()
    try:
        user = get_user_by_telegram_id(session, message.from_user.id)
        if user:
            user.nickname = new_nickname
            session.commit()

        success_text = render_bot_message(
            session,
            "edit_nickname_saved",
            lang="uk",
            nickname=new_nickname,
        )
        # "Нікнейм оновлено на: {nickname} ✅"
    finally:
        session.close()

    await message.answer(success_text, parse_mode="HTML")
    await state.set_state(EditProfileStates.menu)
    await send_edit_menu(message)


# ---------- ОБЛАСТЬ / МІСЦЕ ПРОЖИВАННЯ (1/3 — ОБЛАСТЬ) ----------

@edit_router.message(EditProfileStates.region)
async def edit_region(message: Message, state: FSMContext):
    """
    Редагування області (з пагінацією).
    """
    text = (message.text or "").strip()
    data = await state.get_data()
    page = data.get("regions_page", 0)

    session = SessionLocal()
    try:
        # 🔹 Пагінація: назад
        if text == "⬅️ Назад":
            page = max(page - 1, 0)
            await state.update_data(regions_page=page)

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

        # 🔹 Пагінація: вперед
        if text == "Вперед ➡️":
            max_page = math.ceil(len(VALID_REGIONS) / PAGE_SIZE) - 1
            page = min(page + 1, max_page)
            await state.update_data(regions_page=page)

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

        # 🔹 Скасувати
        if text == "Скасувати":
            await state.clear()
            cancel_text = render_bot_message(
                session,
                "edit_region_cancelled",
                lang="uk",
            )
            # Наприклад: "Зміна місця проживання скасована 🙂"
            await message.answer(cancel_text, parse_mode="HTML")
            return

        # 🔹 Вибір області з кнопок
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

        # ✅ Коректна область — зберігаємо у стейт і переходимо до типу населеного пункту
        region = text
        await state.update_data(region=region)

        ask_loc_type = render_bot_message(
            session,
            "profile_ask_location_type",
            lang="uk",
        )
        await message.answer(
            ask_loc_type,
            reply_markup=location_type_kb(),
            parse_mode="HTML",
        )
        await state.set_state(EditProfileStates.location_type)

    finally:
        session.close()


# ---------- МІСЦЕ ПРОЖИВАННЯ (2/3 — ТИП: МІСТО / СЕЛО) ----------

@edit_router.message(EditProfileStates.location_type)
async def edit_location_type(message: Message, state: FSMContext):
    """
    Обираємо, чи живе мама в місті чи в селі.
    """
    text = (message.text or "").strip().lower()
    session = SessionLocal()

    try:
        if text == "місто":
            await state.update_data(location_type="city")

            msg = render_bot_message(session, "profile_ask_city", lang="uk")
            await message.answer(
                msg,
                reply_markup=ReplyKeyboardMarkup(
                    keyboard=[],
                    resize_keyboard=True,
                ),
                parse_mode="HTML",
            )
            await state.set_state(EditProfileStates.city)

        elif text == "село":
            await state.update_data(location_type="village")

            msg = render_bot_message(session, "profile_ask_village", lang="uk")
            await message.answer(
                msg,
                reply_markup=ReplyKeyboardMarkup(
                    keyboard=[],
                    resize_keyboard=True,
                ),
                parse_mode="HTML",
            )
            await state.set_state(EditProfileStates.village)

        else:
            err_text = render_bot_message(
                session,
                "profile_location_type_invalid",
                lang="uk",
            )
            await message.answer(
                err_text,
                reply_markup=location_type_kb(),
                parse_mode="HTML",
            )

    finally:
        session.close()


# ---------- МІСЦЕ ПРОЖИВАННЯ (3/3 — ЗБЕРЕЖЕННЯ МІСТА) ----------

@edit_router.message(EditProfileStates.city)
async def edit_city_save(message: Message, state: FSMContext):
    """
    Збереження нового міста + регіону.
    """
    city = (message.text or "").strip()
    data = await state.get_data()
    region = data.get("region")

    session = SessionLocal()
    try:
        user = get_user_by_telegram_id(session, message.from_user.id)
        if user:
            user.region = region
            user.city = city
            user.village = None
            session.commit()

        success_text = render_bot_message(
            session,
            "edit_city_saved",
            lang="uk",
            region=region,
            city=city,
        )
        # "Місце проживання оновлено: {region}, місто {city} ✅"
    finally:
        session.close()

    await message.answer(success_text, parse_mode="HTML")
    await state.set_state(EditProfileStates.menu)
    await send_edit_menu(message)


# ---------- МІСЦЕ ПРОЖИВАННЯ (3/3 — ЗБЕРЕЖЕННЯ СЕЛА) ----------

@edit_router.message(EditProfileStates.village)
async def edit_village_save(message: Message, state: FSMContext):
    """
    Збереження нового села + регіону.
    """
    village = (message.text or "").strip()
    data = await state.get_data()
    region = data.get("region")

    session = SessionLocal()
    try:
        user = get_user_by_telegram_id(session, message.from_user.id)
        if user:
            user.region = region
            user.village = village
            user.city = None
            session.commit()

        success_text = render_bot_message(
            session,
            "edit_village_saved",
            lang="uk",
            region=region,
            village=village,
        )
        # "Місце проживання оновлено: {region}, село {village} ✅"
    finally:
        session.close()

    await message.answer(success_text, parse_mode="HTML")
    await state.set_state(EditProfileStates.menu)
    await send_edit_menu(message)


# ---------- ВІК ----------

@edit_router.message(EditProfileStates.age)
async def edit_age_save(message: Message, state: FSMContext):
    """
    Збереження нового віку (з перевірками, як при реєстрації).
    """
    text = (message.text or "").strip()
    session = SessionLocal()

    try:
        if not text.isdigit():
            err_text = render_bot_message(
                session,
                "profile_age_not_digit",
                lang="uk",
            )
            await message.answer(err_text, parse_mode="HTML")
            return

        age = int(text)
        if age < 14 or age > 60:
            err_text = render_bot_message(
                session,
                "profile_age_out_of_range",
                lang="uk",
            )
            await message.answer(err_text, parse_mode="HTML")
            return

        # Зберігаємо
        user = get_user_by_telegram_id(session, message.from_user.id)
        if user:
            user.age = age
            session.commit()

        success_text = render_bot_message(
            session,
            "edit_age_saved",
            lang="uk",
            age=age,
        )
        # "Вік оновлено на: {age} ✅"
    finally:
        session.close()

    await message.answer(success_text, parse_mode="HTML")
    await state.set_state(EditProfileStates.menu)
    await send_edit_menu(message)


# ---------- СТАТУС ----------

@edit_router.message(EditProfileStates.status)
async def edit_status_save(message: Message, state: FSMContext):
    """
    Збереження нового статусу.
    """
    status = (message.text or "").strip()
    session = SessionLocal()

    try:
        if status not in STATUS_OPTIONS:
            err_text = render_bot_message(
                session,
                "profile_status_invalid",
                lang="uk",
            )
            await message.answer(
                err_text,
                reply_markup=status_kb(),
                parse_mode="HTML",
            )
            return

        user = get_user_by_telegram_id(session, message.from_user.id)
        if user:
            user.status = status
            session.commit()

        success_text = render_bot_message(
            session,
            "edit_status_saved",
            lang="uk",
            status=status,
        )
        # "Статус оновлено на: {status} ✅"
    finally:
        session.close()

    await message.answer(success_text, parse_mode="HTML")
    await state.set_state(EditProfileStates.menu)
    await send_edit_menu(message)


# ---------- ІНТЕРЕСИ (ТОГЛ ЧЕРЕЗ CALLBACK) ----------

@edit_router.callback_query(EditProfileStates.interests, F.data.startswith("edit_interest:"))
async def edit_toggle_interest(callback: CallbackQuery, state: FSMContext):
    """
    Тогл (вкл/викл) інтересу при редагуванні.
    """
    interest = callback.data.split(":", 1)[1]

    data = await state.get_data()
    selected = set(data.get("interests", []))

    if interest in selected:
        selected.remove(interest)
    else:
        selected.add(interest)

    selected_list = list(selected)
    await state.update_data(interests=selected_list)

    await callback.message.edit_reply_markup(
        reply_markup=build_edit_interests_kb(selected_list)
    )
    await callback.answer()


@edit_router.callback_query(EditProfileStates.interests, F.data == "edit_interests_done")
async def edit_interests_done(callback: CallbackQuery, state: FSMContext):
    """
    Завершення редагування інтересів:
    - якщо нічого не обрано → показуємо alert
    - інакше зберігаємо в БД і повертаємося до меню редагування
    """
    data = await state.get_data()
    selected = data.get("interests", [])

    session = SessionLocal()
    try:
        if not selected:
            # alert-текст (plain, без HTML)
            alert_text = render_bot_message(
                session,
                "profile_interests_empty",
                lang="uk",
            )
            await callback.answer(alert_text, show_alert=True)
            return

        user = get_user_by_telegram_id(session, callback.from_user.id)
        if user:
            user.interests = selected
            session.commit()

        success_text = render_bot_message(
            session,
            "edit_interests_saved",
            lang="uk",
        )
        # "Інтереси оновлено ✅\nТепер я ще краще зможу підбирати мам за спільними темами 🧩"
    finally:
        session.close()

    await callback.message.answer(success_text, parse_mode="HTML")

    await state.set_state(EditProfileStates.menu)
    await send_edit_menu(callback.message)
    await callback.answer()


# ---------- BIO ----------

@edit_router.message(EditProfileStates.bio)
async def edit_bio_save(message: Message, state: FSMContext):
    """
    Збереження нового BIO.
    """
    new_bio = (message.text or "").strip()

    session = SessionLocal()
    try:
        user = get_user_by_telegram_id(session, message.from_user.id)
        if user:
            user.bio = new_bio
            session.commit()

        success_text = render_bot_message(
            session,
            "edit_bio_saved",
            lang="uk",
        )
        # "BIO оновлено ✅"
    finally:
        session.close()

    await message.answer(success_text, parse_mode="HTML")
    await state.set_state(EditProfileStates.menu)
    await send_edit_menu(message)
