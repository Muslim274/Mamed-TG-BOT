"""
Вспомогательный модуль для обновления стадий пользователя
с автоматическим планированием рассылок
"""
import logging
from datetime import datetime
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession
from aiogram import Bot

from app.database.models import User, OnboardingStage
from app.database.crud import UserCRUD

logger = logging.getLogger(__name__)


class StageUpdateHelper:
    """Хелпер для обновления стадий с отслеживанием времени"""
    
    # Маппинг стадий на поля времени
    STAGE_TIME_FIELDS = {
        OnboardingStage.NEW_USER: 'stage_new_user_at',
        OnboardingStage.INTRO_SHOWN: 'stage_intro_shown_at',
        OnboardingStage.WAIT_PAYMENT: 'stage_wait_payment_at',
        OnboardingStage.PAYMENT_OK: 'stage_payment_ok_at',
        OnboardingStage.WANT_JOIN: 'stage_want_join_at',
        OnboardingStage.COMPLETED: 'stage_completed_at',
    }
    
    @staticmethod
    async def update_user_stage(
        session: AsyncSession,
        telegram_id: int,
        new_stage: str,
        bot: Bot = None
    ) -> bool:
        """
        Обновление стадии пользователя с отслеживанием времени
        и планированием автоматических сообщений
        
        Args:
            session: Сессия БД
            telegram_id: ID пользователя в Telegram
            new_stage: Новая стадия
            bot: Экземпляр бота (для планирования сообщений)
        
        Returns:
            True если обновление успешно
        """
        try:
            # Получаем пользователя
            user = await UserCRUD.get_user_by_telegram_id(session, telegram_id)
            if not user:
                logger.error(f"User {telegram_id} not found")
                return False
            
            old_stage = user.onboarding_stage
            
            # Обновляем стадию и время перехода
            update_values = {'onboarding_stage': new_stage}
            
            # Добавляем время перехода если есть маппинг для этой стадии
            if new_stage in StageUpdateHelper.STAGE_TIME_FIELDS:
                time_field = StageUpdateHelper.STAGE_TIME_FIELDS[new_stage]
                update_values[time_field] = datetime.now()
            
            result = await session.execute(
                update(User)
                .where(User.telegram_id == telegram_id)
                .values(**update_values)
            )
            await session.commit()
            
            if result.rowcount > 0:
                logger.info(f"Updated user {telegram_id} stage: {old_stage} -> {new_stage}")
                
                # Планируем автоматические сообщения если передан bot
                if bot:
                    try:
                        from app.services.automated_messaging import AutomatedMessagingService
                        
                        messaging_service = AutomatedMessagingService(bot)
                        await messaging_service.handle_stage_change(
                            session, user.id, telegram_id, new_stage
                        )
                    except Exception as e:
                        logger.error(f"Error scheduling automated messages for {telegram_id}: {e}")
                
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error updating stage for user {telegram_id}: {e}")
            return False
    
    @staticmethod
    async def get_stage_transition_time(
        session: AsyncSession,
        telegram_id: int,
        stage: str
    ) -> datetime | None:
        """Получить время перехода на указанную стадию"""
        try:
            user = await UserCRUD.get_user_by_telegram_id(session, telegram_id)
            if not user:
                return None
            
            if stage in StageUpdateHelper.STAGE_TIME_FIELDS:
                time_field = StageUpdateHelper.STAGE_TIME_FIELDS[stage]
                return getattr(user, time_field, None)
            
            return None
            
        except Exception as e:
            logger.error(f"Error getting stage transition time for {telegram_id}: {e}")
            return None
