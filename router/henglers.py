from aiogram.types import CallbackQuery
from state import EditProfileStates
from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from keyboard.reply import edit_menu_kb
# send_edit_menu вже є у нас з /edit
router_hengler = Router()

@router_hengler.callback_query(F.data == "view_edit")
async def view_edit_callback(callback: CallbackQuery, state: FSMContext):
    # Переключаємося в меню редагування
    await state.set_state(EditProfileStates.menu)
    await callback.message.answer(
        "Обери, що хочеш змінити 👇",
        reply_markup=edit_menu_kb(),
    )
    await callback.answer()


@router_hengler.callback_query(F.data == "view_match")
async def view_match_callback(callback: CallbackQuery, state: FSMContext):
    # Поки що заглушка – тут потім буде логіка метчінгу
    await callback.message.answer(
        "Тут скоро буде пошук метчів 🤝\n"
        "Коли реалізуємо логіку метчінгу, я підв’яжу її сюди."
    )
    await callback.answer()
