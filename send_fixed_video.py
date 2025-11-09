# send_fixed_video.py


import asyncio
from aiogram import Bot
from aiogram.types import FSInputFile

BOT_TOKEN = "7905682144:AAHW1S4buCfCc30a8aQ1ETs4rCewc9UJVwE"
CHAT_ID   = 389984255          # куда отправляем (можно свой ID)

VIDEO_PATH = "video1_fixed.mp4"
VIDEO_W    = 1280              # ← размеры из ffprobe
VIDEO_H    = 720

async def main():
    bot = Bot(BOT_TOKEN)

    msg = await bot.send_video(
        CHAT_ID,
        FSInputFile(VIDEO_PATH),
        width=VIDEO_W,          # ⚠️ задаём вручную
        height=VIDEO_H,
        supports_streaming=True
    )

    print("\n✅ Новый корректный file_id →", msg.video.file_id)
    print("   Telegram сохранил:", msg.video.width, "x", msg.video.height)

    await bot.session.close()

if __name__ == "__main__":
    asyncio.run(main())