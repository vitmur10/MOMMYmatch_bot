import os
from fastapi import FastAPI, Request
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import Update

from config import TOKEN
from router import all_routers

WEBHOOK_URL = os.getenv("WEBHOOK_URL")

bot = Bot(token=TOKEN)
dp = Dispatcher(storage=MemoryStorage())

for router in all_routers:
    dp.include_router(router)

app = FastAPI()


@app.get("/")
async def healthcheck():
    return {"status": "ok"}


@app.on_event("startup")
async def on_startup():
    if WEBHOOK_URL:
        await bot.set_webhook(WEBHOOK_URL, drop_pending_updates=True)
        print(f"✅ Webhook set to: {WEBHOOK_URL}")
    else:
        # щоб контейнер не падав, якщо забули змінну
        print("⚠ WEBHOOK_URL не заданий — вебхук не буде встановлений")


@app.on_event("shutdown")
async def on_shutdown():
    await bot.session.close()


@app.post("/webhook")
async def telegram_webhook(request: Request):
    data = await request.json()
    update = Update.model_validate(data)
    await dp.feed_update(bot, update)
    return {"ok": True}
