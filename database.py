from sqlalchemy import (
    create_engine, Column, Integer, BigInteger, String, Text, JSON, TIMESTAMP, ForeignKey, CheckConstraint,
    UniqueConstraint
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from datetime import datetime
import os

# ==========================
# SQLite для розробки
# ==========================
DB_FILE = "mommatch_dev.db"
DATABASE_URL = f"sqlite:///{DB_FILE}"

# ❌ БІЛЬШЕ НЕ ВИДАЛЯЄМО БД ПРИ ІМПОРТІ
# if os.path.exists(DB_FILE):
#     os.remove(DB_FILE)

engine = create_engine(DATABASE_URL, echo=True, connect_args={"check_same_thread": False})
Base = declarative_base()


# ==========================
# Таблиця користувачів
# ==========================
class User(Base):
    __tablename__ = "Users"

    telegram_id = Column(BigInteger, primary_key=True)
    name = Column(String(255))

    username = Column(String(255))  # може бути загальний username

    nickname = Column(String(255))
    region = Column(String(100))
    city = Column(String(100))
    village = Column(String(100))
    age = Column(Integer)
    status = Column(String(50), default="active")
    interests = Column(JSON)
    bio = Column(Text)

    choices_made = relationship("Choice", back_populates="chooser", foreign_keys="Choice.chooser_id")
    choices_received = relationship("Choice", back_populates="chosen", foreign_keys="Choice.chosen_id")


# ==========================
# Таблиця виборів
# ==========================
class Choice(Base):
    __tablename__ = "Choices"
    __table_args__ = (
        UniqueConstraint("chooser_id", "chosen_id", name="uix_chooser_chosen"),
        CheckConstraint("choice_type IN ('LIKE','DISLIKE')", name="chk_choice_type")
    )

    chooser_id = Column(BigInteger, ForeignKey("Users.telegram_id", ondelete="CASCADE"), primary_key=True)
    chosen_id = Column(BigInteger, ForeignKey("Users.telegram_id", ondelete="CASCADE"), primary_key=True)
    choice_type = Column(String(20), nullable=False)
    created_at = Column(TIMESTAMP, default=datetime.utcnow)

    chooser = relationship("User", foreign_keys=[chooser_id], back_populates="choices_made")
    chosen = relationship("User", foreign_keys=[chosen_id], back_populates="choices_received")


# ==========================
# Таблиця текстів бота
# ==========================
class BotMessage(Base):
    __tablename__ = "BotMessages"

    message_id = Column(Integer, primary_key=True, autoincrement=True)
    key = Column(String(100), nullable=False, unique=True)
    text = Column(Text, nullable=False)
    lang = Column(String(10), default="uk")
    created_at = Column(TIMESTAMP, default=datetime.utcnow)


# ==========================
# Створення всіх таблиць
# ==========================
def create_tables():
    Base.metadata.create_all(engine)
    print("Таблиці створено у SQLite!")


if __name__ == "__main__":
    create_tables()
