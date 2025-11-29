import math
import re

from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    Message,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
)

from config import VALID_REGIONS, STATUS_OPTIONS, INTEREST_OPTIONS
from database import SessionLocal
from function import save_user_profile_from_state, render_bot_message
from keyboard.reply import (
    location_type_kb,
    status_kb,
    build_interests_kb,
    confirm_kb,
    build_regions_kb,
    PAGE_SIZE,
    edit_menu_kb,
)
from state import ProfileStates, EditProfileStates

router_state = Router()


# ====================== 1. ІМ'Я ======================

@router_state.message(ProfileStates.name)
async def process_name(message: Message, state: FSMContext):
    """
    Перший крок анкети — ім'я.

    Валідуємо:
    - не порожнє
    - містить хоча б одну літеру
    - не складається лише з цифр
    - довжина не менше 2 символів

    Усі тексти беремо з BotMessage:
      - profile_name_empty
      - profile_name_no_letter
      - profile_name_digits_only
      - profile_name_too_short
      - profile_ask_nickname
    """
    name = (message.text or "").strip()
    session = SessionLocal()

    try:
        # ❌ Порожній текст
        if not name:
            text = render_bot_message(session, "profile_name_empty", lang="uk")
            await message.answer(text, parse_mode="HTML")
            return

        # ❌ Немає жодної літери
        if not re.search(r"[A-Za-zА-Яа-яЇїЄєІіҐґ]", name):
            text = render_bot_message(session, "profile_name_no_letter", lang="uk")
            await message.answer(text, parse_mode="HTML")
            return

        # ❌ Лише цифри
        if name.isdigit():
            text = render_bot_message(session, "profile_name_digits_only", lang="uk")
            await message.answer(text, parse_mode="HTML")
            return

        # ❌ Занадто коротке
        if len(name) < 2:
            text = render_bot_message(session, "profile_name_too_short", lang="uk")
            await message.answer(text, parse_mode="HTML")
            return

        # ✅ Усе добре — зберігаємо ім'я в стан
        await state.update_data(name=name)

        text = render_bot_message(session, "profile_ask_nickname", lang="uk")
        await message.answer(text, parse_mode="HTML")
        await state.set_state(ProfileStates.nickname)

    finally:
        session.close()


# ====================== 2. НІКНЕЙМ ======================

@router_state.message(ProfileStates.nickname)
async def process_nickname(message: Message, state: FSMContext):
    """
    Обробка нікнейму (другий крок анкети).

    Після збереження нікнейму одразу показуємо клавіатуру з областями.
    Текст для запиту області — profile_region_choose.
    """
    await state.update_data(nickname=(message.text or "").strip())

    session = SessionLocal()
    try:
        text = render_bot_message(session, "profile_region_choose", lang="uk")
    finally:
        session.close()

    await message.answer(
        text,
        reply_markup=build_regions_kb(page=0),
        parse_mode="HTML",
    )
    await state.set_state(ProfileStates.region)


# ====================== 3. ОБЛАСТЬ ======================

@router_state.message(ProfileStates.region)
async def process_region(message: Message, state: FSMContext):
    """
    Вибір області з пагінацією.

    Кнопки:
    - "⬅️ Назад"  – попередня сторінка
    - "Вперед ➡️" – наступна сторінка
    - "Скасувати" – відміна реєстрації
    - інші         – назва області зі списку VALID_REGIONS
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

            msg_text = render_bot_message(session, "profile_region_choose", lang="uk")
            await message.answer(
                msg_text,
                reply_markup=build_regions_kb(page),
                parse_mode="HTML",
            )
            return

        # 🔹 Пагінація: вперед
        if text == "Вперед ➡️":
            max_page = math.ceil(len(VALID_REGIONS) / PAGE_SIZE) - 1
            page = min(page + 1, max_page)
            await state.update_data(regions_page=page)

            msg_text = render_bot_message(session, "profile_region_choose", lang="uk")
            await message.answer(
                msg_text,
                reply_markup=build_regions_kb(page),
                parse_mode="HTML",
            )
            return

        # 🔹 Скасувати
        if text == "Скасувати":
            msg_text = render_bot_message(session, "profile_region_cancelled", lang="uk")
            await state.clear()
            await message.answer(msg_text, parse_mode="HTML")
            return

        # 🔹 Вибір області з кнопок
        if text not in VALID_REGIONS:
            # Повідомлення про помилку
            err_text = render_bot_message(session, "profile_region_not_found", lang="uk")
            await message.answer(err_text, parse_mode="HTML")

            # Повторно просимо обрати область
            choose_text = render_bot_message(session, "profile_region_choose", lang="uk")
            await message.answer(
                choose_text,
                reply_markup=build_regions_kb(page),
                parse_mode="HTML",
            )
            return

        # ✅ Коректна область
        region = text
        await state.update_data(region=region)

        # "Область: {region}"
        region_text = render_bot_message(
            session,
            "profile_region_selected",
            lang="uk",
            region=region,
        )
        await message.answer(region_text, parse_mode="HTML")

        # Запитуємо тип населеного пункту
        ask_loc_type = render_bot_message(session, "profile_ask_location_type", lang="uk")
        await message.answer(
            ask_loc_type,
            reply_markup=location_type_kb(),
            parse_mode="HTML",
        )
        await state.set_state(ProfileStates.location_type)

    finally:
        session.close()


# ====================== 4. ТИП НАСЕЛЕНОГО ПУНКТУ ======================

@router_state.message(ProfileStates.location_type)
async def process_location_type(message: Message, state: FSMContext):
    """
    Обираємо, де живе користувач:
    - "місто"
    - "село"

    Якщо введено щось інше — просимо обрати з кнопок.
    """
    text = (message.text or "").strip().lower()
    session = SessionLocal()

    try:
        if text == "місто":
            await state.update_data(location_type="city")

            msg_text = render_bot_message(session, "profile_ask_city", lang="uk")
            await message.answer(
                msg_text,
                reply_markup=ReplyKeyboardMarkup(
                    keyboard=[],
                    resize_keyboard=True,
                ),
                parse_mode="HTML",
            )
            await state.set_state(ProfileStates.city)

        elif text == "село":
            await state.update_data(location_type="village")

            msg_text = render_bot_message(session, "profile_ask_village", lang="uk")
            await message.answer(
                msg_text,
                reply_markup=ReplyKeyboardMarkup(
                    keyboard=[],
                    resize_keyboard=True,
                ),
                parse_mode="HTML",
            )
            await state.set_state(ProfileStates.village)

        else:
            # Некоректна відповідь — просимо обрати з кнопок
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


# ====================== 5. МІСТО ======================

@router_state.message(ProfileStates.city)
async def process_city(message: Message, state: FSMContext):
    """
    Зберігаємо назву міста та переходимо до віку.
    """
    await state.update_data(city=(message.text or "").strip(), village=None)

    session = SessionLocal()
    try:
        msg_text = render_bot_message(session, "profile_ask_age", lang="uk")
    finally:
        session.close()

    await message.answer(msg_text, parse_mode="HTML")
    await state.set_state(ProfileStates.age)


# ====================== 6. СЕЛО ======================

@router_state.message(ProfileStates.village)
async def process_village(message: Message, state: FSMContext):
    """
    Зберігаємо назву села та переходимо до віку.
    """
    await state.update_data(village=(message.text or "").strip(), city=None)

    session = SessionLocal()
    try:
        msg_text = render_bot_message(session, "profile_ask_age", lang="uk")
    finally:
        session.close()

    await message.answer(msg_text, parse_mode="HTML")
    await state.set_state(ProfileStates.age)


# ====================== 7. ВІК ======================

@router_state.message(ProfileStates.age)
async def process_age(message: Message, state: FSMContext):
    """
    Обробка віку. Приймаємо лише числа в межах 14–60.
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

        await state.update_data(age=age)

        # Питаємо статус
        ask_status = render_bot_message(session, "profile_ask_status", lang="uk")
        await message.answer(
            ask_status,
            reply_markup=status_kb(),
            parse_mode="HTML",
        )
        await state.set_state(ProfileStates.status)

    finally:
        session.close()


# ====================== 8. СТАТУС ======================

@router_state.message(ProfileStates.status)
async def process_status(message: Message, state: FSMContext):
    """
    Обробка статусу (мама, вагітна тощо).
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

        await state.update_data(status=status)

        # Переходимо до вибору інтересів
        data = await state.get_data()
        selected_interests = data.get("interests", [])

        ask_interests = render_bot_message(
            session,
            "profile_ask_interests",
            lang="uk",
        )
        await message.answer(
            ask_interests,
            reply_markup=build_interests_kb(selected_interests),
            parse_mode="HTML",
        )
        await state.set_state(ProfileStates.interests)

    finally:
        session.close()


# ====================== 9. ІНТЕРЕСИ ======================

@router_state.message(ProfileStates.interests)
async def process_interests(message: Message, state: FSMContext):
    """
    Логіка вибору інтересів.

    Інтереси представлені як кнопки. При натисканні:
    - якщо вже був вибраний → знімаємо
    - якщо не був          → додаємо

    Окрема кнопка "Готово" завершує вибір.
    """
    text = (message.text or "").strip()

    # Якщо натиснута кнопка з "✅ ..."
    if text.startswith("✅ "):
        text = text[2:].strip()

    data = await state.get_data()
    selected = set(data.get("interests", []))

    session = SessionLocal()

    try:
        # 🔹 Користувач натиснув "Готово"
        if text == "Готово":
            if not selected:
                # Потрібно вибрати хоча б один інтерес
                err_text = render_bot_message(
                    session,
                    "profile_interests_empty",
                    lang="uk",
                )
                await message.answer(err_text, parse_mode="HTML")

                ask_again = render_bot_message(
                    session,
                    "profile_interests_choose_again",
                    lang="uk",
                )
                await message.answer(
                    ask_again,
                    reply_markup=build_interests_kb(list(selected)),
                    parse_mode="HTML",
                )
                return

            # Зберігаємо вибір і переходимо до BIO
            await state.update_data(interests=list(selected))

            ask_bio = render_bot_message(session, "profile_ask_bio", lang="uk")
            await message.answer(ask_bio, parse_mode="HTML")
            await state.set_state(ProfileStates.bio)
            return

        # 🔹 Натиснуто щось, що не є інтересом
        if text not in INTEREST_OPTIONS:
            err_text = render_bot_message(
                session,
                "profile_interests_invalid",
                lang="uk",
            )
            await message.answer(err_text, parse_mode="HTML")

            ask_again = render_bot_message(
                session,
                "profile_interests_choose_again",
                lang="uk",
            )
            await message.answer(
                ask_again,
                reply_markup=build_interests_kb(list(selected)),
                parse_mode="HTML",
            )
            return

        # 🔹 Тогл інтересу
        if text in selected:
            selected.remove(text)
        else:
            selected.add(text)

        await state.update_data(interests=list(selected))

        updated_text = render_bot_message(
            session,
            "profile_interests_updated",
            lang="uk",
        )
        await message.answer(
            updated_text,
            reply_markup=build_interests_kb(list(selected)),
            parse_mode="HTML",
        )

    finally:
        session.close()


# ====================== 10. BIO ======================

@router_state.message(ProfileStates.bio)
async def process_bio(message: Message, state: FSMContext):
    """
    Зберігаємо BIO, формуємо коротке резюме анкети й просимо підтвердити.
    """
    await state.update_data(bio=(message.text or "").strip())
    data = await state.get_data()

    # Формуємо текст резюме у вигляді звичайного plain-text
    lines = [
        f"👩 Ім'я: {data.get('name')}",
        f"✨ Нікнейм: {data.get('nickname')}",
        f"📍 Область: {data.get('region')}",
    ]

    location_type = data.get("location_type")
    if location_type == "city":
        lines.append(f"🏙 Місто: {data.get('city')}")
    elif location_type == "village":
        lines.append(f"🌿 Село: {data.get('village')}")

    lines.extend(
        [
            f"🎂 Вік: {data.get('age')}",
            f"👶 Статус: {data.get('status')}",
            "🧩 Інтереси: " + ", ".join(data.get("interests", [])),
            f"📜 BIO: {data.get('bio')}",
        ]
    )

    summary = "\n".join(lines)

    # Текст беремо з BotMessage, де {summary} — готовий блок з усіма полями
    # Приклад шаблону:
    # key="profile_summary"
    # text="Ось як виглядає твоя анкета:\n\n{summary}\n\nВсе правильно?"
    session = SessionLocal()
    try:
        text = render_bot_message(
            session,
            "profile_summary",
            lang="uk",
            summary=summary,
        )
    finally:
        session.close()

    await message.answer(
        text,
        reply_markup=confirm_kb(),
    )

    await state.set_state(ProfileStates.confirm)


# ====================== 11. ПІДТВЕРДЖЕННЯ (ВСЕ ОК) ======================

@router_state.message(ProfileStates.confirm, F.text == "Все ок")
async def confirm_yes(message: Message, state: FSMContext):
    """
    Користувач підтвердив анкету.

    1. Зберігаємо профіль у БД.
    2. Очищаємо стан.
    3. Показуємо повідомлення про успішне збереження +
       коротку підказку з командами.
    """
    data = await state.get_data()
    telegram_id = message.from_user.id
    tg_username = message.from_user.username  # може бути None

    session = SessionLocal()
    try:
        # Збереження профілю
        save_user_profile_from_state(session, telegram_id, tg_username, data)

        # Повідомлення про успішне збереження
        text_saved = render_bot_message(
            session,
            "profile_confirm_saved",
            lang="uk",
        )

        # Підказка з командами /view, /edit, /match
        text_commands = render_bot_message(
            session,
            "profile_confirm_commands",
            lang="uk",
        )
    finally:
        session.close()

    await state.clear()

    await message.answer(text_saved, parse_mode="HTML")
    await message.answer(
        text_commands,
        reply_markup=ReplyKeyboardRemove(),
        parse_mode="HTML",
    )


# ====================== 12. ПІДТВЕРДЖЕННЯ (ЗМІНИТИ) ======================

@router_state.message(ProfileStates.confirm, F.text == "Змінити")
async def confirm_no(message: Message, state: FSMContext):
    """
    Користувач хоче щось змінити в анкеті.

    1. Все одно зберігаємо поточний профіль (щоб нічого не втратити).
    2. Показуємо меню редагування.
    """
    data = await state.get_data()
    telegram_id = message.from_user.id
    tg_username = message.from_user.username

    session = SessionLocal()
    try:
        # 1️⃣ Зберігаємо поточний профіль
        save_user_profile_from_state(session, telegram_id, tg_username, data)

        # 2️⃣ Текст про збереження та перехід до редагування
        text = render_bot_message(
            session,
            "profile_confirm_change",
            lang="uk",
        )
    finally:
        session.close()

    await message.answer(
        text,
        reply_markup=edit_menu_kb(),
        parse_mode="HTML",
    )
    await state.set_state(EditProfileStates.menu)
