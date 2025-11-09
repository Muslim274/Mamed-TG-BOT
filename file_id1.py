from aiogram import Bot, Dispatcher, types
from aiogram.types import Message
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart
from aiogram.fsm.storage.memory import MemoryStorage
import asyncio
import logging

# 🔒 Токен бота
BOT_TOKEN = "7905682144:AAHW1S4buCfCc30a8aQ1ETs4rCewc9UJVwE"

# 🔧 Логгирование
logging.basicConfig(level=logging.INFO)

# 🧠 Память FSM и запуск
bot = Bot(token=BOT_TOKEN, parse_mode=ParseMode.HTML)
dp = Dispatcher(storage=MemoryStorage())


@dp.message(CommandStart())
async def cmd_start(message: Message):
    await message.answer("👋 Отправь мне <b>круглое видео</b>, и я верну его <code>file_id</code>.")


@dp.message()
async def handle_video_note(message: Message):
    if message.video_note:
        file_id = message.video_note.file_id
        await message.answer(f"🎥 <b>file_id:</b>\n<code>{file_id}</code>")
    else:
        await message.answer("Пожалуйста, отправь именно <b>круглое видео</b> (video note).")


async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
