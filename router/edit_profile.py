from aiogram import Router, F
from aiogram.types import Message
from aiogram.fsm.context import FSMContext
from database import SessionLocal
from function import get_user_by_telegram_id, send_edit_menu
from keyboard.reply import status_kb, location_type_kb, build_edit_interests_kb, build_regions_kb, PAGE_SIZE, \
    edit_menu_kb
from state import EditProfileStates
from aiogram.types import ReplyKeyboardMarkup, ReplyKeyboardRemove
from config import VALID_REGIONS, STATUS_OPTIONS
from aiogram.types import CallbackQuery
import math
import re
edit_router = Router()





@edit_router.message(EditProfileStates.menu, F.text == "Ім'я")
async def edit_name_start(message: Message, state: FSMContext):
    await message.answer("Введи нове ім'я 🥰")
    await state.set_state(EditProfileStates.name)


@edit_router.message(EditProfileStates.menu, F.text == "Нікнейм")
async def edit_nickname_start(message: Message, state: FSMContext):
    await message.answer("Введи новий нікнейм, який будуть бачити інші мами ✨")
    await state.set_state(EditProfileStates.nickname)


@edit_router.message(EditProfileStates.menu, F.text == "Місце проживання")
async def edit_location_start(message: Message, state: FSMContext):
    await message.answer(
        "Тепер обери свою область зі списку нижче:",
        reply_markup=build_regions_kb(page=0),
    )
    await state.set_state(EditProfileStates.region)


@edit_router.message(EditProfileStates.menu, F.text == "Вік")
async def edit_age_start(message: Message, state: FSMContext):
    await message.answer("Напиши новий вік (лише число) 🎂")
    await state.set_state(EditProfileStates.age)


@edit_router.message(EditProfileStates.menu, F.text == "Статус")
async def edit_status_start(message: Message, state: FSMContext):
    await message.answer("Обери свій новий статус 👶", reply_markup=status_kb())
    await state.set_state(EditProfileStates.status)


@edit_router.message(EditProfileStates.menu, F.text == "Інтереси")
async def edit_interests_start(message: Message, state: FSMContext):
    session = SessionLocal()
    try:
        user = get_user_by_telegram_id(session, message.from_user.id)
        current_interests = user.interests or []
    finally:
        session.close()

    await state.update_data(interests=current_interests)

    await message.answer(
        "Оновимо інтереси 🧩\n"
        "Натискай на пункти, щоб додати / прибрати.\n"
        "Коли закінчиш — натисни «Готово ✅».",
        reply_markup=build_edit_interests_kb(current_interests),
    )
    await state.set_state(EditProfileStates.interests)


@edit_router.message(EditProfileStates.menu, F.text == "BIO")
async def edit_bio_start(message: Message, state: FSMContext):
    await message.answer("Напиши новий BIO 📝\nТе, що будуть бачити інші мами:")
    await state.set_state(EditProfileStates.bio)


@edit_router.message(EditProfileStates.menu)
async def edit_menu_fallback(message: Message, state: FSMContext):
    text = (message.text or "").strip()

    # Якщо прийшла якась команда типу /view, /match, /help і т.д.
    if text.startswith("/"):
        await state.clear()
        await message.answer(
            "Вийшла з режиму редагування ✅\n"
            "Можеш користуватися командами далі 🙂",
            reply_markup=ReplyKeyboardRemove(),
        )
        # команду юзер надішле ще раз вже поза станом
        return

    # Будь-який інший текст — просимо обрати з меню
    await message.answer(
        "Будь ласка, обери, що хочеш змінити, з кнопок нижче ✏️",
        reply_markup=edit_menu_kb(),
    )


"""
Зберер логіки для обробки введених нових даних користувача
(ім'я, нікнейм, вік, статус, BIO, місце проживання)"""


@edit_router.message(EditProfileStates.name)
async def edit_name_save(message: Message, state: FSMContext):
    new_name = message.text.strip()

    # ❌ Забороняємо пустий текст
    if not new_name:
        await message.answer("Будь ласка, введи ім’я 🙂")
        return

    # ❌ Має містити хоча б одну літеру
    if not re.search(r"[A-Za-zА-Яа-яЇїЄєІіҐґ]", new_name):
        await message.answer("Ім’я повинно містити хоча б одну букву 🙂")
        return

    # ❌ Забороняємо тільки числа
    if new_name.isdigit():
        await message.answer("Ім’я не може складатися лише з цифр 🙂")
        return

    # ❌ Мінімальна довжина
    if len(new_name) < 2:
        await message.answer("Ім’я має містити хоча б 2 літери 🙂")
        return

    # ✅ Зберігаємо
    session = SessionLocal()
    try:
        user = get_user_by_telegram_id(session, message.from_user.id)
        if user:
            user.name = new_name
            session.commit()
    finally:
        session.close()

    await message.answer(f"Ім'я оновлено на: {new_name} ✅")
    await state.set_state(EditProfileStates.menu)
    await send_edit_menu(message)


@edit_router.message(EditProfileStates.nickname)
async def edit_nickname_save(message: Message, state: FSMContext):
    new_nickname = message.text.strip()

    session = SessionLocal()
    try:
        user = get_user_by_telegram_id(session, message.from_user.id)
        if user:
            user.nickname = new_nickname
            session.commit()
    finally:
        session.close()

    await message.answer(f"Нікнейм оновлено на: {new_nickname} ✅")
    await state.set_state(EditProfileStates.menu)
    await send_edit_menu(message)


@edit_router.message(EditProfileStates.region)
async def edit_region(message: Message, state: FSMContext):
    text = message.text.strip()
    data = await state.get_data()
    page = data.get("regions_page", 0)

    # 🔹 Пагінація: назад
    if text == "⬅️ Назад":
        page = max(page - 1, 0)
        await state.update_data(regions_page=page)
        await message.answer(
            "Обери, будь ласка, область:",
            reply_markup=build_regions_kb(page),
        )
        return

    # 🔹 Пагінація: вперед
    if text == "Вперед ➡️":
        max_page = math.ceil(len(VALID_REGIONS) / PAGE_SIZE) - 1
        page = min(page + 1, max_page)
        await state.update_data(regions_page=page)
        await message.answer(
            "Обери, будь ласка, область:",
            reply_markup=build_regions_kb(page),
        )
        return

    # 🔹 Скасувати
    if text == "Скасувати":
        await state.clear()
        await message.answer(
            "Добре, реєстрацію скасовано. "
            "Якщо захочеш — почни знову через /start 🙂"
        )
        return

    # 🔹 Вибір області з кнопок
    if text not in VALID_REGIONS:
        await message.answer(
            "Я не знайшла такої області 😔\n"
            "Будь ласка, обери область кнопкою зі списку.",
        )
        await message.answer(
            "Обери область:",
            reply_markup=build_regions_kb(page),
        )
        return

    region = text
    await state.update_data(region=region)

    await message.answer(
        "Ти живеш у місті чи селі?",
        reply_markup=location_type_kb(),
    )
    await state.set_state(EditProfileStates.location_type)


@edit_router.message(EditProfileStates.location_type)
async def edit_location_type(message: Message, state: FSMContext):
    text = message.text.strip().lower()

    if text == "місто":
        await state.update_data(location_type="city")
        await message.answer(
            "Введи, будь ласка, назву міста 🌆",
            reply_markup=ReplyKeyboardMarkup(keyboard=[], resize_keyboard=True),
        )
        await state.set_state(EditProfileStates.city)

    elif text == "село":
        await state.update_data(location_type="village")
        await message.answer(
            "Введи, будь ласка, назву села 🌿",
            reply_markup=ReplyKeyboardMarkup(keyboard=[], resize_keyboard=True),
        )
        await state.set_state(EditProfileStates.village)

    else:
        await message.answer(
            "Будь ласка, обери *Місто* або *Село* з кнопок нижче 🙂",
            parse_mode="Markdown",
            reply_markup=location_type_kb(),
        )


@edit_router.message(EditProfileStates.city)
async def edit_city_save(message: Message, state: FSMContext):
    city = message.text.strip()
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
    finally:
        session.close()

    await message.answer(f"Місце проживання оновлено: {region}, місто {city} ✅")
    await state.set_state(EditProfileStates.menu)
    await send_edit_menu(message)


@edit_router.message(EditProfileStates.village)
async def edit_village_save(message: Message, state: FSMContext):
    village = message.text.strip()
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
    finally:
        session.close()

    await message.answer(f"Місце проживання оновлено: {region}, село {village} ✅")
    await state.set_state(EditProfileStates.menu)
    await send_edit_menu(message)


@edit_router.message(EditProfileStates.age)
async def edit_age_save(message: Message, state: FSMContext):
    text = message.text.strip()

    if not text.isdigit():
        await message.answer("Будь ласка, напиши вік *цифрами* 🙂", parse_mode="Markdown")
        return

    age = int(text)
    if age < 14 or age > 60:
        await message.answer("Вкажи, будь ласка, реальний вік у межах 14–60 років 🙂")
        return

    session = SessionLocal()
    try:
        user = get_user_by_telegram_id(session, message.from_user.id)
        if user:
            user.age = age
            session.commit()
    finally:
        session.close()

    await message.answer(f"Вік оновлено на: {age} ✅")
    await state.set_state(EditProfileStates.menu)
    await send_edit_menu(message)


@edit_router.message(EditProfileStates.status)
async def edit_status_save(message: Message, state: FSMContext):
    status = message.text.strip()

    if status not in STATUS_OPTIONS:
        await message.answer(
            "Будь ласка, обери статус за допомогою кнопок 🙂",
            reply_markup=status_kb(),
        )
        return

    session = SessionLocal()
    try:
        user = get_user_by_telegram_id(session, message.from_user.id)
        if user:
            user.status = status
            session.commit()
    finally:
        session.close()

    await message.answer(f"Статус оновлено на: {status} ✅")
    await state.set_state(EditProfileStates.menu)
    await send_edit_menu(message)


@edit_router.callback_query(EditProfileStates.interests, F.data.startswith("edit_interest:"))
async def edit_toggle_interest(callback: CallbackQuery, state: FSMContext):
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
    data = await state.get_data()
    selected = data.get("interests", [])

    if not selected:
        await callback.answer(
            "Будь ласка, обери хоча б один інтерес 🙂", show_alert=True
        )
        return

    session = SessionLocal()
    try:
        user = get_user_by_telegram_id(session, callback.from_user.id)
        if user:
            user.interests = selected
            session.commit()
    finally:
        session.close()

    await callback.message.answer(
        "Інтереси оновлено ✅\n"
        "Тепер я ще краще зможу підбирати мам за спільними темами 🧩"
    )

    await state.set_state(EditProfileStates.menu)
    await send_edit_menu(callback.message)
    await callback.answer()


@edit_router.message(EditProfileStates.bio)
async def edit_bio_save(message: Message, state: FSMContext):
    new_bio = message.text.strip()

    session = SessionLocal()
    try:
        user = get_user_by_telegram_id(session, message.from_user.id)
        if user:
            user.bio = new_bio
            session.commit()
    finally:
        session.close()

    await message.answer("BIO оновлено ✅")
    await state.set_state(EditProfileStates.menu)
    await send_edit_menu(message)
