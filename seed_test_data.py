import random
from sqlalchemy.orm import Session

from config import SessionLocal
from database import User  # або звідки в тебе імпортується User
from config import INTEREST_OPTIONS, VALID_REGIONS, STATUS_OPTIONS


def _pick_interests(base_interests: list[str], min_common=1, extra=1) -> list[str]:
    """
    Бере частину спільних інтересів + додає кілька випадкових інших.
    """
    base_interests = base_interests or []
    common = random.sample(base_interests, k=min(len(base_interests), min_common)) if base_interests else []
    others_pool = [i for i in INTEREST_OPTIONS if i not in common]
    others = random.sample(others_pool, k=min(len(others_pool), extra)) if others_pool else []
    return list(dict.fromkeys(common + others))  # унікалізація з збереженням порядку


def seed_test_profiles_for_user(me_telegram_id: int):
    """
    Створює тестові профілі для користувача з telegram_id = me_telegram_id.

    1) 5 з однаковим місцем проживання
    2) 5 зі схожими інтересами (інше місце)
    3) 5 з однаковим місцем + схожими інтересами
    """

    session: Session = SessionLocal()
    try:
        me: User | None = session.query(User).filter(User.telegram_id == me_telegram_id).one_or_none()
        if me is None:
            print(f"❌ Користувача з telegram_id={me_telegram_id} не знайдено в БД")
            return

        base_region = me.region or random.choice(VALID_REGIONS)
        base_city = me.city
        base_village = me.village
        base_interests = me.interests or INTEREST_OPTIONS[:3]
        base_status = me.status or random.choice(STATUS_OPTIONS)

        print(f"➡️ Базуємось на користувачі: {me_telegram_id}, region={base_region}, city={base_city}, village={base_village}")
        print(f"➡️ Базові інтереси: {base_interests}")
        print(f"➡️ Базовий статус: {base_status}")

        test_users: list[User] = []

        # 👥 1. 5 юзерів з тим самим місцем проживання
        for i in range(5):
            test_users.append(
                User(
                    telegram_id=10_000_000 + i,  # штучні ID, щоб не пересікались з реальними
                    name=f"Локальна мама {i+1}",
                    username=None,
                    nickname=f"Local_{i+1}",
                    region=base_region,
                    city=base_city,
                    village=base_village,
                    age=random.randint(22, 40),
                    status=random.choice(STATUS_OPTIONS),
                    interests=random.sample(INTEREST_OPTIONS, k=3),
                    bio="Тестовий профіль (спільне місце проживання).",
                )
            )

        # 💬 2. 5 юзерів зі схожими інтересами, але інше місце
        for i in range(5):
            # інша область
            other_regions = [r for r in VALID_REGIONS if r != base_region]
            region = random.choice(other_regions) if other_regions else base_region

            test_users.append(
                User(
                    telegram_id=10_000_100 + i,
                    name=f"Інтерес мама {i+1}",
                    username=None,
                    nickname=f"Interest_{i+1}",
                    region=region,
                    city=None if base_city else "Інше місто",
                    village=None if base_village else "Інше село",
                    age=random.randint(22, 40),
                    status=random.choice(STATUS_OPTIONS),
                    interests=_pick_interests(base_interests, min_common=1, extra=2),
                    bio="Тестовий профіль (схожі інтереси, інше місце).",
                )
            )

        # 🎯 3. 5 юзерів з тим самим місцем + схожими інтересами
        for i in range(5):
            test_users.append(
                User(
                    telegram_id=10_000_200 + i,
                    name=f"Комбо мама {i+1}",
                    username=None,
                    nickname=f"Combo_{i+1}",
                    region=base_region,
                    city=base_city,
                    village=base_village,
                    age=random.randint(22, 40),
                    status=base_status,
                    interests=_pick_interests(base_interests, min_common=2, extra=1),
                    bio="Тестовий профіль (місце + інтереси).",
                )
            )

        # Додаємо в БД
        for u in test_users:
            # на випадок, якщо вже запускали — не дублюємо по telegram_id
            exists = session.query(User).filter(User.telegram_id == u.telegram_id).one_or_none()
            if exists is None:
                session.add(u)

        session.commit()
        print(f"✅ Створено {len(test_users)} тестових профілів.")

    finally:
        session.close()


if __name__ == "__main__":
    # підстав свій реальний Telegram ID, з яким ти тестуєш бота
    MY_TG_ID = 558530054  # приклад
    seed_test_profiles_for_user(MY_TG_ID)