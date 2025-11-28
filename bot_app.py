import os
from fastapi import FastAPI, Request
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import Update

from config import TOKEN
from router import all_routers  # як у тебе було

# 🔹 URL вебхука беремо з env, щоб потім легко міняти в Cloud Run
WEBHOOK_URL = os.getenv("WEBHOOK_URL")  # наприклад: https://your-domain/webhook

if not WEBHOOK_URL:
    raise RuntimeError("WEBHOOK_URL не заданий у змінних середовища")

bot = Bot(token=TOKEN)
dp = Dispatcher(storage=MemoryStorage())

for router in all_routers:
    dp.include_router(router)

app = FastAPI()


@app.on_event("startup")
async def on_startup():
    # реєструємо вебхук
    await bot.set_webhook(WEBHOOK_URL, drop_pending_updates=True)


@app.on_event("shutdown")
async def on_shutdown():
    await bot.session.close()


@app.post("/webhook")
async def telegram_webhook(request: Request):
    """Ендпоінт, куди Telegram шле оновлення."""
    data = await request.json()
    update = Update.model_validate(data)
    await dp.feed_update(bot, update)
    return {"ok": True}
