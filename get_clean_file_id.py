#!/usr/bin/env python3
"""
Отправляет видео одним сообщением, задаёт правильные width/height
и печатает полученный file_id.

Использование:
    python get_clean_file_id.py --token BOT_TOKEN --chat CHAT_ID video2.mp4
"""

import asyncio, subprocess, argparse, pathlib, sys
from aiogram import Bot
from aiogram.types import FSInputFile


def probe_size(path: str) -> tuple[int, int]:
    """Возвращает (width, height) через ffprobe."""
    out = subprocess.check_output([
        "ffprobe", "-v", "error", "-select_streams", "v:0",
        "-show_entries", "stream=width,height",
        "-of", "csv=p=0:s=x", path
    ]).decode().strip()
    try:
        w, h = map(int, out.split("x"))
        return w, h
    except ValueError:
        print(f"Не удалось распарсить размеры ffprobe: {out}", file=sys.stderr)
        sys.exit(1)


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("video", help="Путь к видеофайлу")
    parser.add_argument("--token", required=True, help="Токен бота")
    parser.add_argument("--chat", required=True, type=int, help="ID чата для отправки")
    args = parser.parse_args()

    video_path = pathlib.Path(args.video).expanduser().resolve()
    if not video_path.exists():
        sys.exit(f"Файл {video_path} не найден")

    w, h = probe_size(str(video_path))
    print(f"▶️  FFprobe: {w}x{h}")

    bot = Bot(args.token)
    msg = await bot.send_video(
        args.chat,
        FSInputFile(str(video_path)),
        width=w,
        height=h,
        supports_streaming=True,
    )
    print("✅ Корректный file_id:", msg.video.file_id)
    print("   Telegram сохранил:", msg.video.width, "x", msg.video.height)
    await bot.session.close()

if __name__ == "__main__":
    asyncio.run(main())
