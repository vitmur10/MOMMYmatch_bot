from sqlalchemy.orm import Session
from sqlalchemy.exc import NoResultFound
from database import User, Choice
from aiogram.types import Message, ReplyKeyboardRemove
from keyboard.reply import edit_menu_kb, build_match_kb
from aiogram.fsm.context import FSMContext
from state import MatchStates, ProfileStates
from database import SessionLocal
import html


def get_user_by_telegram_id(session: Session, telegram_id: int):
    """
    Повертає користувача за telegram_id або None, якщо не існує.
    """
    return session.query(User).filter(User.telegram_id == telegram_id).one_or_none()


async def send_edit_menu(message: Message):
    await message.answer(
        "Що хочеш змінити? Обери параметр нижче 👇\n"
        "Або можеш скорористатися командами\n"
        "🤝 /match — почати пошук мам (метчінг)\n"
        "📇 /view — переглянути свій профіль\n"
        ,
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


def get_excluded_ids(session, me_id: int) -> set[int]:
    """ID користувачів, яких не показуємо (я сама + кого вже лайкала/дизлайкала)."""
    existing_choices = (
        session.query(Choice.chosen_id)
        .filter(Choice.chooser_id == me_id)
        .all()
    )
    excluded = {me_id}
    excluded.update(row[0] for row in existing_choices)
    return excluded


def find_candidates_by_criterion(session, me: User, criterion: str) -> list[User]:
    """
    criterion: 'location' | 'status' | 'interests' | 'location_interests'
    Повертає список User (до 3 штук).
    """
    me_id = me.telegram_id
    excluded_ids = get_excluded_ids(session, me_id)  # ті, кого вже лайкав/дизлайкав

    # на всякий випадок виключимо і себе
    if me_id not in excluded_ids:
        excluded_ids.append(me_id)

    q = session.query(User)
    if excluded_ids:
        q = q.filter(~User.telegram_id.in_(excluded_ids))

    # 1️⃣ Тільки місце проживання
    if criterion == "location":
        if not me.region or (not me.city and not me.village):
            return []

        q = q.filter(User.region == me.region)

        if me.city:
            q = q.filter(User.city == me.city)
        elif me.village:
            q = q.filter(User.village == me.village)

        candidates = q.all()

    # 2️⃣ Тільки статус
    elif criterion == "status":
        if not me.status:
            return []
        q = q.filter(User.status == me.status)
        candidates = q.all()

    # 3️⃣ Тільки інтереси (є хоч один спільний)
    elif criterion == "interests":
        my_interests = set(me.interests or [])
        if not my_interests:
            return []

        candidates_all = q.all()
        candidates: list[User] = []

        for c in candidates_all:
            if not c.interests:
                continue
            if my_interests & set(c.interests):
                candidates.append(c)

    # 4️⃣ Місце + інтереси
    elif criterion == "location_interests":
        my_interests = set(me.interests or [])
        if not me.region or (not me.city and not me.village) or not my_interests:
            return []

        # спершу фільтр по місцю
        q_loc = q.filter(User.region == me.region)
        if me.city:
            q_loc = q_loc.filter(User.city == me.city)
        elif me.village:
            q_loc = q_loc.filter(User.village == me.village)

        candidates_all = q_loc.all()
        candidates: list[User] = []

        for c in candidates_all:
            if not c.interests:
                continue
            if my_interests & set(c.interests):  # є перетин
                candidates.append(c)

    else:
        candidates = []

    return candidates[:3]


async def notify_match(bot, user_a: User, user_b: User):
    """
    Надсилає обом повідомлення про метч.
    Ім'я іншої мами є гіперпосиланням на профіль.
    """

    # ---------- Будуємо гіперлінк до Telegram-профілю ----------
    def name_link(u: User) -> str:
        """
        Ім'я або нікнейм у вигляді гіперпосилання.
        Якщо є username → https://t.me/username
        Якщо немає → tg://user?id=123
        """
        text = u.nickname or u.name or "без імені"

        if u.username:
            return f'<a href="https://t.me/{u.username}">{text}</a>'

        return f'<a href="tg://user?id={u.telegram_id}">{text}</a>'

    # ---------- Контакт (може бути @username або tg://user) ----------
    def contact_link(u: User) -> str:
        if u.username:
            return f"@{u.username}"
        return f'<a href="tg://user?id={u.telegram_id}">написати в Telegram</a>'

    # ---------- Формування текстів ----------
    name_for_a = name_link(user_b)  # user A бачить ім'я B
    name_for_b = name_link(user_a)  # user B бачить ім'я A

    contact_for_a = contact_link(user_b)
    contact_for_b = contact_link(user_a)

    text_for_a = (
        "🎉 <b>У тебе новий метч!</b>\n\n"
        "Ти й інша мама вподобали анкети одна одної 🫶\n\n"
        f"👩 Мама: {name_for_a}\n"
    )

    text_for_b = (
        "🎉 <b>У тебе новий метч!</b>\n\n"
        "Ти й інша мама вподобали анкети одна одної 🫶\n\n"
        f"👩 Мама: {name_for_b}\n"
    )

    # ---------- Відправляємо повідомлення ----------
    await bot.send_message(
        chat_id=user_a.telegram_id,
        text=text_for_a,
        parse_mode="HTML",
        disable_web_page_preview=True
    )

    await bot.send_message(
        chat_id=user_b.telegram_id,
        text=text_for_b,
        parse_mode="HTML",
        disable_web_page_preview=True
    )


async def run_match_flow(message, state, criterion: str):
    me_id = message.from_user.id

    session = SessionLocal()
    try:
        me = get_user_by_telegram_id(session, me_id)
        if me is None:
            await message.answer(
                "Тебе ще немає в базі 🧐\n"
                "Спочатку заповни анкету через /start."
            )
            await state.clear()
            return

        candidates = find_candidates_by_criterion(session, me, criterion)
    finally:
        session.close()

    # ⛔ Кандидатів немає
    if not candidates:
        if criterion == "location":
            crit_text = "за місцем проживання"
        elif criterion == "location_interests":
            crit_text = "за місцем проживання та інтересами"
        elif criterion == "interests":
            crit_text = "за інтересами"
        else:
            crit_text = "за заданим критерієм"

        await message.answer(
            f"Поки що немає кандидатів {crit_text} 😔\n"
            "Спробуй інший критерій або онови анкету через /edit.",
            reply_markup=ReplyKeyboardRemove(),
        )
        await state.clear()
        return

    # ✅ Беремо одного кандидата
    cand = candidates[0]

    nickname = cand.nickname or "не вказано"
    age = str(cand.age) if cand.age is not None else "не вказано"
    bio = cand.bio or "не вказано"
    status = cand.status or "не вказано"

    # 🔒 ЕКРАНУЄМО увесь юзерський текст
    nickname_safe = html.escape(nickname)
    bio_safe = html.escape(bio)
    status_safe = html.escape(status)

    text = (
        "👤 <b>Кандидат</b>\n"
        "━━━━━━━━━━━━━━\n"
        f"✨ <b>Нікнейм:</b> {nickname_safe}\n"
        f"🎂 <b>Вік:</b> {age}\n"
        f"👶 <b>Статус:</b> {status_safe}\n"
        f"📜 <b>BIO:</b>\n{bio_safe}"
    )

    # Зберігаємо, кого оцінюємо і за яким критерієм
    await state.update_data(
        current_candidate_id=cand.telegram_id,
        current_criterion=criterion,
    )

    await message.answer(
        text,
        parse_mode="HTML",
        reply_markup=build_match_kb(),
    )
    await state.set_state(MatchStates.like_dislike)


# 🔹 Хелпер для збереження профілю з FSM-даних
def save_user_profile_from_state(session, telegram_id: int, tg_username: str | None, data: dict):
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
    user.username = tg_username

    session.add(user)
    session.commit()
    return user


def render_bot_message(session, key: str, lang: str = "uk", **kwargs) -> str:
    msg = (
        session.query(BotMessage)
        .filter_by(key=key, lang=lang)
        .one_or_none()
    )

    if msg is None:
        template = f"[Текст '{key}' не знайдено]"
    else:
        template = msg.text

    try:
        # Підставляємо змінні {name}, {age} і т.д.
        return template.format(**kwargs)
    except KeyError as e:
        # Якщо забули якусь змінну передати — не падаємо
        missing = e.args[0]
        return template + f"\n\n[⚠️ Не вистачає змінної: {missing}]"
