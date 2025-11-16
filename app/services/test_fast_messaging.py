"""
ТЕСТОВЫЙ модуль автоматической рассылки с ускоренным режимом
Только для telegram_id: 8181794729
Все сообщения отправляются каждые 3 минуты
"""
import asyncio
import logging
from datetime import datetime, timedelta
import sys
from pathlib import Path

# Добавляем корень проекта в sys.path
sys.path.append(str(Path(__file__).parent.parent.parent))

from aiogram import Bot
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database.connection import AsyncSessionLocal
from app.database.crud import UserCRUD, AutomatedMessageCRUD
from app.database.models import OnboardingStage

logger = logging.getLogger(__name__)

# ТЕСТОВЫЙ ID ПОЛЬЗОВАТЕЛЯ
TEST_USER_ID = 8181794729

# Интервал между сообщениями в МИНУТАХ
TEST_INTERVAL_MINUTES = 3


class TestAutomatedMessagingService:
    """ТЕСТОВЫЙ сервис с ускоренной отправкой"""
    
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
    
    async def schedule_new_user_messages(
        self, 
        session: AsyncSession, 
        user_id: int, 
        telegram_id: int
    ):
        """
        ТЕСТ: NEW_USER сообщения каждые 3 минуты
        """
        if telegram_id != TEST_USER_ID:
            return
        
        now = datetime.now()
        
        # Отменяем старые
        await AutomatedMessageCRUD.cancel_user_messages(
            session, telegram_id, 
            ['K_VIDEO_ID1', 'K_VIDEO_ID2', 'K_VIDEO_ID3', 'K_VIDEO_ID4']
        )
        
        # K_VIDEO_ID1 - через 3 минуты
        await AutomatedMessageCRUD.create_message(
            session=session, user_id=user_id, telegram_id=telegram_id,
            video_file_id=self.VIDEO_MAPPING['K_VIDEO_ID1'],
            video_type='K_VIDEO_ID1',
            required_stage=OnboardingStage.NEW_USER,
            scheduled_at=now + timedelta(minutes=TEST_INTERVAL_MINUTES * 1),
            blocked_stages=[OnboardingStage.WAIT_PAYMENT]
        )
        
        # K_VIDEO_ID2 - через 6 минут
        await AutomatedMessageCRUD.create_message(
            session=session, user_id=user_id, telegram_id=telegram_id,
            video_file_id=self.VIDEO_MAPPING['K_VIDEO_ID2'],
            video_type='K_VIDEO_ID2',
            required_stage=OnboardingStage.NEW_USER,
            scheduled_at=now + timedelta(minutes=TEST_INTERVAL_MINUTES * 2),
            blocked_stages=[OnboardingStage.WAIT_PAYMENT]
        )
        
        # K_VIDEO_ID3 - через 9 минут
        await AutomatedMessageCRUD.create_message(
            session=session, user_id=user_id, telegram_id=telegram_id,
            video_file_id=self.VIDEO_MAPPING['K_VIDEO_ID3'],
            video_type='K_VIDEO_ID3',
            required_stage=OnboardingStage.NEW_USER,
            scheduled_at=now + timedelta(minutes=TEST_INTERVAL_MINUTES * 3),
            blocked_stages=[OnboardingStage.WAIT_PAYMENT]
        )
        
        # K_VIDEO_ID4 - через 12 минут
        await AutomatedMessageCRUD.create_message(
            session=session, user_id=user_id, telegram_id=telegram_id,
            video_file_id=self.VIDEO_MAPPING['K_VIDEO_ID4'],
            video_type='K_VIDEO_ID4',
            required_stage=OnboardingStage.NEW_USER,
            scheduled_at=now + timedelta(minutes=TEST_INTERVAL_MINUTES * 4),
            blocked_stages=[OnboardingStage.WAIT_PAYMENT]
        )
        
        logger.info(f"[TEST] Scheduled NEW_USER messages for {telegram_id} (every 3 min)")
    
    async def schedule_wait_payment_messages(
        self, 
        session: AsyncSession, 
        user_id: int, 
        telegram_id: int
    ):
        """
        ТЕСТ: WAIT_PAYMENT сообщения каждые 3 минуты
        """
        if telegram_id != TEST_USER_ID:
            return
        
        now = datetime.now()
        
        # Отменяем старые
        await AutomatedMessageCRUD.cancel_user_messages(
            session, telegram_id, 
            ['K_VIDEO_ID1', 'K_VIDEO_ID2', 'K_VIDEO_ID3', 'K_VIDEO_ID4',
             'K_VIDEO_ID5', 'K_VIDEO_ID6', 'K_VIDEO_ID7']
        )
        
        blocked = [OnboardingStage.PAYMENT_OK, OnboardingStage.WANT_JOIN]
        
        # K_VIDEO_ID5 - через 3 минуты
        await AutomatedMessageCRUD.create_message(
            session=session, user_id=user_id, telegram_id=telegram_id,
            video_file_id=self.VIDEO_MAPPING['K_VIDEO_ID5'],
            video_type='K_VIDEO_ID5',
            required_stage=OnboardingStage.WAIT_PAYMENT,
            scheduled_at=now + timedelta(minutes=TEST_INTERVAL_MINUTES * 1),
            blocked_stages=blocked
        )
        
        # K_VIDEO_ID6 - через 6 минут
        await AutomatedMessageCRUD.create_message(
            session=session, user_id=user_id, telegram_id=telegram_id,
            video_file_id=self.VIDEO_MAPPING['K_VIDEO_ID6'],
            video_type='K_VIDEO_ID6',
            required_stage=OnboardingStage.WAIT_PAYMENT,
            scheduled_at=now + timedelta(minutes=TEST_INTERVAL_MINUTES * 2),
            blocked_stages=blocked
        )
        
        # K_VIDEO_ID7 - через 9 минут
        await AutomatedMessageCRUD.create_message(
            session=session, user_id=user_id, telegram_id=telegram_id,
            video_file_id=self.VIDEO_MAPPING['K_VIDEO_ID7'],
            video_type='K_VIDEO_ID7',
            required_stage=OnboardingStage.WAIT_PAYMENT,
            scheduled_at=now + timedelta(minutes=TEST_INTERVAL_MINUTES * 3),
            blocked_stages=blocked
        )
        
        logger.info(f"[TEST] Scheduled WAIT_PAYMENT messages for {telegram_id} (every 3 min)")
    
    async def schedule_want_join_messages(
        self, 
        session: AsyncSession, 
        user_id: int, 
        telegram_id: int
    ):
        """
        ТЕСТ: WANT_JOIN сообщения каждые 3 минуты
        """
        if telegram_id != TEST_USER_ID:
            return
        
        now = datetime.now()
        
        # Отменяем все старые
        await AutomatedMessageCRUD.cancel_user_messages(session, telegram_id)
        
        blocked = [OnboardingStage.COMPLETED]
        
        # K_VIDEO_ID8 - через 3 минуты
        await AutomatedMessageCRUD.create_message(
            session=session, user_id=user_id, telegram_id=telegram_id,
            video_file_id=self.VIDEO_MAPPING['K_VIDEO_ID8'],
            video_type='K_VIDEO_ID8',
            required_stage=OnboardingStage.WANT_JOIN,
            scheduled_at=now + timedelta(minutes=TEST_INTERVAL_MINUTES * 1),
            blocked_stages=blocked
        )
        
        # K_VIDEO_ID9 - через 6 минут
        await AutomatedMessageCRUD.create_message(
            session=session, user_id=user_id, telegram_id=telegram_id,
            video_file_id=self.VIDEO_MAPPING['K_VIDEO_ID9'],
            video_type='K_VIDEO_ID9',
            required_stage=OnboardingStage.WANT_JOIN,
            scheduled_at=now + timedelta(minutes=TEST_INTERVAL_MINUTES * 2),
            blocked_stages=blocked
        )
        
        # K_VIDEO_ID10 - через 9 минут
        await AutomatedMessageCRUD.create_message(
            session=session, user_id=user_id, telegram_id=telegram_id,
            video_file_id=self.VIDEO_MAPPING['K_VIDEO_ID10'],
            video_type='K_VIDEO_ID10',
            required_stage=OnboardingStage.WANT_JOIN,
            scheduled_at=now + timedelta(minutes=TEST_INTERVAL_MINUTES * 3),
            blocked_stages=blocked
        )
        
        logger.info(f"[TEST] Scheduled WANT_JOIN messages for {telegram_id} (every 3 min)")
    
    async def handle_stage_change(
        self, 
        session: AsyncSession, 
        user_id: int, 
        telegram_id: int, 
        new_stage: str
    ):
        """Обработка смены стадии для тестового пользователя"""
        if telegram_id != TEST_USER_ID:
            return
        
        logger.info(f"[TEST] Stage change for {telegram_id}: {new_stage}")
        
        if new_stage in [OnboardingStage.NEW_USER, OnboardingStage.INTRO_SHOWN]:
            await self.schedule_new_user_messages(session, user_id, telegram_id)
        
        elif new_stage == OnboardingStage.WAIT_PAYMENT:
            await self.schedule_wait_payment_messages(session, user_id, telegram_id)
        
        elif new_stage == OnboardingStage.WANT_JOIN:
            await self.schedule_want_join_messages(session, user_id, telegram_id)
        
        elif new_stage in [OnboardingStage.PAYMENT_OK, OnboardingStage.COMPLETED]:
            await AutomatedMessageCRUD.cancel_user_messages(session, telegram_id)
            logger.info(f"[TEST] Cancelled all messages for {telegram_id}")


# ============================================
# ИСПОЛЬЗОВАНИЕ В КОДЕ
# ============================================

async def test_stage_update_with_fast_messaging(
    session: AsyncSession,
    telegram_id: int,
    new_stage: str,
    bot: Bot
):
    """
    Функция для обновления стадии ТЕСТОВОГО пользователя
    Использовать ВМЕСТО StageUpdateHelper для telegram_id = 8181794729
    """
    from sqlalchemy import update
    from app.database.models import User
    
    if telegram_id != TEST_USER_ID:
        # Для остальных пользователей используем обычную логику
        from app.helpers.stage_helper import StageUpdateHelper
        return await StageUpdateHelper.update_user_stage(
            session, telegram_id, new_stage, bot
        )
    
    # Для тестового пользователя
    user = await UserCRUD.get_user_by_telegram_id(session, telegram_id)
    if not user:
        return False
    
    # Обновляем стадию
    result = await session.execute(
        update(User)
        .where(User.telegram_id == telegram_id)
        .values(onboarding_stage=new_stage)
    )
    await session.commit()
    
    if result.rowcount > 0:
        # Планируем УСКОРЕННЫЕ сообщения
        test_service = TestAutomatedMessagingService(bot)
        await test_service.handle_stage_change(
            session, user.id, telegram_id, new_stage
        )
        return True
    
    return False


# ============================================
# РУЧНОЙ ЗАПУСК ТЕСТА
# ============================================

async def run_manual_test():
    """
    Ручной запуск теста для пользователя 8181794729
    """
    print("=" * 50)
    print("ТЕСТОВЫЙ РЕЖИМ - Ускоренная рассылка")
    print(f"Пользователь: {TEST_USER_ID}")
    print(f"Интервал: {TEST_INTERVAL_MINUTES} минуты")
    print("=" * 50)
    
    bot = Bot(token=settings.BOT_TOKEN)
    
    async with AsyncSessionLocal() as session:
        user = await UserCRUD.get_user_by_telegram_id(session, TEST_USER_ID)
        
        if not user:
            print(f"❌ Пользователь {TEST_USER_ID} не найден в БД")
            await bot.session.close()
            return
        
        print(f"\n✓ Пользователь найден: {user.full_name}")
        print(f"✓ Текущая стадия: {user.onboarding_stage}")
        
        print("\nВыберите стадию для теста:")
        print("1. NEW_USER (4 видео по 3 мин)")
        print("2. WAIT_PAYMENT (3 видео по 3 мин)")
        print("3. WANT_JOIN (3 видео по 3 мин)")
        print("0. Выход")
        
        choice = input("\nВведите номер: ")
        
        stages = {
            "1": OnboardingStage.NEW_USER,
            "2": OnboardingStage.WAIT_PAYMENT,
            "3": OnboardingStage.WANT_JOIN
        }
        
        if choice in stages:
            new_stage = stages[choice]
            
            success = await test_stage_update_with_fast_messaging(
                session, TEST_USER_ID, new_stage, bot
            )
            
            if success:
                print(f"\n✅ Стадия установлена: {new_stage}")
                print(f"📹 Сообщения запланированы каждые {TEST_INTERVAL_MINUTES} минуты")
                print("\n⏰ График отправки:")
                
                messages = await AutomatedMessageCRUD.get_user_scheduled_messages(
                    session, TEST_USER_ID
                )
                
                for i, msg in enumerate(messages, 1):
                    from datetime import timezone
                    time_diff = (msg.scheduled_at - datetime.now(timezone.utc)).total_seconds() / 60
                    print(f"  {i}. {msg.video_type}: через {int(time_diff)} мин")
                
                print("\n✓ Ждите отправки. Worker проверяет каждые 60 секунд.")
            else:
                print("❌ Ошибка установки стадии")
        elif choice == "0":
            print("Выход...")
        else:
            print("Неверный выбор")
    
    await bot.session.close()


if __name__ == "__main__":
    asyncio.run(run_manual_test())
