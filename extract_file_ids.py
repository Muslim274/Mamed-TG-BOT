# -*- coding: utf-8 -*-
"""
Script dlya izvlecheniya file_id iz dokumentov i foto
Otpravte dokumenty/foto v chat s etim botom, i on vernyot vam file_id
"""
import asyncio
import sys
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from app.config import settings

# Fix console encoding
if sys.platform == 'win32':
    import codecs
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
    sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')

async def main():
    bot = Bot(token=settings.BOT_TOKEN)
    dp = Dispatcher()

    @dp.message(Command("start"))
    async def cmd_start(message: types.Message):
        await message.answer(
            "Otpravte mne dokumenty ili foto, i ya vernu vam file_id\n\n"
            "Send me documents or photos and I will return you their file_id"
        )

    @dp.message(F.document)
    async def document_handler(message: types.Message):
        file_id = message.document.file_id
        file_name = message.document.file_name or "Unknown"

        response = f"FILE ID (Document: {file_name}):\n<code>{file_id}</code>"

        await message.answer(response, parse_mode="HTML")
        print(f"Document: {file_name} -> {file_id}")

    @dp.message(F.photo)
    async def photo_handler(message: types.Message):
        # Beryon samoe bolshoe foto (luchshee kachestvo)
        file_id = message.photo[-1].file_id

        response = f"FILE ID (Photo):\n<code>{file_id}</code>"

        await message.answer(response, parse_mode="HTML")
        print(f"Photo -> {file_id}")

    print("Bot zapushchen! Otpravte dokumenty ili foto...")
    print(f"Bot username: @{(await bot.get_me()).username}")

    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
