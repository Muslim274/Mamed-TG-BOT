import asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command

# Вставь сюда свой токен
BOT_TOKEN = '7905682144:AAHW1S4buCfCc30a8aQ1ETs4rCewc9UJVwE'

async def main():
    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher()

    @dp.message(Command("start"))
    async def cmd_start(message: types.Message):
        await message.answer("Пришли мне круговое видео (video note), и я пришлю тебе его file_id.")

    @dp.message(lambda message: message.video_note is not None)
    async def video_note_handler(message: types.Message):
        file_id = message.video_note.file_id
        await message.answer(f"file_id:\n<code>{file_id}</code>", parse_mode="HTML")

    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
