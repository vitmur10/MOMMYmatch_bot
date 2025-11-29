import os
from fastapi import FastAPI, Request
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import Update

from config import TOKEN
from router import all_routers

# ==========================
# URL вебхука (Telegram → наш сервер)
# Береться з ENV: WEBHOOK_URL=https://your-app.com/webhook
# ==========================
WEBHOOK_URL = os.getenv("WEBHOOK_URL")

# ==========================
# Ініціалізація Telegram-бота та диспетчера
# ==========================
bot = Bot(token=TOKEN)

# Пам'яткова FSM (тримання станів у RAM)
# У продакшені можна замінити на RedisStorage
dp = Dispatcher(storage=MemoryStorage())

# Підключаємо всі наші роутери (команди, стейти, матчинг)
for router in all_routers:
    dp.include_router(router)

# ==========================
# Ініціалізація FastAPI (наші HTTP endpoints)
# ==========================
app = FastAPI()


# ==========================
# Проста перевірка працездатності сервера
# ==========================
@app.get("/")
async def healthcheck():
    return {"status": "ok"}


# ==========================
# Подія запуску FastAPI
# Встановлюємо вебхук для Telegram
# ==========================
@app.on_event("startup")
async def on_startup():
    if WEBHOOK_URL:
        # Встановлюємо Telegram → наш сервер (webhook)
        await bot.set_webhook(WEBHOOK_URL, drop_pending_updates=True)
        print(f"✅ Webhook set to: {WEBHOOK_URL}")
    else:
        # Щоб контейнер/GCP не падав, якщо забули змінну
        print("⚠ WEBHOOK_URL не заданий — вебхук не буде встановлений")


# ==========================
# Закриття сесії бота при зупинці сервера
# ==========================
@app.on_event("shutdown")
async def on_shutdown():
    await bot.session.close()


# ==========================
# Головний endpoint вебхука Telegram
# Сюди Telegram надсилає кожну подію (Update)
# ==========================
@app.post("/webhook")
async def telegram_webhook(request: Request):
    # Отримуємо JSON з Telegram
    data = await request.json()

    # Перетворюємо на Update Aiogram
    update = Update.model_validate(data)

    # Передаємо апдейти в диспетчер для обробки
    await dp.feed_update(bot, update)

    return {"ok": True}
