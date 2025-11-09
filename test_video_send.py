"""
Скрипт для тестирования отправки видео
Проверяет, работают ли file_id из .env
"""
import asyncio
import logging
from aiogram import Bot
from app.config import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def test_videos():
    """Тестирует отправку всех видео"""
    bot = Bot(token=settings.BOT_TOKEN)

    # ID администратора для теста
    admin_id = settings.ADMIN_ID

    try:
        # Тест вводного видео (превью)
        logger.info(f"📹 Тестирую вводное видео (VIDEO2_ID)...")
        logger.info(f"File ID: {settings.VIDEO2_ID[:50]}...")

        try:
            await bot.send_video(
                chat_id=admin_id,
                video=settings.VIDEO2_ID,
                caption="🎬 ТЕСТ: Вводное видео (превью)",
                supports_streaming=True
            )
            logger.info("✅ Вводное видео отправлено успешно!")
        except Exception as e:
            logger.error(f"❌ Ошибка отправки вводного видео: {e}")

        # Тест уроков
        lessons = [
            ("Урок 1", getattr(settings, "lesson_1", None)),
            ("Урок 2", getattr(settings, "lesson_2", None)),
            ("Урок 3", getattr(settings, "lesson_3", None)),
            ("Урок 4", getattr(settings, "lesson_4", None)),
            ("Урок 5", getattr(settings, "lesson_5", None)),
        ]

        for lesson_name, lesson_id in lessons:
            if lesson_id:
                logger.info(f"\n📚 Тестирую {lesson_name}...")
                logger.info(f"File ID: {lesson_id[:50]}...")

                try:
                    await bot.send_video(
                        chat_id=admin_id,
                        video=lesson_id,
                        caption=f"🎬 ТЕСТ: {lesson_name}",
                        supports_streaming=True
                    )
                    logger.info(f"✅ {lesson_name} отправлен успешно!")
                except Exception as e:
                    logger.error(f"❌ Ошибка отправки {lesson_name}: {e}")
            else:
                logger.warning(f"⚠️ {lesson_name} не найден в настройках")

        logger.info("\n✅ Все тесты завершены!")

    finally:
        await bot.session.close()


if __name__ == "__main__":
    print("Запуск теста видео...")
    print(f"Видео будут отправлены администратору ID: {settings.ADMIN_ID}")
    asyncio.run(test_videos())
