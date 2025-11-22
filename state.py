from aiogram.fsm.state import StatesGroup, State

class ProfileStates(StatesGroup):
    # 1. Ім'я
    name = State()

    # 2. Нікнейм (те, що бачать інші користувачі)
    nickname = State()

    # 3. Місце проживання
    region = State()          # область
    location_type = State()   # місто / село (кнопки)
    city = State()            # назва міста (якщо вибрали "місто")
    village = State()         # назва села (якщо вибрали "село")

    # 4. Вік
    age = State()

    # 5. Статус (мама / вагітна)
    status = State()

    # 6. Інтереси (може бути мультивибір)
    interests = State()

    # 7. BIO
    bio = State()

    # 8. Підтвердження анкети (перед збереженням у БД)
    confirm = State()


class EditProfileStates(StatesGroup):
    # Меню редагування
    menu = State()

    # Окремі поля для редагування
    name = State()
    nickname = State()

    region = State()
    location_type = State()
    city = State()
    village = State()

    age = State()
    status = State()
    interests = State()
    bio = State()