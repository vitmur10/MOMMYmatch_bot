# router/profile.py

from aiogram import Router, F
from aiogram.types import (
    Message,
    ReplyKeyboardMarkup,
    KeyboardButton,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    CallbackQuery,
)
from database import User
from aiogram.fsm.context import FSMContext
from keyboard.reply import location_type_kb, status_kb
from keyboard.inline import build_interests_kb, confirm_kb
from state import ProfileStates
from config import VALID_REGIONS, SessionLocal, STATUS_OPTIONS
from function import get_user_by_telegram_id
router_state = Router()


@router_state.message(ProfileStates.name)
async def process_name(message: Message, state: FSMContext):
    await state.update_data(name=message.text.strip())

    await message.answer(
        "Супер! 🌼\n"
        "Тепер напиши нікнейм, який будуть бачити інші мами.\n"
        "Це може бути будь-який псевдонім 😊"
    )
    await state.set_state(ProfileStates.nickname)


# ------------------------------
# 2. Нікнейм
# ------------------------------

@router_state.message(ProfileStates.nickname)
async def process_nickname(message: Message, state: FSMContext):
    await state.update_data(nickname=message.text.strip())

    regions_str = ", ".join(VALID_REGIONS)
    await message.answer(
        "Клас 🥰\n"
        "Тепер давай визначимо твоє місце проживання.\n\n"
        "Напиши, будь ласка, свою область.\n"
        f"Наприклад: *Львівська*\n\n"
        f"Список доступних областей:\n{regions_str}",
        parse_mode="Markdown",
    )
    await state.set_state(ProfileStates.region)


# ------------------------------
# 3. Область (region)
# ------------------------------

@router_state.message(ProfileStates.region)
async def process_region(message: Message, state: FSMContext):
    region_input = message.text.strip()

    # Нормалізуємо регіон: порівнюємо по lower()
    normalized_map = {r.lower(): r for r in VALID_REGIONS}
    key = region_input.lower()

    if key not in normalized_map:
        await message.answer(
            "Я не знайшла такої області 😔\n"
            "Перевір написання і обери одну з доступних.\n"
            "Напиши ще раз область:"
        )
        return

    region = normalized_map[key]
    await state.update_data(region=region)

    await message.answer(
        "Ти живеш у місті чи селі?",
        reply_markup=location_type_kb(),
    )
    await state.set_state(ProfileStates.location_type)


# ------------------------------
# 4. Тип населеного пункту (місто / село)
# ------------------------------

@router_state.message(ProfileStates.location_type)
async def process_location_type(message: Message, state: FSMContext):
    text = message.text.strip().lower()

    if text == "місто":
        await state.update_data(location_type="city")
        await message.answer(
            "Введи, будь ласка, назву міста 🌆",
            reply_markup=ReplyKeyboardMarkup(
                keyboard=[],
                resize_keyboard=True,
            ),
        )
        await state.set_state(ProfileStates.city)

    elif text == "село":
        await state.update_data(location_type="village")
        await message.answer(
            "Введи, будь ласка, назву села 🌿",
            reply_markup=ReplyKeyboardMarkup(
                keyboard=[],
                resize_keyboard=True,
            ),
        )
        await state.set_state(ProfileStates.village)

    else:
        await message.answer(
            "Будь ласка, обери *Місто* або *Село* з кнопок нижче 🙂",
            parse_mode="Markdown",
            reply_markup=location_type_kb(),
        )


# ------------------------------
# 5. Місто
# ------------------------------

@router_state.message(ProfileStates.city)
async def process_city(message: Message, state: FSMContext):
    await state.update_data(city=message.text.strip(), village=None)

    await message.answer(
        "Супер! 🎂 Тепер напиши, будь ласка, свій вік (лише число)."
    )
    await state.set_state(ProfileStates.age)


# ------------------------------
# 6. Село
# ------------------------------

@router_state.message(ProfileStates.village)
async def process_village(message: Message, state: FSMContext):
    await state.update_data(village=message.text.strip(), city=None)

    await message.answer(
        "Супер! 🎂 Тепер напиши, будь ласка, свій вік (лише число)."
    )
    await state.set_state(ProfileStates.age)


# ------------------------------
# 7. Вік
# ------------------------------

@router_state.message(ProfileStates.age)
async def process_age(message: Message, state: FSMContext):
    text = message.text.strip()

    if not text.isdigit():
        await message.answer("Будь ласка, напиши вік *цифрами* 🙂", parse_mode="Markdown")
        return

    age = int(text)
    if age < 14 or age > 60:
        await message.answer(
            "Вкажи, будь ласка, реальний вік у межах 14–60 років 🙂"
        )
        return

    await state.update_data(age=age)

    await message.answer(
        "Обери свій статус:",
        reply_markup=status_kb(),
    )
    await state.set_state(ProfileStates.status)


# ------------------------------
# 8. Статус (мама / вагітна)
# ------------------------------

@router_state.message(ProfileStates.status)
async def process_status(message: Message, state: FSMContext):
    status = message.text.strip()

    if status not in STATUS_OPTIONS:
        await message.answer(
            "Будь ласка, обери статус за допомогою кнопок 🙂",
            reply_markup=status_kb(),
        )
        return

    await state.update_data(status=status)

    # Переходимо до інтересів
    data = await state.get_data()
    selected_interests = data.get("interests", [])

    await message.answer(
        "Тепер обери свої інтереси 🧩\n"
        "Ти можеш обрати кілька пунктів, натискаючи на кнопки.\n"
        "Коли закінчиш — натисни *Готово ✅*.",
        reply_markup=build_interests_kb(selected_interests),
    )
    await state.set_state(ProfileStates.interests)


# ------------------------------
# 9. Інтереси — вибір/зняття вибору (CallbackQuery)
# ------------------------------

@router_state.callback_query(ProfileStates.interests, F.data.startswith("interest:"))
async def toggle_interest(callback: CallbackQuery, state: FSMContext):
    interest = callback.data.split(":", 1)[1]

    data = await state.get_data()
    selected = set(data.get("interests", []))

    if interest in selected:
        selected.remove(interest)
    else:
        selected.add(interest)

    selected_list = list(selected)
    await state.update_data(interests=selected_list)

    # Оновлюємо клавіатуру з урахуванням вибору
    await callback.message.edit_reply_markup(
        reply_markup=build_interests_kb(selected_list)
    )

    await callback.answer()  # просто закриваємо "годинник"


@router_state.callback_query(ProfileStates.interests, F.data == "interests_done")
async def interests_done(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    selected = data.get("interests", [])

    if not selected:
        await callback.answer(
            "Будь ласка, обери хоча б один інтерес 🙂", show_alert=True
        )
        return

    await callback.message.answer(
        "Дякую! 🥰\n"
        "Тепер напиши, будь ласка, короткий BIO: трохи про себе і що ти шукаєш."
    )
    await state.set_state(ProfileStates.bio)
    await callback.answer()


# ------------------------------
# 10. BIO
# ------------------------------

@router_state.message(ProfileStates.bio)
async def process_bio(message: Message, state: FSMContext):
    await state.update_data(bio=message.text.strip())

    data = await state.get_data()

    # Формуємо резюме анкети
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

    text = "Ось як виглядає твоя анкета:\n\n" + "\n".join(lines)

    await message.answer(
        text + "\n\nВсе правильно?",
        reply_markup=confirm_kb(),
    )

    await state.set_state(ProfileStates.confirm)


# ------------------------------
# 11. Підтвердження та збереження в БД
# ------------------------------

@router_state.callback_query(ProfileStates.confirm, F.data == "confirm_yes")
async def confirm_yes(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    telegram_id = callback.from_user.id

    session = SessionLocal()
    try:
        user = get_user_by_telegram_id(session, telegram_id)

        if user is None:
            user = User(telegram_id=telegram_id)

        user.name = data.get("name")
        user.nickname = data.get("nickname")
        user.region = data.get("region")
        user.city = data.get("city")
        user.village = data.get("village")
        user.age = data.get("age")
        user.status = data.get("status")
        user.interests = data.get("interests", [])
        user.bio = data.get("bio")

        session.add(user)
        session.commit()

    finally:
        session.close()

    await state.clear()

    await callback.message.answer(
        "Чудово! 🌸 Твоя анкета збережена.\n"
        "Тепер я зможу підбирати для тебе мам за спільними інтересами 🫶"
    )
    await callback.answer()


@router_state.callback_query(ProfileStates.confirm, F.data == "confirm_no")
async def confirm_no(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.answer(
        "Добре, давай спробуємо ще раз з початку 💫\n"
        "Напиши, будь ласка, своє ім’я."
    )
    await state.set_state(ProfileStates.name)
    await callback.answer()
