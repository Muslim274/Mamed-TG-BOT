#!/usr/bin/env python
"""
get_file_id.py  ─ утилита для получения file_id.

Пример:
    python get_file_id.py /path/to/video.mp4 389984255
    python get_file_id.py --video intro.mp4 389984255      # отправить как видео
"""
import sys
import asyncio
from pathlib import Path
from argparse import ArgumentParser

from aiogram import Bot
from aiogram.types import FSInputFile

# ────────────────────────────────────────────────────────────────────────────────
BOT_TOKEN = "7905682144:AAHW1S4buCfCc30a8aQ1ETs4rCewc9UJVwE"   # <-- свой токен
# ────────────────────────────────────────────────────────────────────────────────


async def main(file_path: Path, chat_id: int, as_video: bool):
    bot = Bot(BOT_TOKEN, parse_mode=None)

    input_file = FSInputFile(str(file_path), filename=file_path.name)

    if as_video:
        msg = await bot.send_video(chat_id, input_file, supports_streaming=True)
        media = msg.video
    else:
        msg = await bot.send_document(chat_id, input_file)
        # document может быть video или file, поэтому ищем все варианты
        media = (
            msg.document
            or msg.video
            or msg.animation
            or (msg.photo[-1] if msg.photo else None)
        )

    print("file_id:", media.file_id)
    await bot.session.close()


# ───────────────────────── CLI ─────────────────────────
if __name__ == "__main__":
    parser = ArgumentParser()
    parser.add_argument(
        "--video",
        action="store_true",
        help="Отправить как video (стримится сразу, лимит 50 МБ)",
    )
    parser.add_argument("file_path", help="Путь к файлу")
    parser.add_argument("chat_id", type=int, help="Кому отправить (ваш Telegram-ID)")

    args = parser.parse_args()

    path = Path(args.file_path).expanduser().resolve()
    if not path.exists():
        print("File not found:", path)
        sys.exit(1)

    try:
        asyncio.run(main(path, args.chat_id, args.video))
    except KeyboardInterrupt:
        sys.exit(0)
