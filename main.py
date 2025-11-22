from config import TOKEN
from router import all_routers
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram import Bot, Dispatcher
import asyncio

async def main():
    bot = Bot(token=TOKEN)
    dp = Dispatcher(storage=MemoryStorage())

    # 👇 інжектимо бота в модуль нагадувань, щоб не потрібен був env

    # стартуємо фоновий цикл днів народження

    for router in all_routers:
        dp.include_router(router)

    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)



if __name__ == "__main__":
    asyncio.run(main())