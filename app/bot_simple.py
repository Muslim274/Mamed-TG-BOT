"""
Упрощенная версия бота для диагностики network timeout
"""
import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.client.telegram import TelegramAPIServer
from aiogram.fsm.storage.redis import RedisStorage
from aiogram.types import Update, ErrorEvent

from app.config import settings
from app.handlers import register_all_handlers
from app.middlewares import register_all_middlewares
from app.database.connection import init_db

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/root/telegram-referral-bot/bot.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Отключаем лишние логи
logging.getLogger('aiogram.event').setLevel(logging.WARNING)
logging.getLogger('aiohttp.access').setLevel(logging.WARNING)

async def on_startup(bot: Bot):
    """Функция вызывается при запуске бота"""
    logger.info("🚀 Bot startup initiated")
    
    try:
        # Увеличиваем таймаут для get_me
        logger.info("🔍 Checking bot info with extended timeout...")
        bot_info = await bot.get_me(request_timeout=30)
        logger.info(f"✅ Bot connected: @{bot_info.username} (ID: {bot_info.id})")
        
        # Проверяем webhook
        webhook_info = await bot.get_webhook_info(request_timeout=30)
        if webhook_info.url:
            await bot.delete_webhook(request_timeout=30)
            logger.info("🗑️ Webhook cleared")
        
        # Проверяем pending updates
        logger.info("🔄 Checking pending updates...")
        updates = await bot.get_updates(request_timeout=30)
        if updates:
            logger.info(f"🔄 Clearing {len(updates)} pending updates")
            await bot.get_updates(offset=updates[-1].update_id + 1, request_timeout=30)
        
        logger.info("✅ Bot startup completed successfully")
        
    except Exception as e:
        logger.error(f"❌ Startup failed: {e}", exc_info=True)
        raise

async def on_shutdown(bot: Bot):
    """Функция вызывается при остановке бота"""
    logger.info("🛑 Bot shutdown initiated")
    await bot.session.close()
    logger.info("✅ Bot shutdown completed")

async def handle_update_error(error_event: ErrorEvent):
    """Обработка ошибок в обновлениях"""
    logger.error(f"❌ Update error: {error_event.exception}")
    return True

async def main():
    """Основная функция запуска бота с расширенными таймаутами"""
    logger.info("🔥 Starting ReferralBot with extended timeouts...")
    
    try:
        # Создаем сессию с увеличенными таймаутами
        session = AiohttpSession(
            api=TelegramAPIServer.from_base('https://api.telegram.org'),
            timeout=60,  # Увеличиваем общий таймаут до 60 секунд
            connector_params={
                'keepalive_timeout': 300,
                'timeout': 60
            }
        )
        
        # Инициализация бота с кастомной сессией
        logger.info("📱 Initializing bot with extended timeouts...")
        bot = Bot(token=settings.BOT_TOKEN, session=session)

        # Инициализация хранилища
        logger.info("💾 Initializing Redis storage...")
        storage = RedisStorage.from_url(settings.REDIS_URL)
        
        # Инициализация диспетчера
        dp = Dispatcher(storage=storage)
        
        # Установка обработчиков событий
        dp.startup.register(on_startup)
        dp.shutdown.register(on_shutdown)
        dp.errors.register(handle_update_error)

        # Регистрация middleware
        logger.info("🔧 Registering middlewares...")
        register_all_middlewares(dp)

        # Регистрация handlers
        logger.info("🎯 Registering handlers...")
        register_all_handlers(dp)
        
        # Инициализация БД
        logger.info("🗄️ Initializing database...")
        await init_db()

        # Запуск polling с увеличенным таймаутом
        logger.info("🚀 Starting polling with extended timeout...")
        await dp.start_polling(
            bot,
            skip_updates=True,
            allowed_updates=['message', 'callback_query'],
            polling_timeout=30,  # Увеличиваем polling timeout
            request_timeout=30   # Увеличиваем request timeout
        )
        
    except Exception as e:
        logger.error(f"💥 Bot crashed: {str(e)}", exc_info=True)
        raise
    finally:
        logger.info("🔚 Bot session closed")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("🛑 Bot stopped by user")
    except Exception as e:
        logger.error(f"💥 Fatal error: {e}", exc_info=True)
