"""
Главный модуль бота с правильным онбордингом - ИСПРАВЛЕН
"""
import asyncio
import logging
from aiogram import Bot, Dispatcher, types
from aiogram.fsm.storage.redis import RedisStorage
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import Update, ErrorEvent
from aiogram.client.default import DefaultBotProperties

from app.config import settings
from app.middlewares import register_all_middlewares
from app.database.connection import init_db

# 🆕 Импорты для онбординга
from app.handlers.onboarding import create_onboarding_router, setup_onboarding_logging
from app.middlewares.onboarding_check import OnboardingCheckMiddleware

from app.handlers.simple_support import register_simple_support_handlers, support_handler
#from app.handlers.enhanced_support import register_enhanced_support_handlers

from app.handlers.simple_support import support_handler
#from app.handlers.enhanced_support import enhanced_support

from app.services.video_uniquifier_service import video_uniquifier_service
from app.handlers.video_uniquifier_handler import register_video_uniquifier_handlers

from app.services.automated_messaging import start_automated_messaging_worker

from app.handlers import crypto_payment_handler

# 🆕 Импорты для новых функций статистики и отчетов
from app.services.daily_reports_scheduler import DailyReportsScheduler




from aiogram.enums import ParseMode

# Настройка логирования
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('bot.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Отключаем лишние логи от библиотек
logging.getLogger('aiogram.event').setLevel(logging.WARNING)
logging.getLogger('aiohttp.access').setLevel(logging.WARNING)



async def set_bot_commands(bot: Bot):
    """
    Устанавливает команды бота для всех админов из ADMIN_IDS
    """
    print("DEBUG: set_bot_commands started")
    logger.info("Setting up admin bot commands for multiple admins...")

    admin_commands = [
        types.BotCommand(command="reset_balance", description="💰 Управление балансом"),
        types.BotCommand(command="broadcast", description="📢 Рассылка"),
        types.BotCommand(command="clean_db_user", description="🗑️ Удаление пользователя"),
        types.BotCommand(command="get_info", description="📊 Ежедневный отчет"),
        types.BotCommand(command="segments", description="📈 Статистика по сегментам"),
    ]

    print(f"DEBUG: Created {len(admin_commands)} commands")
    
    try:
        # Сначала очищаем глобальные команды
        await bot.delete_my_commands()
        print("DEBUG: Cleared global commands")
        
        # Получаем список всех админов
        admin_ids = settings.admin_ids_list
        print(f"DEBUG: Found {len(admin_ids)} admins: {admin_ids}")
        logger.info(f"👥 Setting commands for admins: {admin_ids}")
        
        # Устанавливаем команды для каждого админа
        for admin_id in admin_ids:
            try:
                await bot.set_my_commands(
                    commands=admin_commands,
                    scope=types.BotCommandScopeChat(chat_id=admin_id)
                )
                print(f"DEBUG: Commands set for admin {admin_id}")
                logger.info(f"✅ Admin commands set for user {admin_id}")
                
            except Exception as e:
                print(f"WARNING: Failed to set commands for admin {admin_id}: {e}")
                logger.warning(f"⚠️ Failed to set commands for admin {admin_id}: {e}")
        
        print(f"DEBUG: Commands setup completed for {len(admin_ids)} admins")
        logger.info(f"✅ Admin commands setup completed for {len(admin_ids)} admins")
        
    except Exception as e:
        print(f"ERROR: Error in commands setup: {e}")
        logger.error(f"❌ Error setting bot commands: {e}")

        
        
async def on_startup(bot: Bot):
    """Функция вызывается при запуске бота"""
    logger.info("🚀 Bot startup initiated")
    
    try:
        # Получаем информацию о боте
        bot_info = await bot.get_me()
        logger.info(f"✅ Bot connected: @{bot_info.username} (ID: {bot_info.id})")
        
        # Логируем информацию об админах
        admin_ids = settings.admin_ids_list
        logger.info(f"👥 Configured admins ({len(admin_ids)}): {admin_ids}")
        print(f"DEBUG: Configured admins: {admin_ids}")
        
        # Очищаем webhook если установлен
        webhook_info = await bot.get_webhook_info()
        if webhook_info.url:
            await bot.delete_webhook()
            logger.info("🗑️ Webhook cleared")
        
        # Проверяем и очищаем pending updates
        updates = await bot.get_updates()
        if updates:
            logger.info(f"🔄 Clearing {len(updates)} pending updates")
            await bot.get_updates(offset=updates[-1].update_id + 1)
        
        # Устанавливаем команды для всех админов
        await set_bot_commands(bot)
        
        logger.info("✅ Bot startup completed successfully")
        print("DEBUG: Bot startup completed")
        
    except Exception as e:
        logger.error(f"❌ Error during bot startup: {e}")
        print(f"ERROR: Startup error: {e}")
        raise

async def on_shutdown(bot: Bot):
    """Функция вызывается при остановке бота"""
    logger.info("🛑 Bot shutdown initiated")
    await bot.session.close()
    logger.info("✅ Bot shutdown completed")

async def handle_update_error(error_event: ErrorEvent):
    """Обработка ошибок в обновлениях"""
    logger.error(f"❌ Update error: {error_event.exception}")
    logger.error(f"Update content: {error_event.update}")
    
    # Пытаемся отправить сообщение пользователю об ошибке
    try:
        if error_event.update.message:
            await error_event.update.message.answer(
                "🔧 Произошла техническая ошибка. Попробуйте позже или обратитесь в поддержку."
            )
        elif error_event.update.callback_query:
            await error_event.update.callback_query.answer(
                "🔧 Произошла техническая ошибка.",
                show_alert=True
            )
    except Exception as e:
        logger.error(f"❌ Failed to send error message to user: {e}")
    
    return True

async def register_handlers_in_correct_order(dp: Dispatcher):
    """
    🚨 КРИТИЧЕСКИ ВАЖНО: Регистрация handlers в правильном порядке
    """
    logger.info("🔧 Starting handler registration in CORRECT order...")
    
    
    
    # 🔥 АДМИНСКИЕ ХЕНДЛЕРЫ (высший приоритет)
    logger.info("🔑 Registering ADMIN DELETE USER handlers...")
    try:
        from app.handlers.admin_delete_user import router as admin_delete_router
        dp.include_router(admin_delete_router)
        logger.info("✅ Admin delete user router registered")
    except ImportError as e:
        logger.warning(f"⚠️ Admin delete user router not found: {e}")
        

    
    # 🆕 0. BROADCAST - САМЫЙ ВЫСОКИЙ ПРИОРИТЕТ для админа!
    logger.info("📢 Registering BROADCAST handlers...")
    from app.handlers.broadcast import register_broadcast_handlers
    register_broadcast_handlers(dp)

    # 🆕 BROADCAST SEGMENTS - новые сегменты для рассылки
    logger.info("📊 Registering BROADCAST SEGMENTS handlers...")
    try:
        from app.handlers.broadcast.broadcast_segments import router as segments_router
        dp.include_router(segments_router)
        logger.info("✅ Broadcast segments router registered")
    except ImportError as e:
        logger.warning(f"⚠️ Broadcast segments router not found: {e}")

    # 🆕 REPORTS - админские отчеты и статистика
    logger.info("📊 Registering ADMIN REPORTS handlers...")
    try:
        from app.handlers.admin.reports import router as reports_router
        dp.include_router(reports_router)
        logger.info("✅ Admin reports router registered")
    except ImportError as e:
        logger.warning(f"⚠️ Admin reports router not found: {e}")
    
    # ADMIN - админские функции
    logger.info("🔧 Registering ADMIN handlers...")
    from app.handlers.admin_menu import register_admin_handlers
    register_admin_handlers(dp)
    
    # 🔄 RESET COMMAND - сброс пользователя
    logger.info("🔄 Registering RESET COMMAND handler...")
    try:
        from app.handlers.reset_command import router as reset_router
        dp.include_router(reset_router)
        logger.info("✅ Reset command router registered")
    except ImportError as e:
        logger.warning(f"⚠️ Reset command router not found: {e}")
    
    # 10. Унификатор видео
    logger.info("🎬 Registering VIDEO UNIQUIFIER handlers...")
    register_video_uniquifier_handlers(dp)
    
    # CRYPTO PAYMENT - криптовалюты
    logger.info("🔐 Registering CRYPTO PAYMENT handlers...")
    dp.include_router(crypto_payment_handler.router)
    
    # 🎯 1. ПОДДЕРЖКА - САМЫЙ ВЫСОКИЙ ПРИОРИТЕТ!
    logger.info("👨‍💼 Registering SUPPORT handlers...")
    # register_enhanced_support_handlers(dp)
    register_simple_support_handlers(dp)
        
    # 🆕 1. ПЕРВЫМ регистрируем onboarding router (САМЫЙ ВЫСОКИЙ ПРИОРИТЕТ!)
    if settings.ONBOARDING_ENABLED:
        logger.info("🎯 Creating onboarding router...")
        onboarding_router = create_onboarding_router()
        
        # Настройка логирования онбординга
        setup_onboarding_logging(onboarding_router)
        
        # РЕГИСТРИРУЕМ ПЕРВЫМ - САМЫЙ ВЫСОКИЙ ПРИОРИТЕТ!
        dp.include_router(onboarding_router)
        logger.info("✅ Onboarding router registered FIRST (HIGHEST PRIORITY)")
        
        # 🔍 ОТЛАДКА: Проверяем количество handlers
        message_handlers_count = len(onboarding_router.message.handlers)
        callback_handlers_count = len(onboarding_router.callback_query.handlers)
        logger.info(f"📊 Onboarding router: messages={message_handlers_count}, callbacks={callback_handlers_count}")
        
        # Выводим все message handlers для отладки
        for i, handler in enumerate(onboarding_router.message.handlers):
            handler_name = handler.callback.__name__ if hasattr(handler.callback, '__name__') else str(handler.callback)
            logger.info(f"   📝 Message handler {i}: {handler_name}")
    else:
        logger.warning("⚠️ Onboarding router NOT registered - onboarding disabled")
        
    # 0. DEBUG SUPPORT (только для отладки) - ПЕРВЫМ!
    # logger.info("🔍 Registering DEBUG SUPPORT handlers...")
    # from app.debug_support import register_debug_support_handlers
    # register_debug_support_handlers(dp)
    



    # 2. SUPPORT - высокий приоритет (админ + пользователи)
    logger.info("👨‍💼 Registering SUPPORT handlers...")
    from app.handlers.support import register_support_handlers
    register_support_handlers(dp)
    
    # 3. MAIN MENU - для завершивших онбординг
    logger.info("🎛️ Registering MAIN MENU handlers...")
    from app.handlers.main_menu import register_main_menu_handlers
    register_main_menu_handlers(dp)
    
    # 4. START - для завершивших онбординг
    # logger.info("🏁 Registering START handlers...")
    # from app.handlers.start import register_start_handlers
    # register_start_handlers(dp)
        
    # 5. REFERRAL - реферальные ссылки
    logger.info("💰 Registering REFERRAL handlers...")
    from app.handlers.referral import register_referral_handlers
    register_referral_handlers(dp)
    
    # 6. STATS - статистика
    logger.info("📊 Registering STATS handlers...")
    from app.handlers.stats import register_stats_handlers
    register_stats_handlers(dp)
    
    # 7. INSTRUCTIONS - материалы
    logger.info("📚 Registering INSTRUCTIONS handlers...")
    from app.handlers.instructions import register_instructions_handlers
    register_instructions_handlers(dp)
    
    # 8. FAQ - вопросы
    logger.info("❓ Registering FAQ handlers...")
    from app.handlers.faq import register_faq_handlers
    register_faq_handlers(dp)
    
    # 9. CLEAR KEYBOARD - очистка клавиатуры
    logger.info("🧹 Registering CLEAR KEYBOARD handlers...")
    from app.handlers.clear_keyboard import register_clear_handlers
    register_clear_handlers(dp)
    

    
    # 🔍 ФИНАЛЬНАЯ ОТЛАДКА: Общее количество handlers
    total_message_handlers = len(dp.message.handlers)
    total_callback_handlers = len(dp.callback_query.handlers)
    logger.info(f"📊 TOTAL handlers registered: messages={total_message_handlers}, callbacks={total_callback_handlers}")
    
    logger.info("✅ All handlers registered in CORRECT order: Onboarding → Support → Others")

async def main():
    """Основная функция запуска бота"""
    logger.info("🔥 Starting ReferralBot with Onboarding...")
    
    # Логирование конфигурации (безопасно)
    logger.info(f"BOT_TOKEN: ...{settings.BOT_TOKEN[-8:]}")
    logger.info(f"REDIS_URL: {settings.REDIS_URL}")
    logger.info(f"DATABASE_URL: ...{settings.DATABASE_URL[-20:]}")
    logger.info(f"ONBOARDING_ENABLED: {settings.ONBOARDING_ENABLED}")
    
    try:
        # Инициализация бота
        logger.info("📱 Initializing bot...")
        bot = Bot(token=settings.BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
        
        # Инициализация хранилища
        logger.info("💾 Initializing Memory storage...")
        storage = MemoryStorage()
        
        # Инициализация диспетчера
        dp = Dispatcher(storage=storage)
        
        # Установка обработчиков событий
        dp.startup.register(on_startup)
        dp.shutdown.register(on_shutdown)
        dp.errors.register(handle_update_error)
        
        # 🆕 Регистрация middleware для онбординга (ВАЖНО: ПЕРВЫМ!)
        logger.info("🔧 Registering onboarding middleware...")
        dp.message.middleware(OnboardingCheckMiddleware())
        dp.callback_query.middleware(OnboardingCheckMiddleware())
        
        # Регистрация существующих middleware
        logger.info("🔧 Registering existing middlewares...")
        register_all_middlewares(dp)
        
        # 🚨 РЕГИСТРАЦИЯ HANDLERS В ПРАВИЛЬНОМ ПОРЯДКЕ!
        await register_handlers_in_correct_order(dp)
        
        # Инициализация БД
        logger.info("🗄️ Initializing database...")
        await init_db()
        
        # 🆕 Обновляем admin_id в поддержке
        # enhanced_support.admin_id = settings.ADMIN_ID
        support_handler.admin_id = settings.ADMIN_ID
        logger.info(f"👨‍💼 Support admin set to: {settings.ADMIN_ID}")
        
        # 🆕 Инициализация Google Sheets - ОТКЛЮЧЕНО
        # try:
        #     from app.services.google_sheets import init_google_sheets
        #     await init_google_sheets()
        # except Exception as e:
        #     logger.warning(f"⚠️ Google Sheets initialization failed: {e}")

        # 🆕 Инициализация Support Chat Logger - ОТКЛЮЧЕНО
        # try:
        #     from app.services.support_chat_logger import init_support_chat_logger
        #     await init_support_chat_logger()
        # except Exception as e:
        #     logger.warning(f"⚠️ Support Chat Logger initialization failed: {e}")

        # 🆕 Инициализация AI автоответов - ОТКЛЮЧЕНО
        # try:
        #     from app.services.auto_answers import init_auto_answers_service
        #     await init_auto_answers_service()
        # except Exception as e:
        #     logger.warning(f"⚠️ AI Auto Answers initialization failed: {e}")
            
            
        # 🆕 Создание видео-уроков в БД (если их нет)
        if settings.ONBOARDING_ENABLED:
            await init_course_videos()
        
        # 🆕 УСТАНОВКА КОМАНД ПОСЛЕ НАСТРОЙКИ БОТА
        await set_bot_commands(bot)

        asyncio.create_task(start_automated_messaging_worker(bot))

        # 🆕 Запуск планировщика ежедневных отчетов
        try:
            from datetime import time as dt_time
            daily_scheduler = DailyReportsScheduler(bot, send_time=dt_time(9, 0))  # Отправка в 09:00
            await daily_scheduler.start()
            logger.info("✅ Daily reports scheduler started (09:00)")
        except Exception as e:
            logger.error(f"❌ Failed to start daily reports scheduler: {e}")

        # Запуск polling
        logger.info("🚀 Starting polling...")
        await dp.start_polling(
            bot,
            skip_updates=True,
            allowed_updates=['message', 'callback_query']
        )
        
    except Exception as e:
        logger.error(f"💥 Bot crashed: {str(e)}", exc_info=True)
        raise
    finally:
        logger.info("🔚 Bot session closed")
        
        

async def init_course_videos():
    """Инициализация видео-уроков в базе данных"""
    try:
        from app.database.connection import AsyncSessionLocal
        from app.database.crud import CourseVideoCRUD
        from app.utils.constants import COURSE_STRUCTURE
        from app.config import get_course_video_id
        
        logger.info("📹 Initializing course videos in database...")
        
        async with AsyncSessionLocal() as session:
            # Проверяем существующие видео
            existing_videos = await CourseVideoCRUD.get_all_videos(session)
            existing_lesson_numbers = {video.lesson_number for video in existing_videos}
            
            # Создаем недостающие видео
            created_count = 0
            for lesson_num, lesson_data in COURSE_STRUCTURE.items():
                if lesson_num not in existing_lesson_numbers:
                    video_file_id = get_course_video_id(lesson_num)
                    
                    await CourseVideoCRUD.create_video(
                        session=session,
                        lesson_number=lesson_num,
                        title=lesson_data["title"],
                        description=lesson_data["description"],
                        video_file_id=video_file_id,
                        duration_seconds=lesson_data["duration"] * 60
                    )
                    created_count += 1
            
            if created_count > 0:
                logger.info(f"✅ Created {created_count} course video records")
            else:
                logger.info("ℹ️ All course videos already exist in database")
                
    except Exception as e:
        logger.error(f"❌ Error initializing course videos: {e}", exc_info=True)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("🛑 Bot stopped by user")
    except Exception as e:
        logger.error(f"💥 Fatal error: {e}", exc_info=True)