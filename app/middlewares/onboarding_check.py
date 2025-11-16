"""
ИСПРАВЛЕННЫЙ middleware для проверки стадии онбординга с исключением админа
"""
import logging
from typing import Callable, Dict, Any, Awaitable, Union

from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery

from app.database.connection import AsyncSessionLocal
from app.database.crud import UserCRUD
from app.database.models import OnboardingStage
from app.config import settings

logger = logging.getLogger(__name__)


class OnboardingCheckMiddleware(BaseMiddleware):
    """
    Middleware для проверки стадии онбординга пользователя.
    Добавляет в data информацию о пользователе и статусе онбординга.
    """

    async def __call__(
        self,
        handler: Callable[[Union[Message, CallbackQuery], Dict[str, Any]], Awaitable[Any]],
        event: Union[Message, CallbackQuery],
        data: Dict[str, Any]
    ) -> Any:
        
        user_id = event.from_user.id
        
        # ✅ ИСКЛЮЧЕНИЕ: Админ всегда считается завершившим онбординг
        if user_id in settings.admin_ids_list:
            data['onboarding_user'] = None  # Админ может не быть в БД
            data['onboarding_completed'] = True
            data['onboarding_stage'] = OnboardingStage.COMPLETED
            data['is_admin'] = True
            return await handler(event, data)
        
        try:
            # Получаем пользователя из БД
            async with AsyncSessionLocal() as session:
                user = await UserCRUD.get_user_by_telegram_id(session, user_id)
                
                # Добавляем информацию в data для использования в handlers
                data['onboarding_user'] = user
                data['onboarding_completed'] = (
                    user and user.onboarding_stage == OnboardingStage.COMPLETED
                )
                data['onboarding_stage'] = (
                    user.onboarding_stage if user else OnboardingStage.NEW_USER
                )
                
                # Логируем для отладки
                if user:
                    logger.debug(
                        f"User {user_id} (@{event.from_user.username}) "
                        f"onboarding stage: {user.onboarding_stage}"
                    )
                else:
                    logger.debug(f"New user {user_id} (@{event.from_user.username})")
        
        except Exception as e:
            logger.error(f"Error in OnboardingCheckMiddleware: {e}")
            # В случае ошибки считаем пользователя новым
            data['onboarding_user'] = None
            data['onboarding_completed'] = False
            data['onboarding_stage'] = OnboardingStage.NEW_USER
        
        # Вызываем следующий handler
        return await handler(event, data)


class OnboardingStageMiddleware(BaseMiddleware):
    """
    Дополнительный middleware для фильтрации обновлений 
    по стадии онбординга (используется в роутерах)
    """
    
    def __init__(self, allowed_stages: list[str] = None, completed_only: bool = False):
        """
        Args:
            allowed_stages: Список разрешенных стадий онбординга
            completed_only: Если True, пропускает только завершивших онбординг
        """
        self.allowed_stages = allowed_stages or []
        self.completed_only = completed_only

    async def __call__(
        self,
        handler: Callable,
        event: Union[Message, CallbackQuery],
        data: Dict[str, Any]
    ) -> Any:
        
        user_id = event.from_user.id
                
        onboarding_completed = data.get('onboarding_completed', False)
        onboarding_stage = data.get('onboarding_stage', OnboardingStage.NEW_USER)
        
        # ✅ ИСКЛЮЧЕНИЕ: Админ всегда проходит
        if event.from_user.id in settings.admin_ids_list:
            logger.debug(f"Admin {settings.ADMIN_ID} - allowing all actions")
            return await handler(event, data)
        
        # 🆕 ИСПРАВЛЕНИЕ: РАЗРЕШАЕМ /start для ВСЕХ пользователей
        if hasattr(event, 'text') and event.text and event.text.startswith('/start'):
            logger.debug(f"Allowing /start command for user at stage {onboarding_stage}")
            return await handler(event, data)
        
        # Если нужны только завершившие онбординг
        if self.completed_only and not onboarding_completed:
            logger.debug(f"Skipping handler - onboarding not completed (stage: {onboarding_stage})")
            return
        
        # Если указаны конкретные стадии
        if self.allowed_stages and onboarding_stage not in self.allowed_stages:
            logger.debug(f"Skipping handler - stage {onboarding_stage} not in {self.allowed_stages}")
            return
        
        # Если завершен онбординг, но handler для не завершивших
        if self.allowed_stages and onboarding_completed and OnboardingStage.COMPLETED not in self.allowed_stages:
            logger.debug(f"Skipping handler - onboarding completed but handler for incomplete stages")
            return
        
        return await handler(event, data)