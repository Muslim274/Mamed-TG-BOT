"""
Модуль автоматической рассылки круглых видео
"""
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Optional
import pytz
from aiogram import Bot
from sqlalchemy.ext.asyncio import AsyncSession
import json

from app.config import settings
from app.database.connection import AsyncSessionLocal as async_session_maker
from app.database.crud import UserCRUD, AutomatedMessageCRUD
from app.database.models import OnboardingStage, AutomatedMessageStatus

logger = logging.getLogger(__name__)

# Московская временная зона
MSK = pytz.timezone('Europe/Moscow')


class AutomatedMessagingService:
    """Сервис автоматической рассылки"""
    
    # Маппинг видео ID из конфига
    VIDEO_MAPPING = {
        'K_VIDEO_ID1': settings.K_VIDEO_ID1,
        'K_VIDEO_ID2': settings.K_VIDEO_ID2,
        'K_VIDEO_ID3': settings.K_VIDEO_ID3,
        'K_VIDEO_ID4': settings.K_VIDEO_ID4,
        'K_VIDEO_ID5': settings.K_VIDEO_ID5,
        'K_VIDEO_ID6': settings.K_VIDEO_ID6,
        'K_VIDEO_ID7': settings.K_VIDEO_ID7,
        'K_VIDEO_ID8': settings.K_VIDEO_ID8,
        'K_VIDEO_ID9': settings.K_VIDEO_ID9,
        'K_VIDEO_ID10': settings.K_VIDEO_ID10,
    }
    
    def __init__(self, bot: Bot):
        self.bot = bot
    
    @staticmethod
    def get_next_11am_msk(days_offset: int = 1) -> datetime:
        """Получить следующую дату в 11:00 МСК с учетом смещения в днях"""
        now_msk = datetime.now(MSK)
        target_date = now_msk + timedelta(days=days_offset)
        target_time = target_date.replace(hour=11, minute=0, second=0, microsecond=0)
        
        # Если время уже прошло сегодня, берем следующий день
        if target_time <= now_msk:
            target_time += timedelta(days=1)
        
        # Конвертируем в UTC для БД
        return target_time.astimezone(pytz.UTC).replace(tzinfo=None)
    
    async def schedule_new_user_messages(
        self, 
        session: AsyncSession, 
        user_id: int, 
        telegram_id: int
    ):
        """
        Планирование сообщений для NEW_USER и INTRO_SHOWN
        
        Стадия NEW_USER или INTRO_SHOWN:
        - через 30 мин -> K_VIDEO_ID1
        - через 3 часа после первого -> K_VIDEO_ID2
        - на следующие сутки в 11:00 МСК -> K_VIDEO_ID3
        - через 2 суток после предыдущего в 11:00 МСК -> K_VIDEO_ID4
        """
        now = datetime.now()
        
        # Отменяем все предыдущие запланированные сообщения этого типа
        await AutomatedMessageCRUD.cancel_user_messages(
            session, 
            telegram_id, 
            ['K_VIDEO_ID1', 'K_VIDEO_ID2', 'K_VIDEO_ID3', 'K_VIDEO_ID4']
        )
        
        # K_VIDEO_ID1 - через 30 минут
        await AutomatedMessageCRUD.create_message(
            session=session,
            user_id=user_id,
            telegram_id=telegram_id,
            video_file_id=self.VIDEO_MAPPING['K_VIDEO_ID1'],
            video_type='K_VIDEO_ID1',
            required_stage='["new_user","intro_shown"]',
            scheduled_at=now + timedelta(minutes=30),
            blocked_stages=[OnboardingStage.WAIT_PAYMENT]
        )
        
        # K_VIDEO_ID2 - через 3 часа после первого (3.5 часа от начала)
        await AutomatedMessageCRUD.create_message(
            session=session,
            user_id=user_id,
            telegram_id=telegram_id,
            video_file_id=self.VIDEO_MAPPING['K_VIDEO_ID2'],
            video_type='K_VIDEO_ID2',
            required_stage='["new_user","intro_shown"]',
            scheduled_at=now + timedelta(hours=3, minutes=30),
            blocked_stages=[OnboardingStage.WAIT_PAYMENT]
        )
        
        # K_VIDEO_ID3 - на следующие сутки в 11:00 МСК
        await AutomatedMessageCRUD.create_message(
            session=session,
            user_id=user_id,
            telegram_id=telegram_id,
            video_file_id=self.VIDEO_MAPPING['K_VIDEO_ID3'],
            video_type='K_VIDEO_ID3',
            required_stage='["new_user","intro_shown"]',
            scheduled_at=self.get_next_11am_msk(days_offset=1),
            blocked_stages=[OnboardingStage.WAIT_PAYMENT]
        )
        
        # K_VIDEO_ID4 - через 2 суток после K_VIDEO_ID3 в 11:00 МСК
        await AutomatedMessageCRUD.create_message(
            session=session,
            user_id=user_id,
            telegram_id=telegram_id,
            video_file_id=self.VIDEO_MAPPING['K_VIDEO_ID4'],
            video_type='K_VIDEO_ID4',
            required_stage='["new_user","intro_shown"]',
            scheduled_at=self.get_next_11am_msk(days_offset=3),
            blocked_stages=[OnboardingStage.WAIT_PAYMENT]
        )
        
        logger.info(f"Scheduled NEW_USER messages for user {telegram_id}")
    
    async def schedule_wait_payment_messages(
        self, 
        session: AsyncSession, 
        user_id: int, 
        telegram_id: int
    ):
        """
        Планирование сообщений для WAIT_PAYMENT
        
        После перехода на WAIT_PAYMENT:
        - через 3 часа -> K_VIDEO_ID5
        - на следующие сутки в 11:00 МСК -> K_VIDEO_ID6
        - еще через сутки в 11:00 МСК -> K_VIDEO_ID7
        """
        now = datetime.now()
        
        # Отменяем сообщения для NEW_USER
        await AutomatedMessageCRUD.cancel_user_messages(
            session, 
            telegram_id, 
            ['K_VIDEO_ID1', 'K_VIDEO_ID2', 'K_VIDEO_ID3', 'K_VIDEO_ID4']
        )
        
        # Отменяем предыдущие сообщения WAIT_PAYMENT
        await AutomatedMessageCRUD.cancel_user_messages(
            session, 
            telegram_id, 
            ['K_VIDEO_ID5', 'K_VIDEO_ID6', 'K_VIDEO_ID7']
        )
        
        blocked = [OnboardingStage.PAYMENT_OK, OnboardingStage.WANT_JOIN]
        
        # K_VIDEO_ID5 - через 3 часа
        await AutomatedMessageCRUD.create_message(
            session=session,
            user_id=user_id,
            telegram_id=telegram_id,
            video_file_id=self.VIDEO_MAPPING['K_VIDEO_ID5'],
            video_type='K_VIDEO_ID5',
            required_stage='["wait_payment"]',
            scheduled_at=now + timedelta(hours=3),
            blocked_stages=blocked
        )
        
        # K_VIDEO_ID6 - на следующие сутки в 11:00 МСК
        await AutomatedMessageCRUD.create_message(
            session=session,
            user_id=user_id,
            telegram_id=telegram_id,
            video_file_id=self.VIDEO_MAPPING['K_VIDEO_ID6'],
            video_type='K_VIDEO_ID6',
            required_stage='["wait_payment"]',
            scheduled_at=self.get_next_11am_msk(days_offset=1),
            blocked_stages=blocked
        )
        
        # K_VIDEO_ID7 - еще через сутки в 11:00 МСК
        await AutomatedMessageCRUD.create_message(
            session=session,
            user_id=user_id,
            telegram_id=telegram_id,
            video_file_id=self.VIDEO_MAPPING['K_VIDEO_ID7'],
            video_type='K_VIDEO_ID7',
            required_stage='["wait_payment"]',
            scheduled_at=self.get_next_11am_msk(days_offset=2),
            blocked_stages=blocked
        )
        
        logger.info(f"Scheduled WAIT_PAYMENT messages for user {telegram_id}")
    
    async def schedule_want_join_messages(
        self, 
        session: AsyncSession, 
        user_id: int, 
        telegram_id: int
    ):
        """
        Планирование сообщений для WANT_JOIN
        
        После перехода на WANT_JOIN:
        - через 3 суток в 11:00 МСК -> K_VIDEO_ID8
        - еще через 3 суток в 11:00 МСК -> K_VIDEO_ID9
        - еще через 3 суток в 11:00 МСК -> K_VIDEO_ID10
        """
        # Отменяем все предыдущие сообщения
        await AutomatedMessageCRUD.cancel_user_messages(
            session, 
            telegram_id, 
            ['K_VIDEO_ID1', 'K_VIDEO_ID2', 'K_VIDEO_ID3', 'K_VIDEO_ID4',
             'K_VIDEO_ID5', 'K_VIDEO_ID6', 'K_VIDEO_ID7']
        )
        
        # Отменяем предыдущие сообщения WANT_JOIN
        await AutomatedMessageCRUD.cancel_user_messages(
            session, 
            telegram_id, 
            ['K_VIDEO_ID8', 'K_VIDEO_ID9', 'K_VIDEO_ID10']
        )
        
        blocked = [OnboardingStage.COMPLETED]
        
        # K_VIDEO_ID8 - через 3 суток в 11:00 МСК
        await AutomatedMessageCRUD.create_message(
            session=session,
            user_id=user_id,
            telegram_id=telegram_id,
            video_file_id=self.VIDEO_MAPPING['K_VIDEO_ID8'],
            video_type='K_VIDEO_ID8',
            required_stage='["want_join"]',
            scheduled_at=self.get_next_11am_msk(days_offset=3),
            blocked_stages=blocked
        )
        
        # K_VIDEO_ID9 - через 6 суток в 11:00 МСК
        await AutomatedMessageCRUD.create_message(
            session=session,
            user_id=user_id,
            telegram_id=telegram_id,
            video_file_id=self.VIDEO_MAPPING['K_VIDEO_ID9'],
            video_type='K_VIDEO_ID9',
            required_stage='["want_join"]',
            scheduled_at=self.get_next_11am_msk(days_offset=6),
            blocked_stages=blocked
        )
        
        # K_VIDEO_ID10 - через 9 суток в 11:00 МСК
        await AutomatedMessageCRUD.create_message(
            session=session,
            user_id=user_id,
            telegram_id=telegram_id,
            video_file_id=self.VIDEO_MAPPING['K_VIDEO_ID10'],
            video_type='K_VIDEO_ID10',
            required_stage='["want_join"]',
            scheduled_at=self.get_next_11am_msk(days_offset=9),
            blocked_stages=blocked
        )
        
        logger.info(f"Scheduled WANT_JOIN messages for user {telegram_id}")
    
    async def handle_stage_change(
        self, 
        session: AsyncSession, 
        user_id: int, 
        telegram_id: int, 
        new_stage: str
    ):
        """
        Обработка изменения стадии пользователя
        Планирует новые сообщения в зависимости от стадии
        """
        logger.info(f"Handling stage change for user {telegram_id}: {new_stage}")
        
        if new_stage in [OnboardingStage.NEW_USER, OnboardingStage.INTRO_SHOWN]:
            await self.schedule_new_user_messages(session, user_id, telegram_id)
        
        elif new_stage == OnboardingStage.WAIT_PAYMENT:
            await self.schedule_wait_payment_messages(session, user_id, telegram_id)
        
        elif new_stage == OnboardingStage.WANT_JOIN:
            await self.schedule_want_join_messages(session, user_id, telegram_id)
        
        elif new_stage in [OnboardingStage.PAYMENT_OK, OnboardingStage.COMPLETED]:
            # Отменяем все запланированные сообщения
            await AutomatedMessageCRUD.cancel_user_messages(session, telegram_id)
            logger.info(f"Cancelled all messages for user {telegram_id} (stage: {new_stage})")
    
    async def send_video_note(self, telegram_id: int, video_file_id: str) -> bool:
        """Отправка круглого видео пользователю"""
        try:
            await self.bot.send_video_note(
                chat_id=telegram_id,
                video_note=video_file_id
            )
            logger.info(f"Successfully sent video note to {telegram_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to send video note to {telegram_id}: {e}")
            return False
    
    async def process_pending_messages(self):
        """
        Обработка всех запланированных сообщений
        Эта функция должна вызываться периодически
        """
        async with async_session_maker() as session:
            try:
                # Получаем все сообщения, время которых наступило
                messages = await AutomatedMessageCRUD.get_pending_messages(session)
                
                logger.info(f"Processing {len(messages)} pending messages")
                
                for message in messages:
                    try:
                        # Получаем пользователя
                        user = await UserCRUD.get_user_by_telegram_id(session, message.telegram_id)
                        
                        if not user:
                            await AutomatedMessageCRUD.update_message_status(
                                session, message.id, 
                                AutomatedMessageStatus.FAILED,
                                "User not found"
                            )
                            continue
                        
                        # Проверяем, что пользователь все еще на нужной стадии
                        allowed_stages = json.loads(message.required_stage) if message.required_stage.startswith('[') else [message.required_stage]
                        if user.onboarding_stage not in allowed_stages:
                            await AutomatedMessageCRUD.update_message_status(
                                session, message.id, 
                                AutomatedMessageStatus.CANCELLED,
                                f"User stage changed to {user.onboarding_stage}"
                            )
                            continue
                        
                        # Проверяем, что пользователь не на блокирующей стадии
                        if message.blocked_stages:
                            
                            blocked = json.loads(message.blocked_stages)
                            if user.onboarding_stage in blocked:
                                await AutomatedMessageCRUD.update_message_status(
                                    session, message.id, 
                                    AutomatedMessageStatus.CANCELLED,
                                    f"User on blocked stage {user.onboarding_stage}"
                                )
                                continue
                        
                        # Отправляем сообщение
                        success = await self.send_video_note(
                            message.telegram_id, 
                            message.video_file_id
                        )
                        
                        if success:
                            await AutomatedMessageCRUD.update_message_status(
                                session, message.id, 
                                AutomatedMessageStatus.SENT
                            )
                        else:
                            await AutomatedMessageCRUD.update_message_status(
                                session, message.id, 
                                AutomatedMessageStatus.FAILED,
                                "Failed to send message"
                            )
                    
                    except Exception as e:
                        logger.error(f"Error processing message {message.id}: {e}")
                        await AutomatedMessageCRUD.update_message_status(
                            session, message.id, 
                            AutomatedMessageStatus.FAILED,
                            str(e)
                        )
            
            except Exception as e:
                logger.error(f"Error in process_pending_messages: {e}")


async def start_automated_messaging_worker(bot: Bot):
    """
    Запуск фонового worker'а для обработки автоматических сообщений
    Проверяет каждые 60 секунд
    """
    service = AutomatedMessagingService(bot)
    logger.info("Starting automated messaging worker")
    
    while True:
        try:
            await service.process_pending_messages()
        except Exception as e:
            logger.error(f"Error in automated messaging worker: {e}")
        
        # Проверка каждые 60 секунд
        await asyncio.sleep(60)