"""
Диагностический скрипт для проверки бота - исправленная версия
"""
import asyncio
import logging
from aiogram import Bot
from app.config import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_bot():
    """Тестирование бота"""
    print("🔍 Запуск диагностики бота...")
    
    try:
        # Создаем бота
        bot = Bot(token=settings.BOT_TOKEN)
        
        # Получаем информацию о боте
        bot_info = await bot.get_me()
        print(f"✅ Бот активен: @{bot_info.username}")
        print(f"📋 ID бота: {bot_info.id}")
        print(f"📝 Имя бота: {bot_info.first_name}")
        
        # Получаем список команд
        commands = await bot.get_my_commands()
        print(f"📚 Команды бота: {[cmd.command for cmd in commands]}")
        
        # Получаем webhook info
        webhook_info = await bot.get_webhook_info()
        print(f"🔗 Webhook URL: {webhook_info.url or 'Не установлен (используется polling)'}")
        
        # Проверяем updates
        print("\n🔄 Получение последних обновлений...")
        updates = await bot.get_updates(limit=5)
        print(f"📨 Количество необработанных обновлений: {len(updates)}")
        
        for i, update in enumerate(updates):
            if update.message:
                print(f"Update {i+1}: {update.message.text}")
            else:
                print(f"Update {i+1}: No message content")
        
        await bot.session.close()
        
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        logger.error(f"Bot test failed: {e}", exc_info=True)

async def test_database():
    """Тестирование подключения к БД"""
    print("\n🗄️ Проверка базы данных...")
    
    try:
        from app.database.connection import AsyncSessionLocal
        from app.database.crud import UserCRUD
        
        async with AsyncSessionLocal() as session:
            # Пробуем выполнить простой запрос
            user = await UserCRUD.get_user_by_telegram_id(session, 123456)
            print("✅ Подключение к БД работает")
            
    except Exception as e:
        print(f"❌ Ошибка БД: {e}")
        logger.error(f"Database test failed: {e}", exc_info=True)

async def test_handlers():
    """Тестирование регистрации хендлеров"""
    print("\n🎯 Проверка хендлеров...")
    
    try:
        from aiogram import Dispatcher
        from app.handlers import register_all_handlers
        
        dp = Dispatcher()
        register_all_handlers(dp)
        
        # Проверяем зарегистрированные роутеры (исправленная версия)
        if hasattr(dp, 'sub_routers'):
            print(f"✅ Зарегистрировано роутеров: {len(dp.sub_routers)}")
            
            # Проверяем хендлеры сообщений
            handlers_count = 0
            for router in dp.sub_routers:
                if hasattr(router, 'message') and hasattr(router.message, 'handlers'):
                    handlers_count += len(router.message.handlers)
                if hasattr(router, 'callback_query') and hasattr(router.callback_query, 'handlers'):
                    handlers_count += len(router.callback_query.handlers)
            
            print(f"📋 Всего хендлеров: {handlers_count}")
        else:
            print("⚠️ Новая версия aiogram - подсчет хендлеров недоступен")
            print("✅ Хендлеры зарегистрированы успешно")
        
    except Exception as e:
        print(f"❌ Ошибка хендлеров: {e}")
        logger.error(f"Handlers test failed: {e}", exc_info=True)

async def test_specific_user(user_id: int):
    """Тестирование конкретного пользователя"""
    print(f"\n👤 Проверка пользователя {user_id}...")
    
    try:
        bot = Bot(token=settings.BOT_TOKEN)
        
        # Проверяем, заблокирован ли бот пользователем
        try:
            await bot.send_chat_action(user_id, "typing")
            print(f"✅ Пользователь {user_id} не заблокировал бота")
        except Exception as e:
            error_msg = str(e).lower()
            if "chat not found" in error_msg or "blocked" in error_msg or "forbidden" in error_msg:
                print(f"❌ Пользователь {user_id} заблокировал бота или чат не найден")
            elif "user not found" in error_msg:
                print(f"❌ Пользователь {user_id} не существует")
            else:
                print(f"❓ Неизвестная ошибка с пользователем {user_id}: {e}")
        
        await bot.session.close()
        
    except Exception as e:
        print(f"❌ Ошибка проверки пользователя: {e}")

async def test_missing_files():
    """Проверка наличия необходимых файлов"""
    print("\n📁 Проверка файлов...")
    
    try:
        from app.utils.helpers import generate_ref_code
        print("✅ app/utils/helpers.py найден")
    except ImportError as e:
        print(f"❌ app/utils/helpers.py отсутствует: {e}")
    
    try:
        from app.keyboards.reply import get_main_menu
        print("✅ app/keyboards/reply.py найден")
    except ImportError as e:
        print(f"❌ app/keyboards/reply.py отсутствует: {e}")
    
    try:
        from app.keyboards.inline import get_referral_menu
        print("✅ app/keyboards/inline.py найден")
    except ImportError as e:
        print(f"❌ app/keyboards/inline.py отсутствует: {e}")

async def main():
    """Основная функция диагностики"""
    print("🚀 Запуск полной диагностики...")
    print("=" * 50)
    
    await test_bot()
    await test_database()
    await test_handlers()
    await test_missing_files()
    
    # Тестируем конкретных пользователей
    print("\n" + "=" * 50)
    print("Введите ID пользователей для проверки (через пробел):")
    print("Например: 123456789 987654321")
    print("Или нажмите Enter для пропуска")
    
    try:
        user_input = input("ID пользователей: ").strip()
        if user_input:
            user_ids = [int(uid) for uid in user_input.split()]
            for user_id in user_ids:
                await test_specific_user(user_id)
        else:
            print("⏭️ Проверка пользователей пропущена")
    except KeyboardInterrupt:
        print("\n👋 Диагностика прервана")
    except ValueError:
        print("❌ Неверный формат ID")
    
    print("\n✅ Диагностика завершена")
    print("\n💡 Рекомендации:")
    print("1. Если есть ошибки импорта - создайте недостающие файлы")
    print("2. Если пользователь заблокировал бота - попросите его разблокировать")
    print("3. Перезапустите бота после исправления ошибок")

if __name__ == "__main__":
    asyncio.run(main())