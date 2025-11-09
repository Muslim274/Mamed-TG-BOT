#!/usr/bin/env python3
"""
Отправляет видео как круглое видеосообщение (video_note)
и печатает полученный file_id.

Использование:
    python get_round_file_id.py --token BOT_TOKEN --chat CHAT_ID round_video.mp4
"""

import asyncio, argparse, pathlib, sys
from aiogram import Bot
from aiogram.types import FSInputFile


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("video", help="Путь к подготовленному круглому видеофайлу")
    parser.add_argument("--token", required=True, help="Токен бота")
    parser.add_argument("--chat", required=True, type=int, help="ID чата для отправки (твой ID или тест-чат)")
    args = parser.parse_args()

    video_path = pathlib.Path(args.video).expanduser().resolve()
    if not video_path.exists():
        sys.exit(f"Файл {video_path} не найден")

    bot = Bot(args.token)
    msg = await bot.send_video_note(
        args.chat,
        FSInputFile(str(video_path)),
    )
    print("✅ Корректный file_id для круглого видео:", msg.video_note.file_id)
    print("   Telegram сохранил длительность:", msg.video_note.duration, "сек")
    await bot.session.close()

if __name__ == "__main__":
    asyncio.run(main())