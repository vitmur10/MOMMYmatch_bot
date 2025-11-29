from sqlalchemy import (
    create_engine,
    Column,
    Integer,
    BigInteger,
    String,
    Text,
    JSON,
    TIMESTAMP,
    ForeignKey,
    CheckConstraint,
    UniqueConstraint,
)
from sqlalchemy.orm import declarative_base, relationship, sessionmaker
from datetime import datetime
from config import DATABASE_URL


# ==========================
# ПІДКЛЮЧЕННЯ ДО БАЗИ DАНИХ
# ==========================

# Перевіряємо, що DATABASE_URL заданий (через .env / env vars).
# Якщо ні — падаємо з помилкою, щоб не запускати бот без БД.
if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL не заданий! Додай його в .env або env vars.")

# Створюємо engine для PostgreSQL.
# - pool_pre_ping=True — перевірка з’єднання перед використанням (боротьба з "мертвими" конектами).
# - pool_size — розмір пулу постійних з’єднань.
# - max_overflow — скільки додаткових з’єднань можна створити поверх pool_size.
engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=10,
)

# Фабрика сесій — будемо її використовувати у коді (SessionLocal()).
SessionLocal = sessionmaker(bind=engine)

# Базовий клас для всіх моделей
Base = declarative_base()


# ==========================
# МОДЕЛЬ: користувачі (Users)
# ==========================
class User(Base):
    """
    Таблиця користувачів бота.

    Зберігає основні дані анкети:
    - telegram_id — primary key (ID користувача в Telegram).
    - name — ім'я.
    - username — @username в Telegram (для побудови посилань).
    - nickname — псевдонім, який бачать інші мами.
    - region / city / village — місце проживання.
      (місто й село взаємовиключні; logіку забезпечуємо на рівні коду).
    - age — вік.
    - status — статус мами (не плутати з внутрішнім статусом, краще потім перейменувати).
    - interests — JSON-масив інтересів (список рядків).
    - bio — опис про себе.

    Також є 2 зв'язки:
    - choices_made — вибори, які зробив цей користувач (кого лайкнув/дизлайкнув).
    - choices_received — вибори, які отримав цей користувач (хто лайкнув/дизлайкнув його).
    """

    __tablename__ = "Users"

    # Telegram ID як первинний ключ (BigInteger, бо Telegram дає великі ID)
    telegram_id = Column(BigInteger, primary_key=True)

    # Ім'я (з анкети)
    name = Column(String(255))

    # Загальний telegram username (@nickname), якщо є
    username = Column(String(255))

    # Нікнейм, який бачать інші мами (може відрізнятися від username)
    nickname = Column(String(255))

    # Регіон (область)
    region = Column(String(100))

    # Місто
    city = Column(String(100))

    # Село
    village = Column(String(100))

    # Вік
    age = Column(Integer)

    # Статус (наприклад: "мама", "вагітна" і т.п.)
    # Зараз тут стоїть default="active" — можна потім змінити, якщо захочеш тримати інший формат.
    status = Column(String(50), default="active")

    # Інтереси у форматі JSON (список рядків)
    interests = Column(JSON)

    # Короткий опис (BIO)
    bio = Column(Text)

    # Вибори, які зробила ця користувачка (LIKE/DISLIKE інших)
    choices_made = relationship(
        "Choice",
        back_populates="chooser",
        foreign_keys="Choice.chooser_id",
    )

    # Вибори, які отримала ця користувачка (LIKE/DISLIKE від інших)
    choices_received = relationship(
        "Choice",
        back_populates="chosen",
        foreign_keys="Choice.chosen_id",
    )


# ==========================
# МОДЕЛЬ: вибори (Choices)
# ==========================
class Choice(Base):
    """
    Таблиця виборів (лайки/дизлайки між користувачами).

    - chooser_id — хто обирає (хто лайкнув / дизлайкнув).
    - chosen_id  — кого оцінили.
    - choice_type — 'LIKE' або 'DISLIKE'.
    - created_at — коли зроблено вибір.

    Обмеження:
    - UniqueConstraint(chooser_id, chosen_id) — один користувач може один раз оцінити іншого
      (але ми можемо змінити choice_type з LIKE на DISLIKE і навпаки).
    - CheckConstraint(choice_type IN ('LIKE','DISLIKE')) — захист від некоректних значень.
    """

    __tablename__ = "Choices"
    __table_args__ = (
        # Один запис на пару (хто-кого), щоб не було дубльованих лайків/дизлайків
        UniqueConstraint("chooser_id", "chosen_id", name="uix_chooser_chosen"),
        # choice_type може бути тільки LIKE або DISLIKE
        CheckConstraint("choice_type IN ('LIKE','DISLIKE')", name="chk_choice_type"),
    )

    # Хто обрав (foreign key на Users.telegram_id)
    chooser_id = Column(
        BigInteger,
        ForeignKey("Users.telegram_id", ondelete="CASCADE"),
        primary_key=True,
    )

    # Кого обрали (foreign key на Users.telegram_id)
    chosen_id = Column(
        BigInteger,
        ForeignKey("Users.telegram_id", ondelete="CASCADE"),
        primary_key=True,
    )

    # Тип вибору: LIKE / DISLIKE
    choice_type = Column(String(20), nullable=False)

    # Коли вибір було зроблено
    created_at = Column(TIMESTAMP, default=datetime.utcnow)

    # Об'єкт користувача, який зробив вибір
    chooser = relationship(
        "User",
        foreign_keys=[chooser_id],
        back_populates="choices_made",
    )

    # Об'єкт користувача, якого оцінюють
    chosen = relationship(
        "User",
        foreign_keys=[chosen_id],
        back_populates="choices_received",
    )


# ==========================
# МОДЕЛЬ: тексти бота (BotMessages)
# ==========================
class BotMessage(Base):
    """
    Таблиця текстів бота.

    Використовується для зберігання шаблонів повідомлень:
    - key — унікальний ключ (наприклад: "start_new_user", "profile_ask_age").
    - text — текст повідомлення (може містити плейсхолдери {name}, {age} тощо).
    - lang — код мови (за замовчуванням 'uk').
    - created_at — дата створення запису.

    Далі ці тексти підтягуються через render_bot_message(session, key, lang, **kwargs).
    """

    __tablename__ = "BotMessages"

    # PK (автоінкремент)
    message_id = Column(Integer, primary_key=True, autoincrement=True)

    # Унікальний ключ повідомлення (для пошуку в коді)
    key = Column(String(100), nullable=False, unique=True)

    # Сам текст (шаблон) повідомлення
    text = Column(Text, nullable=False)

    # Мова (наприклад, 'uk', 'en')
    lang = Column(String(10), default="uk")

    # Дата створення
    created_at = Column(TIMESTAMP, default=datetime.utcnow)


# ==========================
# СТВОРЕННЯ ВСІХ ТАБЛИЦЬ
# ==========================
def create_tables() -> None:
    """
    Створює всі таблиці в базі даних згідно з описаними моделями.

    Викликається один раз:
        python database.py

    або підтягується з окремого скрипта ініціалізації.
    """
    Base.metadata.create_all(engine)
    print("Таблиці створено у PostgreSQL!")


# Якщо запустити файл напряму — створюємо таблиці
if __name__ == "__main__":
    create_tables()
