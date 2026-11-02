import asyncio
import logging
import os
from datetime import datetime

import aiohttp
from aiogram import Bot, Dispatcher
from aiogram.filters import Command
from aiogram.types import Message

# Токен берётся из переменных окружения (безопасно)
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("Не указан BOT_TOKEN")

API_URL = "https://tvzvezda.ru/api/v1/services/broadcast/current-playing/radiozvezda/"
POLL_INTERVAL = 30
HISTORY_SIZE = 20

last_track = None
history: list[tuple[str, datetime]] = []
subscribers: set[int] = set()

logging.basicConfig(level=logging.INFO)
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()


async def fetch_now_playing() -> str | None:
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(API_URL, timeout=10) as resp:
                if resp.status != 200:
                    return None
                data = await resp.json()
                return data.get("broadcastCurrentPlayingName")
    except Exception as e:
        logging.error(f"Ошибка API: {e}")
        return None


async def poll_loop():
    global last_track
    while True:
        track = await fetch_now_playing()
        if track and track != last_track:
            now = datetime.now()
            history.insert(0, (track, now))
            history[:] = history[:HISTORY_SIZE]

            text = f"📻 <b>Сейчас на Радио Звезда:</b>\n\n{track}"
            for chat_id in list(subscribers):
                try:
                    await bot.send_message(chat_id, text, parse_mode="HTML")
                except Exception:
                    subscribers.discard(chat_id)

            last_track = track
            logging.info(f"Новый трек: {track}")

        await asyncio.sleep(POLL_INTERVAL)


@dp.message(Command("start"))
async def cmd_start(message: Message):
    await message.answer(
        "👋 Бот Радио Звезда\n\n"
        "Команды:\n"
        "/now — что играет прямо сейчас\n"
        "/history — последние треки\n"
        "/subscribe — уведомления при смене трека\n"
        "/unsubscribe — отписаться"
    )


@dp.message(Command("now"))
async def cmd_now(message: Message):
    track = await fetch_now_playing()
    if track:
        await message.answer(f"📻 <b>Сейчас играет:</b>\n\n{track}", parse_mode="HTML")
    else:
        await message.answer("Не удалось получить данные. Попробуйте позже.")


@dp.message(Command("history"))
async def cmd_history(message: Message):
    if not history:
        await message.answer("История пока пуста.")
        return

    lines = [f"{i}. [{ts.strftime('%H:%M:%S')}] {track}" for i, (track, ts) in enumerate(history, 1)]
    await message.answer("📜 <b>Последние треки:</b>\n\n" + "\n".join(lines), parse_mode="HTML")


@dp.message(Command("subscribe"))
async def cmd_subscribe(message: Message):
    subscribers.add(message.chat.id)
    await message.answer("✅ Вы подписаны на уведомления.")


@dp.message(Command("unsubscribe"))
async def cmd_unsubscribe(message: Message):
    subscribers.discard(message.chat.id)
    await message.answer("❌ Вы отписались.")


async def main():
    asyncio.create_task(poll_loop())
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())