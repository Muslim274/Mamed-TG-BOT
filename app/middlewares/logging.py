"""
Middleware для логирования
"""
import logging
from typing import Callable, Dict, Any, Awaitable

from aiogram import BaseMiddleware
from aiogram.types import Message

logger = logging.getLogger(__name__)


class LoggingMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[Message, Dict[str, Any]], Awaitable[Any]],
        event: Message,
        data: Dict[str, Any]
    ) -> Any:
        user = event.from_user
        
        # Безопасное получение текста сообщения
        message_content = event.text or "[медиа-файл]"
        
        logger.info(
            f"User {user.id} (@{user.username}) sent: {message_content}"
        )
        
        return await handler(event, data)