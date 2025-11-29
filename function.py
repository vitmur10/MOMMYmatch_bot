from sqlalchemy.orm import Session
from sqlalchemy.exc import NoResultFound
from database import User, Choice, BotMessage
from aiogram.types import Message, ReplyKeyboardRemove
from keyboard.reply import edit_menu_kb, build_match_kb
from aiogram.fsm.context import FSMContext
from state import MatchStates, ProfileStates
from database import SessionLocal
import html
import asyncio


# ====================== БАЗОВІ ХЕЛПЕРИ ПО КОРИСТУВАЧАМ ======================

def get_user_by_telegram_id(session: Session, telegram_id: int):
    """
    Повертає користувача за telegram_id або None, якщо його ще немає в базі.
    """
    return session.query(User).filter(User.telegram_id == telegram_id).one_or_none()


async def send_edit_menu(message: Message):
    """
    Відправляє меню редагування анкети з невеликою затримкою перед підказкою.

    За edit.csv:
      ROW 1: основний текст (edit_r1_c0)
      ROW 2: затримка 3 секунд
      ROW 3: додатковий текст з командами (edit_r3_c0)
    """
    session = SessionLocal()
    try:
        # Основне запитання: "Що саме хочеш оновити..."
        text_main = render_bot_message(session, "edit_r1_c0", lang="uk")

        # Додаткова підказка з командами /view, /match
        text_hint = render_bot_message(session, "edit_r3_c0", lang="uk")
    finally:
        session.close()

    # 1️⃣ Надсилаємо основний текст + клавіатуру з пунктами редагування
    await message.answer(
        text_main,
        reply_markup=edit_menu_kb(),
        parse_mode="HTML",
    )

    # 2️⃣ Затримка 3 секунди (ROW 2: "затримка 3 секунд")
    #   + надсилаємо друге повідомлення, якщо воно реально є в БД
    if not (text_hint.startswith("[Текст 'edit_r3_c0'") and "не знайдено" in text_hint):
        await asyncio.sleep(3)
        await message.answer(text_hint, parse_mode="HTML")


def get_status_emoji(status: str) -> str:
    """
    Повертає емодзі в залежності від статусу.

    Використовується для відображення короткого статусу:
    - містить "мама"  -> 👩‍👧‍👦
    - містить "вагіт" -> 🤰
    - інакше           -> 👶
    """
    if not status:
        return "👶"
    status = status.lower()
    if "мама" in status:
        return "👩‍👧‍👦"
    if "вагіт" in status:
        return "🤰"
    return "👶"


def get_excluded_ids(session: Session, me_id: int) -> set[int]:
    """
    Повертає множину telegram_id користувачів, яких НЕ показуємо в пошуку.

    Сюди входять:
    - я сама (me_id)
    - всі, кого вже лайкала/дизлайкала (з таблиці Choice)
    """
    existing_choices = (
        session.query(Choice.chosen_id)
        .filter(Choice.chooser_id == me_id)
        .all()
    )
    excluded: set[int] = {me_id}  # завжди виключаємо себе
    excluded.update(row[0] for row in existing_choices)
    return excluded


# ====================== ПОШУК КАНДИДАТІВ ДЛЯ МЕТЧУ ======================

def find_candidates_by_criterion(session: Session, me: User, criterion: str) -> list[User]:
    """
    Підбирає список кандидатів (користувачів) для метчингу за заданим критерієм.

    Параметри:
        session   – активна сесія БД
        me        – поточний користувач (мама, яка шукає)
        criterion – один із:
                    'location'            – тільки місце проживання
                    'status'              – тільки статус (мама/вагітна і т.д.)
                    'interests'           – тільки інтереси (є хоча б один спільний)
                    'location_interests'  – місце + інтереси

    Повертає:
        Список з максимум 3-х користувачів User, які підходять під критерій.
    """
    me_id = me.telegram_id
    excluded_ids = get_excluded_ids(session, me_id)  # кого вже бачила / себе

    q = session.query(User)
    if excluded_ids:
        q = q.filter(~User.telegram_id.in_(excluded_ids))

    # 1️⃣ Тільки місце проживання
    if criterion == "location":
        # Якщо у самої немає регіону або міста/села – пошук неможливий
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

        # Спочатку фільтр по місцю
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
            # Є перетин інтересів
            if my_interests & set(c.interests):
                candidates.append(c)

    else:
        candidates = []

    # Обмежуємо до 3-х кандидатів
    return candidates[:3]


# ====================== НОТИФІКАЦІЯ ПРО МЕТЧ ======================

async def notify_match(bot, user_a: User, user_b: User):
    """
    Надсилає обом користувачам повідомлення про новий метч.

    Текст повідомлення береться з BotMessage (ключ "match_new"), де можна
    використати плейсхолдери:
        {mama}    – ім'я/нік іншої мами у вигляді гіперпосилання на профіль
        {contact} – короткий контакт (наприклад, @username або tg://user)
    """

    # ---------- Будуємо гіперлінк до Telegram-профілю ----------

    def name_link(u: User) -> str:
        """
        Ім'я або нікнейм у вигляді гіперпосилання.

        Якщо є username → https://t.me/username
        Якщо немає → tg://user?id=123
        """
        raw_text = u.nickname or u.name or "без імені"
        # Екрануємо текст, щоб уникнути поламаного HTML
        text = html.escape(raw_text)

        if u.username:
            return f'<a href="https://t.me/{u.username}">{text}</a>'

        return f'<a href="tg://user?id={u.telegram_id}">{text}</a>'

    # ---------- Контакт (може бути @username або tg://user) ----------

    def contact_link(u: User) -> str:
        """
        Коротке посилання для контакту:
        - якщо є username → @username
        - інакше         → tg://user?id=...
        """
        if u.username:
            return f"@{u.username}"
        return f'<a href="tg://user?id={u.telegram_id}">написати в Telegram</a>'

    name_for_a = name_link(user_b)  # user A бачить B
    name_for_b = name_link(user_a)  # user B бачить A
    contact_for_a = contact_link(user_b)
    contact_for_b = contact_link(user_a)

    # Текст повідомлення забираємо з БД
    session = SessionLocal()
    try:
        # Приклад шаблону в BotMessage:
        # key="match_new", lang="uk"
        # text="🎉 <b>У тебе новий метч!</b>\n\n"
        #      "Ти й інша мама вподобали анкети одна одної 🫶\n\n"
        #      "👩 Мама: {mama}\n"
        #      "✉ Контакт: {contact}"
        text_for_a = render_bot_message(
            session,
            key="match_new",
            lang="uk",
            mama=name_for_a,
            contact=contact_for_a,
        )
        text_for_b = render_bot_message(
            session,
            key="match_new",
            lang="uk",
            mama=name_for_b,
            contact=contact_for_b,
        )
    finally:
        session.close()

    # ---------- Відправляємо повідомлення ----------

    await bot.send_message(
        chat_id=user_a.telegram_id,
        text=text_for_a,
        parse_mode="HTML",
        disable_web_page_preview=True,
    )

    await bot.send_message(
        chat_id=user_b.telegram_id,
        text=text_for_b,
        parse_mode="HTML",
        disable_web_page_preview=True,
    )


# ====================== ОСНОВНИЙ ФЛОУ ПОШУКУ (МЕТЧИНГ) ======================

async def run_match_flow(message: Message, state: FSMContext, criterion: str):
    """
    Запускає логіку пошуку кандидатів за обраним критерієм та показує першого кандидата.

    Кроки:
    1. Дістаємо поточного користувача з БД.
    2. Підбираємо список кандидатів за критерієм.
    3. Якщо кандидатів немає – показуємо відповідне повідомлення.
    4. Якщо є – показуємо анкету першого кандидата та ставимо стан like/dislike.
    """
    me_id = message.from_user.id
    session = SessionLocal()

    try:
        # 1. Отримуємо поточного користувача
        me = get_user_by_telegram_id(session, me_id)
        if me is None:
            # Якщо користувача немає в БД – просимо пройти /start
            # Приклад шаблону:
            # key="match_user_not_found"
            # "Тебе ще немає в базі 🧐\nСпочатку заповни анкету через /start."
            text = render_bot_message(session, "match_user_not_found", lang="uk")
            await message.answer(text, parse_mode="HTML")
            await state.clear()
            return

        # 2. Шукаємо кандидатів
        candidates = find_candidates_by_criterion(session, me, criterion)

        # 3. Якщо кандидатів немає – показуємо відповідне повідомлення
        if not candidates:
            if criterion == "location":
                key = "match_no_candidates_location"
                # Наприклад: "Поки що немає кандидатів за місцем проживання 😔\n..."
            elif criterion == "location_interests":
                key = "match_no_candidates_location_interests"
                # Наприклад: "Поки що немає кандидатів за місцем проживання та інтересами 😔\n..."
            elif criterion == "interests":
                key = "match_no_candidates_interests"
                # Наприклад: "Поки що немає кандидатів за інтересами 😔\n..."
            else:
                key = "match_no_candidates_default"
                # Наприклад: "Поки що немає кандидатів за заданим критерієм 😔\n..."

            text = render_bot_message(session, key, lang="uk")
            await message.answer(
                text,
                reply_markup=ReplyKeyboardRemove(),
                parse_mode="HTML",
            )
            await state.clear()
            return

        # 4. Беремо одного кандидата (першого зі списку)
        cand = candidates[0]

        # Підготовка даних з fallback-ами
        nickname = cand.nickname or "не вказано"
        age = str(cand.age) if cand.age is not None else "не вказано"
        bio = cand.bio or "не вказано"
        status = cand.status or "не вказано"

        # Екрануємо весь юзерський текст, щоб не поламати HTML
        nickname_safe = html.escape(nickname)
        bio_safe = html.escape(bio)
        status_safe = html.escape(status)

        # Текст анкети кандидата беремо з BotMessage
        # Приклад шаблону:
        # key="match_candidate_profile"
        # text="👤 <b>Кандидат</b>\n"
        #      "━━━━━━━━━━━━━━\n"
        #      "✨ <b>Нікнейм:</b> {nickname}\n"
        #      "🎂 <b>Вік:</b> {age}\n"
        #      "👶 <b>Статус:</b> {status}\n"
        #      "📜 <b>BIO:</b>\n{bio}"
        text = render_bot_message(
            session,
            key="match_candidate_profile",
            lang="uk",
            nickname=nickname_safe,
            age=age,
            status=status_safe,
            bio=bio_safe,
        )

    finally:
        # Закриваємо сесію перед відправкою повідомлень
        session.close()

    # Зберігаємо, кого оцінюємо, і за яким критерієм
    await state.update_data(
        current_candidate_id=cand.telegram_id,
        current_criterion=criterion,
    )

    # Показуємо кандидата + клавіатуру лайк/дизлайк
    await message.answer(
        text,
        parse_mode="HTML",
        reply_markup=build_match_kb(),
    )
    await state.set_state(MatchStates.like_dislike)


# ====================== ЗБЕРЕЖЕННЯ АНКЕТИ З FSM-СТАНУ ======================

def save_user_profile_from_state(
    session: Session,
    telegram_id: int,
    tg_username: str | None,
    data: dict,
):
    """
    Оновлює або створює користувача в БД на основі даних з FSM-стану.

    Параметри:
        session     – активна сесія БД
        telegram_id – ID користувача у Telegram
        tg_username – username з Telegram (може бути None)
        data        – dict з даними анкети:
                      name, nickname, region, city, village, age,
                      status, interests (list), bio
    """
    user = get_user_by_telegram_id(session, telegram_id)
    if user is None:
        user = User(telegram_id=telegram_id)

    # Переносимо дані з FSM в модель User
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


# ====================== ТЕКСТИ БОТА З БАЗИ (BotMessage) ======================

def render_bot_message(session: Session, key: str, lang: str = "uk", **kwargs) -> str:
    """
    Дістає текст бота з таблиці BotMessage та підставляє змінні.

    Таблиця BotMessage має, наприклад, такі поля:
        - key  (str)  – унікальний ключ повідомлення, наприклад "edit_menu"
        - lang (str)  – мова ("uk", "en" і т.д.)
        - text (str)  – шаблон, в якому можна використовувати плейсхолдери {name}, {age}, ...

    Параметри:
        session – активна сесія БД
        key     – ключ повідомлення (наприклад, "edit_menu", "match_new")
        lang    – мова повідомлення ("uk" за замовчуванням)
        **kwargs – змінні для підстановки в шаблон (name=..., age=..., тощо)

    Повертає:
        Готовий рядок для відправки користувачу.
        Якщо ключ не знайдено – повертає "[Текст 'key' не знайдено]".
        Якщо не вистачає змінної – додає попередження в кінці.
    """
    msg = (
        session.query(BotMessage)
        .filter_by(key=key, lang=lang)
        .one_or_none()
    )

    if msg is None:
        # Фолбек, якщо тексту ще немає в БД
        template = f"[Текст '{key}' не знайдено]"
    else:
        template = msg.text

    try:
        # Підставляємо змінні {name}, {age}, {mama}, {contact}, ...
        return template.format(**kwargs)
    except KeyError as e:
        # Якщо забули якусь змінну передати — не падаємо, а показуємо попередження
        missing = e.args[0]
        return template + f"\n\n[⚠️ Не вистачає змінної: {missing}]"
