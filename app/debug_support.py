"""
ОТЛАДОЧНЫЙ ИНСТРУМЕНТ для диагностики системы поддержки
Файл: app/debug_support.py
"""
import logging
from aiogram import Router, types, F
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from datetime import datetime
import re

from app.database.connection import AsyncSessionLocal
from app.database.crud import UserCRUD
from app.database.models import OnboardingStage
from app.config import settings

logger = logging.getLogger(__name__)
router = Router()

# ID админа
ADMIN_ID = settings.ADMIN_ID

# Глобальное хранилище для отладки
debug_storage = {
    "admin_messages": [],
    "user_messages": [],
    "admin_message_links": {},
    "middleware_logs": []
}

@router.message(F.text == "/debug_support")
async def debug_support_status(message: types.Message):
    """Команда для отладки состояния поддержки"""
    if message.from_user.id != ADMIN_ID:
        await message.answer("❌ Команда только для админа")
        return
    
    logger.info(f"🔍 DEBUG: Support status requested by admin {message.from_user.id}")
    
    try:
        # Проверяем статус админа в БД
        async with AsyncSessionLocal() as session:
            admin_user = await UserCRUD.get_user_by_telegram_id(session, ADMIN_ID)
        
        # Импортируем хранилище из support.py
        try:
            from app.handlers.support import admin_message_to_user, user_last_message_time
            current_links = admin_message_to_user
            current_users = user_last_message_time
        except ImportError:
            current_links = {}
            current_users = {}
        
        debug_info = f"""
🔍 <b>ОТЛАДКА СИСТЕМЫ ПОДДЕРЖКИ</b>

🤖 <b>Информация о боте:</b>
• Bot ID: {(await message.bot.get_me()).id}
• Admin ID: {ADMIN_ID}

👤 <b>Статус админа в БД:</b>
• Найден: {'✅' if admin_user else '❌'}
• Onboarding stage: {admin_user.onboarding_stage if admin_user else 'Не найден'}
• Ref code: {admin_user.ref_code if admin_user else 'Не найден'}

🔗 <b>Активные связи (admin_msg_id → user_id):</b>
{chr(10).join([f"• {msg_id} → {user_id}" for msg_id, user_id in current_links.items()]) if current_links else "• Нет активных связей"}

👥 <b>Пользователи с таймерами:</b>
{chr(10).join([f"• {user_id}: {time}" for user_id, time in current_users.items()]) if current_users else "• Нет активных таймеров"}

📊 <b>Статистика отладки:</b>
• Сообщений от админа: {len(debug_storage['admin_messages'])}
• Сообщений от пользователей: {len(debug_storage['user_messages'])}
• Middleware логов: {len(debug_storage['middleware_logs'])}
"""
        
        await message.reply(debug_info, parse_mode="HTML")
        logger.info("✅ Debug info sent to admin")
        
    except Exception as e:
        await message.reply(f"❌ Ошибка отладки: {str(e)}")
        logger.error(f"❌ Debug error: {e}", exc_info=True)

@router.message(F.text == "/debug_clear")
async def debug_clear_storage(message: types.Message):
    """Очистка отладочного хранилища"""
    if message.from_user.id != ADMIN_ID:
        return
    
    debug_storage.clear()
    debug_storage.update({
        "admin_messages": [],
        "user_messages": [],
        "admin_message_links": {},
        "middleware_logs": []
    })
    
    await message.reply("🧹 Отладочное хранилище очищено")

@router.message(F.text == "/test_reply")
async def test_reply_system(message: types.Message):
    """Тест системы Reply"""
    if message.from_user.id != ADMIN_ID:
        return
    
    logger.info(f"🧪 TEST: Reply system test by admin {message.from_user.id}")
    
    # Создаем тестовое сообщение как будто от пользователя
    test_msg = await message.answer("""
💬 <b>ТЕСТОВОЕ СООБЩЕНИЕ ОТ ПОЛЬЗОВАТЕЛЯ</b>

👤 <b>Имя:</b> Test User
🆔 <b>ID:</b> <code>123456789</code>
🅰 <b>Username:</b> @testuser
🔗 <b>Реф. код:</b> ref_TEST123
⏰ <b>Время:</b> {datetime.now().strftime('%d.%m.%Y %H:%M')}
🎯 <b>Стадия:</b> Тест

💬 <b>Сообщение:</b>
Это тестовое сообщение для проверки Reply

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📝 <b>ДЛЯ ОТВЕТА:</b> Нажмите Reply на это сообщение ⬆️
🔄 User ID: <code>123456789</code>
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
""", parse_mode="HTML")
    
    # Добавляем тестовую связь
    try:
        from app.handlers.support import admin_message_to_user
        admin_message_to_user[test_msg.message_id] = 123456789
        logger.info(f"🔗 TEST: Added test link {test_msg.message_id} → 123456789")
    except ImportError:
        logger.warning("⚠️ Could not import admin_message_to_user")
    
    await message.reply(f"🧪 Тестовое сообщение создано (ID: {test_msg.message_id}). Попробуйте Reply на него.")

# Middleware для отладки
async def debug_middleware(handler, event, data):
    """Middleware для отладки всех сообщений"""
    user_id = event.from_user.id
    is_admin = user_id == ADMIN_ID
    
    debug_entry = {
        "timestamp": datetime.now().isoformat(),
        "user_id": user_id,
        "is_admin": is_admin,
        "message_type": type(event).__name__,
        "text": getattr(event, 'text', None),
        "reply_to_message_id": getattr(event.reply_to_message, 'message_id', None) if hasattr(event, 'reply_to_message') and event.reply_to_message else None
    }
    
    debug_storage["middleware_logs"].append(debug_entry)
    
    # Логируем подробно
    logger.info(f"🔍 MIDDLEWARE DEBUG: {debug_entry}")
    
    if is_admin:
        debug_storage["admin_messages"].append(debug_entry)
        logger.info(f"🔑 ADMIN MESSAGE: {event.text[:50] if hasattr(event, 'text') else 'No text'}")
    else:
        debug_storage["user_messages"].append(debug_entry)
        logger.info(f"👤 USER MESSAGE: {event.text[:50] if hasattr(event, 'text') else 'No text'}")
    
    return await handler(event, data)

@router.message(F.text == "/debug_handlers")
async def debug_handlers_order(message: types.Message):
    """Отладка порядка handlers"""
    if message.from_user.id != ADMIN_ID:
        return
    
    # Получаем информацию о handlers в диспетчере
    try:
        # Это будет работать, если вызвать из активного диспетчера
        dp = message.bot.dispatcher if hasattr(message.bot, 'dispatcher') else None
        
        if dp:
            handlers_info = f"""
🔍 <b>ИНФОРМАЦИЯ О HANDLERS</b>

📝 <b>Message handlers:</b> {len(dp.message.handlers)}
🔄 <b>Callback handlers:</b> {len(dp.callback_query.handlers)}

📋 <b>Message handlers (первые 10):</b>
"""
            
            for i, handler in enumerate(dp.message.handlers[:10]):
                handler_name = getattr(handler.callback, '__name__', 'Unknown')
                filters_info = str(handler.filters) if hasattr(handler, 'filters') else 'No filters'
                handlers_info += f"• {i}: {handler_name} ({filters_info[:50]}...)\n"
        else:
            handlers_info = "❌ Не удалось получить информацию о диспетчере"
        
        await message.reply(handlers_info, parse_mode="HTML")
        
    except Exception as e:
        await message.reply(f"❌ Ошибка получения информации о handlers: {str(e)}")

@router.message(F.text.startswith("/debug_msg"))
async def debug_specific_message(message: types.Message):
    """Отладка конкретного сообщения"""
    if message.from_user.id != ADMIN_ID:
        return
    
    parts = message.text.split()
    if len(parts) < 2:
        await message.reply("Использование: /debug_msg <message_id>")
        return
    
    try:
        msg_id = int(parts[1])
        
        # Ищем в хранилище связей
        try:
            from app.handlers.support import admin_message_to_user
            user_id = admin_message_to_user.get(msg_id)
            
            if user_id:
                info = f"✅ Сообщение {msg_id} связано с пользователем {user_id}"
            else:
                info = f"❌ Сообщение {msg_id} не найдено в связях"
                info += f"\n\n🔗 Доступные связи: {list(admin_message_to_user.keys())}"
        except ImportError:
            info = "❌ Не удалось импортировать admin_message_to_user"
        
        await message.reply(info)
        
    except ValueError:
        await message.reply("❌ Неверный формат message_id")

def register_debug_support_handlers(dp):
    """Регистрация отладочных handlers"""
    dp.include_router(router)
    
    # Добавляем middleware для отладки
    dp.message.middleware(debug_middleware)
    dp.callback_query.middleware(debug_middleware)