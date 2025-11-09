#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Скрипт для загрузки видео в Telegram и получения file_id
Загружает все видео и сохраняет file_id в файл
"""
import asyncio
import logging
import os
from pathlib import Path
from aiogram import Bot
from aiogram.types import FSInputFile
from app.config import settings

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)


async def upload_videos():
    """Загружает все видео и получает file_id"""
    bot = Bot(token=settings.BOT_TOKEN)
    admin_id = settings.ADMIN_ID

    # Словарь: название переменной -> путь к файлу
    videos_to_upload = {
        # Вводное видео (превью) - используем video2.mp4
        "VIDEO2_ID": "video2.mp4",

        # Уроки
        "lesson_1": "lesson_1.mp4",
        "lesson_2": "lesson_2.mp4",
        "lesson_3": "lesson_3.mp4",
        "lesson_4": "lesson_4.mp4",
        "lesson_5": "lesson_5.mp4",

        # Другие видео
        "VIDEO3_ID": "video3.mp4",
        "VIDEO7_ID": "video7.mp4",

        # Круглые видео для дожима (если нужны)
        "K_VIDEO_ID1": "k_vid1.MP4",
    }

    results = {}

    try:
        logger.info("=" * 60)
        logger.info("ЗАГРУЗКА ВИДЕО И ПОЛУЧЕНИЕ FILE_ID")
        logger.info("=" * 60)
        logger.info(f"Видео будут отправлены администратору ID: {admin_id}")
        logger.info("")

        for var_name, file_path in videos_to_upload.items():
            if not os.path.exists(file_path):
                logger.warning(f"ПРОПУЩЕНО {var_name}: файл {file_path} не найден")
                continue

            file_size_mb = os.path.getsize(file_path) / (1024 * 1024)
            logger.info(f"Загружаю {var_name} ({file_path}, {file_size_mb:.1f} MB)...")

            try:
                # Отправляем видео
                video_file = FSInputFile(file_path)
                message = await bot.send_video(
                    chat_id=admin_id,
                    video=video_file,
                    caption=f"Upload: {var_name}",
                    supports_streaming=True
                )

                # Получаем file_id
                file_id = message.video.file_id
                results[var_name] = file_id

                logger.info(f"УСПЕХ {var_name}:")
                logger.info(f"  File ID: {file_id}")
                logger.info("")

            except Exception as e:
                logger.error(f"ОШИБКА при загрузке {var_name}: {e}")
                logger.info("")

        # Сохраняем результаты в файл
        if results:
            output_file = "new_video_ids.env"
            with open(output_file, "w", encoding="utf-8") as f:
                f.write("# Новые file_id для видео\n")
                f.write("# Скопируйте эти строки в .env файл\n\n")

                for var_name, file_id in results.items():
                    f.write(f"{var_name}={file_id}\n")

            logger.info("=" * 60)
            logger.info("ГОТОВО!")
            logger.info("=" * 60)
            logger.info(f"Новые file_id сохранены в файл: {output_file}")
            logger.info("Скопируйте их в .env файл")
            logger.info("")
            logger.info("Результат:")
            for var_name, file_id in results.items():
                logger.info(f"  {var_name}={file_id}")

    finally:
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(upload_videos())
