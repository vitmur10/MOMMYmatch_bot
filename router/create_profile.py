# router/profile.py

from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    Message,
    ReplyKeyboardMarkup,
    CallbackQuery,ReplyKeyboardRemove
)
import math
from config import VALID_REGIONS, SessionLocal, STATUS_OPTIONS, INTEREST_OPTIONS
from database import User
from function import get_user_by_telegram_id
from keyboard.reply import location_type_kb, status_kb, build_interests_kb, confirm_kb, build_regions_kb, PAGE_SIZE, edit_menu_kb
from state import ProfileStates, EditProfileStates

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

    await message.answer(
        "Клас 🥰\n"
        "Тепер обери свою область зі списку нижче:",
        reply_markup=build_regions_kb(page=0),
    )
    await state.set_state(ProfileStates.region)


# ------------------------------
# 3. Область (region)
# ------------------------------

@router_state.message(ProfileStates.region)
async def process_region(message: Message, state: FSMContext):
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

    # ✅ Коректна область
    region = text
    await state.update_data(region=region)

    await message.answer(f"Область: {region}")
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

@router_state.message(ProfileStates.interests)
async def process_interests(message: Message, state: FSMContext):
    text = message.text.strip()

    # Якщо натиснув кнопку з "✅ ..."
    if text.startswith("✅ "):
        text = text[2:].strip()

    # Дістаємо поточний вибір зі стейту
    data = await state.get_data()
    selected = set(data.get("interests", []))

    # 🔹 Користувач натиснув "Готово"
    if text == "Готово":
        if not selected:
            await message.answer("Будь ласка, обери хоча б один інтерес 🙂")
            await message.answer(
                "Оберіть, будь ласка, інтереси:",
                reply_markup=build_interests_kb(list(selected)),
            )
            return

        # зберігаємо вибір і йдемо далі
        await state.update_data(interests=list(selected))
        await message.answer(
            "Дякую! 🥰\n"
            "Тепер напиши, будь ласка, короткий BIO: трохи про себе і що ти шукаєш."
        )
        await state.set_state(ProfileStates.bio)
        return

    # 🔹 Натиснуто щось, що не є інтересом
    if text not in INTEREST_OPTIONS:
        await message.answer(
            "Будь ласка, обирай інтереси з кнопок нижче або натисни 'Готово'."
        )
        await message.answer(
            "Оберіть інтереси:",
            reply_markup=build_interests_kb(list(selected)),
        )
        return

    # 🔹 Тогл інтересу
    if text in selected:
        selected.remove(text)
    else:
        selected.add(text)

    await state.update_data(interests=list(selected))

    await message.answer(
        "Оновила список інтересів. Можеш обрати ще або натиснути 'Готово' ✅",
        reply_markup=build_interests_kb(list(selected)),
    )


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

@router_state.message(ProfileStates.confirm, F.text == "Все ок")
async def confirm_yes(message: Message, state: FSMContext):
    data = await state.get_data()
    telegram_id = message.from_user.id
    tg_username = message.from_user.username  # може бути None

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

        # 👇 Сюди кладемо Telegram-username
        user.username = tg_username

        session.add(user)
        session.commit()

    finally:
        session.close()

    await state.clear()

    await message.answer(
        "Чудово! 🌸 Твоя анкета збережена.\n"
        "Тепер я зможу підбирати для тебе мам за спільними інтересами 🫶"
    )
    await message.answer(
        "Можеш скористатися командами:\n"
        "• /view — переглянути свій профіль\n"
        "• /edit — змінити дані анкети\n"
        "• /match — почати пошук мам"
        ,reply_markup=ReplyKeyboardRemove()
    )


@router_state.message(ProfileStates.confirm, F.text == "Змінити")
async def confirm_no(message: Message, state: FSMContext):
    await message.answer(
        "Добре, давай щось підредагуємо ✏️\n"
        "Обери, що хочеш змінити:",
        reply_markup=edit_menu_kb(),
    )
    await state.set_state(EditProfileStates.menu)
