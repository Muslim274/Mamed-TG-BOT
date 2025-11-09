# app/middlewares/admin_middleware.py
"""
Middleware для проверки прав администратора
"""
import logging
from typing import Callable, Dict, Any, Awaitable
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Message, CallbackQuery

from app.config import settings, is_admin

logger = logging.getLogger(__name__)

class AdminOnlyMiddleware(BaseMiddleware):
    """Middleware для проверки прав администратора"""
    
    def __init__(self, admin_commands: set = None):
        """
        Args:
            admin_commands: Набор команд, доступных только админу
        """
        self.admin_commands = admin_commands or {
            "-clean_db_user-",
            "-broadcast-",
            "/admin",
            "/stats"
        }
    
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        """Проверка прав администратора"""
        
        # Получаем пользователя из события
        user = None
        message_text = ""
        
        if isinstance(event, Message):
            user = event.from_user
            message_text = event.text or ""
        elif isinstance(event, CallbackQuery):
            user = event.from_user
            message_text = event.data or ""
        
        # Если пользователь не определен, пропускаем
        if not user:
            return await handler(event, data)
        
        # Проверяем, является ли сообщение админской командой
        is_admin_command = any(
            cmd in message_text for cmd in self.admin_commands
        )
        
        # Если это не админская команда, пропускаем проверку
        if not is_admin_command:
            return await handler(event, data)
        
        # Проверяем права админа
        if not is_admin(user.id):
            logger.warning(
                f"Non-admin user {user.id} (@{user.username}) "
                f"tried to access admin command: {message_text[:50]}"
            )

            # Отправляем предупреждение
            if isinstance(event, Message):
                await event.answer("❌ У вас нет прав для выполнения этой команды")
            elif isinstance(event, CallbackQuery):
                await event.answer("❌ Недостаточно прав", show_alert=True)

            return  # Блокируем выполнение
        
        # Логируем админскую активность
        logger.info(
            f"Admin {user.id} (@{user.username}) "
            f"executed admin command: {message_text[:50]}"
        )
        
        # Разрешаем выполнение
        return await handler(event, data)


# Функция для регистрации middleware
def register_admin_middleware(dp):
    """Регистрация middleware для админских команд"""
    admin_middleware = AdminOnlyMiddleware()
    
    # Регистрируем для сообщений и callback-запросов
    dp.message.middleware(admin_middleware)
    dp.callback_query.middleware(admin_middleware)
    
    logger.info("✅ Admin middleware registered")
