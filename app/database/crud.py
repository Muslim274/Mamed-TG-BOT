"""
Исправленные CRUD операции для правильного подсчета продаж
"""
import logging
from sqlalchemy import select, update, func
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timedelta
from typing import Optional, List, Tuple

from app.database.models import (
    User, Click, Sale, Withdrawal, CourseVideo, 
    UserCourseProgress, OnboardingStage, Payment, ReferralHistory,
    AutomatedMessage, AutomatedMessageStatus  
)

logger = logging.getLogger(__name__)


class ClickCRUD:
    @staticmethod
    async def create_click(session: AsyncSession, ref_code: str, 
                          ip_address: str, user_agent: str, source: str = None,
                          user_telegram_id: int = None) -> Click:
        """Создание записи о клике с поддержкой user_telegram_id"""
        click = Click(
            ref_code=ref_code,
            ip_address=ip_address,
            user_agent=user_agent,
            source=source,
            user_telegram_id=user_telegram_id
        )
        session.add(click)
        await session.commit()
        await session.refresh(click)
        return click
    
    @staticmethod
    async def get_last_click_by_user(session: AsyncSession, user_telegram_id: int) -> Optional[Click]:
        """Получение последнего клика пользователя"""
        try:
            result = await session.execute(
                select(Click)
                .where(Click.user_telegram_id == user_telegram_id)
                .order_by(Click.created_at.desc())
                .limit(1)
            )
            return result.scalar_one_or_none()
        except Exception as e:
            logger.error(f"Error getting last click for user {user_telegram_id}: {e}")
            return None

    @staticmethod
    async def count_clicks_by_ref_code(session: AsyncSession, ref_code: str) -> int:
        """Подсчет кликов по реферальному коду"""
        try:
            result = await session.execute(
                select(func.count(Click.id)).where(Click.ref_code == ref_code)
            )
            count = result.scalar()
            return count or 0
        except Exception as e:
            logger.error(f"Error counting clicks for ref_code {ref_code}: {e}")
            return 0


class ReferralHistoryCRUD:
    @staticmethod
    async def log_action(session: AsyncSession, user_telegram_id: int, ref_code: str,
                        action_type: str, ip_address: str = None, user_agent: str = None,
                        amount: float = None, commission_amount: float = None) -> ReferralHistory:
        """Логирование действий для аналитики"""
        history = ReferralHistory(
            user_telegram_id=user_telegram_id,
            ref_code=ref_code,
            action_type=action_type,
            ip_address=ip_address,
            user_agent=user_agent,
            amount=amount,
            commission_amount=commission_amount
        )
        session.add(history)
        await session.commit()
        await session.refresh(history)
        return history
    
    @staticmethod
    async def get_user_referral_history(session: AsyncSession, user_telegram_id: int) -> List[ReferralHistory]:
        """Получение истории реферальных действий пользователя"""
        try:
            result = await session.execute(
                select(ReferralHistory)
                .where(ReferralHistory.user_telegram_id == user_telegram_id)
                .order_by(ReferralHistory.created_at.desc())
            )
            return result.scalars().all()
        except Exception as e:
            logger.error(f"Error getting referral history for user {user_telegram_id}: {e}")
            return []


class UserCRUD:
    
    @staticmethod
    async def get_last_referrer(session: AsyncSession, user_telegram_id: int) -> Optional[str]:
        """
        Получение последнего реферального кода для пользователя
        Сначала ищет в кликах, если не найдено - возвращает referred_by
        """
        try:
            # Ищем последний клик пользователя
            last_click = await ClickCRUD.get_last_click_by_user(session, user_telegram_id)
            
            if last_click:
                # ИСПРАВЛЕНИЕ: Убираем проверку на 30 дней - всегда используем последний клик
                logger.info(f"Using last click ref_code: {last_click.ref_code} for user {user_telegram_id}")
                return last_click.ref_code
            
            # Fallback на original referrer
            user = await UserCRUD.get_user_by_telegram_id(session, user_telegram_id)
            if user and user.referred_by:
                logger.info(f"Using original referred_by: {user.referred_by} for user {user_telegram_id}")
                return user.referred_by
            
            logger.info(f"No referrer found for user {user_telegram_id}")
            return None
            
        except Exception as e:
            logger.error(f"Error getting last referrer for user {user_telegram_id}: {e}")
            return None
    
    @staticmethod
    async def update_user_gender(session: AsyncSession, telegram_id: int, gender: str) -> bool:
        """Обновление пола пользователя"""
        result = await session.execute(
            update(User)
            .where(User.telegram_id == telegram_id)
            .values(gender=gender)
        )
        await session.commit()
        return result.rowcount > 0
    
    @staticmethod
    async def create_user(session: AsyncSession, telegram_id: int, username: str, 
                         full_name: str, ref_code: str, referred_by: str = None,
                         onboarding_stage: str = OnboardingStage.NEW_USER) -> User:
        """Создание нового пользователя"""
        user = User(
            telegram_id=telegram_id,
            username=username,
            full_name=full_name,
            ref_code=ref_code,
            referred_by=referred_by,
            onboarding_stage=onboarding_stage
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)
        return user
    
    @staticmethod
    async def get_user_by_telegram_id(session: AsyncSession, telegram_id: int) -> Optional[User]:
        """Получение пользователя по telegram_id"""
        result = await session.execute(
            select(User).where(User.telegram_id == telegram_id)
        )
        return result.scalar_one_or_none()
    
    @staticmethod
    async def get_user_by_ref_code(session: AsyncSession, ref_code: str) -> Optional[User]:
        """Получение пользователя по реферальному коду"""
        result = await session.execute(
            select(User).where(User.ref_code == ref_code)
        )
        return result.scalar_one_or_none()
    
    # Методы для онбординга
    
    @staticmethod
    async def update_onboarding_stage(session: AsyncSession, telegram_id: int, 
                                    stage: str) -> bool:
                                        
        # Логируем для пользователя 8181794729
        if telegram_id == 8181794729:
            logger.info(f"🎯 USER {telegram_id} STAGE CHANGE → {stage}")
        
        """Обновление стадии онбординга"""
        result = await session.execute(
            update(User)
            .where(User.telegram_id == telegram_id)
            .values(onboarding_stage=stage)
        )
        await session.commit()
        return result.rowcount > 0
    
    @staticmethod
    async def complete_payment(session: AsyncSession, telegram_id: int) -> bool:
        """Отметка об успешной оплате"""
        result = await session.execute(
            update(User)
            .where(User.telegram_id == telegram_id)
            .values(
                payment_completed=True,
                onboarding_stage=OnboardingStage.PAYMENT_OK
            )
        )
        await session.commit()
        return result.rowcount > 0
    
    @staticmethod
    async def update_course_step(session: AsyncSession, telegram_id: int, 
                               step: int) -> bool:
        """Обновление текущего шага курса"""
        # Определяем стадию на основе шага
        stage = f"course_{step}" if step <= 10 else OnboardingStage.COURSE_COMPLETED
        
        result = await session.execute(
            update(User)
            .where(User.telegram_id == telegram_id)
            .values(
                current_course_step=step,
                onboarding_stage=stage
            )
        )
        await session.commit()
        return result.rowcount > 0
        
    @staticmethod
    async def get_paid_users(session: AsyncSession) -> List[User]:
        """Получение всех пользователей, которые оплатили курс"""
        try:
            result = await session.execute(
                select(User).where(
                    User.status == "active",
                    User.payment_completed == True
                )
            )
            users = result.scalars().all()
            return list(users)
        except Exception as e:
            logger.error(f"Error getting paid users: {e}")
            return []
            
    @staticmethod
    async def get_unpaid_users(session: AsyncSession) -> List[User]:
        """Получение всех пользователей, которые не оплатили курс (NEW_USER, INTRO_SHOWN)"""
        try:
            result = await session.execute(
                select(User).where(
                    User.status == "active",
                    User.onboarding_stage.in_([OnboardingStage.NEW_USER, OnboardingStage.INTRO_SHOWN])
                )
            )
            users = result.scalars().all()
            return list(users)
        except Exception as e:
            logger.error(f"Error getting unpaid users: {e}")
            return []
    
    @staticmethod
    async def get_learning_users(session: AsyncSession) -> List[User]:
        """Получение всех пользователей, которые проходят обучение (WANT_JOIN)"""
        try:
            result = await session.execute(
                select(User).where(
                    User.status == "active",
                    User.onboarding_stage == OnboardingStage.WANT_JOIN
                )
            )
            users = result.scalars().all()
            return list(users)
        except Exception as e:
            logger.error(f"Error getting learning users: {e}")
            return []
            
            
            
    @staticmethod
    async def get_payment_page_users(session: AsyncSession) -> List[User]:
        """Получение всех пользователей на стадии ожидания оплаты (WAIT_PAYMENT)"""
        try:
            result = await session.execute(
                select(User).where(
                    User.status == "active",
                    User.onboarding_stage == OnboardingStage.WAIT_PAYMENT
                )
            )
            users = result.scalars().all()
            return list(users)
        except Exception as e:
            logger.error(f"Error getting payment page users: {e}")
            return []
        
    @staticmethod
    async def complete_course(session: AsyncSession, telegram_id: int) -> bool:
        """Завершение курса"""
        result = await session.execute(
            update(User)
            .where(User.telegram_id == telegram_id)
            .values(
                onboarding_stage=OnboardingStage.COURSE_COMPLETED,
                course_completed_at=datetime.now()
            )
        )
        await session.commit()
        return result.rowcount > 0
    
    @staticmethod
    async def show_partner_offer(session: AsyncSession, telegram_id: int) -> bool:
        """Отметка о показе предложения партнерства"""
        result = await session.execute(
            update(User)
            .where(User.telegram_id == telegram_id)
            .values(
                onboarding_stage=OnboardingStage.PARTNER_OFFER,
                partner_offer_shown_at=datetime.now()
            )
        )
        await session.commit()
        return result.rowcount > 0
    
    @staticmethod
    async def complete_onboarding(session: AsyncSession, telegram_id: int) -> bool:
        """Завершение онбординга"""
        result = await session.execute(
            update(User)
            .where(User.telegram_id == telegram_id)
            .values(
                onboarding_stage=OnboardingStage.COMPLETED,
                onboarding_completed_at=datetime.now()
            )
        )
        await session.commit()
        return result.rowcount > 0

    # Методы для рассылки
    
    @staticmethod
    async def get_all_active_users(session: AsyncSession) -> List[User]:
        """Получение всех активных пользователей для рассылки"""
        try:
            result = await session.execute(
                select(User).where(User.status == "active")
            )
            users = result.scalars().all()
            return list(users)
        except Exception as e:
            logger.error(f"Error getting all active users: {e}")
            return []

    @staticmethod
    async def count_active_users(session: AsyncSession) -> int:
        """Подсчет количества активных пользователей"""
        try:
            result = await session.execute(
                select(func.count(User.id)).where(User.status == "active")
            )
            count = result.scalar()
            return count or 0
        except Exception as e:
            logger.error(f"Error counting active users: {e}")
            return 0

    @staticmethod
    async def validate_telegram_ids(session: AsyncSession, telegram_ids: List[int]) -> Tuple[List[dict], List[int]]:
        """
        Валидация списка Telegram ID - проверка существования в БД
        
        Args:
            session: Сессия БД
            telegram_ids: Список Telegram ID для проверки
        
        Returns:
            Tuple[List[dict], List[int]]: (найденные пользователи, не найденные ID)
        """
        try:
            # Получаем пользователей по списку ID
            result = await session.execute(
                select(User).where(
                    User.telegram_id.in_(telegram_ids),
                    User.status == "active"
                )
            )
            found_users = result.scalars().all()
            
            # Преобразуем в список словарей с нужными полями
            found_user_data = []
            found_ids = set()
            
            for user in found_users:
                found_user_data.append({
                    'telegram_id': user.telegram_id,
                    'username': user.username,
                    'full_name': user.full_name,
                    'onboarding_stage': user.onboarding_stage
                })
                found_ids.add(user.telegram_id)
            
            # Определяем не найденные ID
            not_found_ids = [id for id in telegram_ids if id not in found_ids]
            
            logger.info(f"Validation result: {len(found_user_data)} found, {len(not_found_ids)} not found")
            
            return found_user_data, not_found_ids
            
        except Exception as e:
            logger.error(f"Error validating telegram IDs: {e}")
            return [], telegram_ids

    @staticmethod
    async def get_users_by_telegram_ids(session: AsyncSession, telegram_ids: List[int]) -> List[User]:
        """
        Получение пользователей по списку Telegram ID
        
        Args:
            session: Сессия БД
            telegram_ids: Список Telegram ID
        
        Returns:
            List[User]: Список найденных пользователей
        """
        try:
            result = await session.execute(
                select(User).where(
                    User.telegram_id.in_(telegram_ids),
                    User.status == "active"
                )
            )
            users = result.scalars().all()
            return list(users)
        except Exception as e:
            logger.error(f"Error getting users by telegram IDs: {e}")
            return []

    @staticmethod
    async def get_broadcast_statistics(session: AsyncSession) -> dict:
        """Получение статистики для рассылки"""
        try:
            # Общее количество активных пользователей
            total_active = await UserCRUD.count_active_users(session)
            
            # Количество завершивших онбординг
            result = await session.execute(
                select(func.count(User.id)).where(
                    User.status == "active",
                    User.onboarding_stage == OnboardingStage.COMPLETED
                )
            )
            completed_onboarding = result.scalar() or 0
            
            # Количество оплативших
            result = await session.execute(
                select(func.count(User.id)).where(
                    User.status == "active",
                    User.payment_completed == True
                )
            )
            paid_users = result.scalar() or 0
            
            return {
                'total_active': total_active,
                'completed_onboarding': completed_onboarding,
                'paid_users': paid_users,
                'incomplete_onboarding': total_active - completed_onboarding
            }
            
        except Exception as e:
            logger.error(f"Error getting broadcast statistics: {e}")
            return {
                'total_active': 0,
                'completed_onboarding': 0,
                'paid_users': 0,
                'incomplete_onboarding': 0
            }


class SaleCRUD:
    @staticmethod
    async def create_sale(session: AsyncSession, ref_code: str, amount: float,
                         commission_percent: float, customer_email: str, product: str) -> Sale:
        """Создание записи о продаже с АВТОМАТИЧЕСКИМ ПОДТВЕРЖДЕНИЕМ"""
        commission_amount = amount * commission_percent / 100
        sale = Sale(
            ref_code=ref_code,
            amount=amount,
            commission_percent=commission_percent,
            commission_amount=commission_amount,
            customer_email=customer_email,
            product=product,
            status="confirmed"  # СРАЗУ ПОДТВЕРЖДЕМ для тестовых платежей
        )
        session.add(sale)
        await session.commit()
        await session.refresh(sale)
        return sale
    
    @staticmethod
    async def get_user_sales(session: AsyncSession, ref_code: str) -> List[Sale]:
        """Получение продаж пользователя - ИСПРАВЛЕНО"""
        try:
            result = await session.execute(
                select(Sale).where(Sale.ref_code == ref_code)
            )
            sales = result.scalars().all()
            return list(sales)  # Конвертируем в список для избежания проблем
        except Exception as e:
            # Логируем ошибку, но возвращаем пустой список
            logger.error(f"Error getting sales for ref_code {ref_code}: {e}")
            return []
    
    @staticmethod
    async def count_user_sales(session: AsyncSession, ref_code: str) -> int:
        """Подсчет количества продаж пользователя"""
        try:
            result = await session.execute(
                select(func.count(Sale.id)).where(Sale.ref_code == ref_code)
            )
            count = result.scalar()
            return count or 0
        except Exception as e:
            logger.error(f"Error counting sales for ref_code {ref_code}: {e}")
            return 0
    
    @staticmethod
    async def count_confirmed_sales(session: AsyncSession, ref_code: str) -> int:
        """Подсчет количества подтвержденных продаж"""
        try:
            result = await session.execute(
                select(func.count(Sale.id)).where(
                    Sale.ref_code == ref_code,
                    Sale.status == "confirmed"
                )
            )
            count = result.scalar()
            return count or 0
        except Exception as e:
            logger.error(f"Error counting confirmed sales for ref_code {ref_code}: {e}")
            return 0
    
    @staticmethod
    async def get_total_commission(session: AsyncSession, ref_code: str) -> float:
        """Получение общей суммы комиссии - ИСПРАВЛЕНО"""
        try:
            result = await session.execute(
                select(func.sum(Sale.commission_amount)).where(
                    Sale.ref_code == ref_code,
                    Sale.status == "confirmed"
                )
            )
            total = result.scalar()
            # ВАЖНО: если нет продаж, scalar() возвращает None
            return float(total or 0)
        except Exception as e:
            logger.error(f"Error getting total commission for ref_code {ref_code}: {e}")
            return 0.0


# CRUD для новых моделей онбординга

class CourseVideoCRUD:
    @staticmethod
    async def get_all_videos(session: AsyncSession) -> List[CourseVideo]:
        """Получение всех активных видео курса"""
        result = await session.execute(
            select(CourseVideo)
            .where(CourseVideo.is_active == True)
            .order_by(CourseVideo.lesson_number)
        )
        return result.scalars().all()
    
    @staticmethod
    async def get_video_by_lesson(session: AsyncSession, lesson_number: int) -> Optional[CourseVideo]:
        """Получение видео по номеру урока"""
        result = await session.execute(
            select(CourseVideo)
            .where(CourseVideo.lesson_number == lesson_number)
            .where(CourseVideo.is_active == True)
        )
        return result.scalar_one_or_none()
    
    @staticmethod
    async def create_video(session: AsyncSession, lesson_number: int, title: str,
                          video_file_id: str, description: str = None,
                          duration_seconds: int = None) -> CourseVideo:
        """Создание записи о видео"""
        video = CourseVideo(
            lesson_number=lesson_number,
            title=title,
            description=description,
            video_file_id=video_file_id,
            duration_seconds=duration_seconds
        )
        session.add(video)
        await session.commit()
        await session.refresh(video)
        return video


class UserCourseProgressCRUD:
    @staticmethod
    async def start_lesson(session: AsyncSession, user_id: int, lesson_number: int) -> UserCourseProgress:
        """Начало просмотра урока"""
        # Проверяем, есть ли уже запись
        result = await session.execute(
            select(UserCourseProgress)
            .where(UserCourseProgress.user_id == user_id)
            .where(UserCourseProgress.lesson_number == lesson_number)
        )
        progress = result.scalar_one_or_none()
        
        if not progress:
            progress = UserCourseProgress(
                user_id=user_id,
                lesson_number=lesson_number
            )
            session.add(progress)
            await session.commit()
            await session.refresh(progress)
        
        return progress
    
    @staticmethod
    async def complete_lesson(session: AsyncSession, user_id: int, lesson_number: int,
                            watch_time_seconds: int = 0) -> bool:
        """Завершение просмотра урока"""
        result = await session.execute(
            update(UserCourseProgress)
            .where(UserCourseProgress.user_id == user_id)
            .where(UserCourseProgress.lesson_number == lesson_number)
            .values(
                is_completed=True,
                completed_at=datetime.now(),
                watch_time_seconds=watch_time_seconds
            )
        )
        await session.commit()
        return result.rowcount > 0
    
    @staticmethod
    async def get_user_progress(session: AsyncSession, user_id: int) -> List[UserCourseProgress]:
        """Получение прогресса пользователя по курсу"""
        result = await session.execute(
            select(UserCourseProgress)
            .where(UserCourseProgress.user_id == user_id)
            .order_by(UserCourseProgress.lesson_number)
        )
        return result.scalars().all()
    
    @staticmethod
    async def get_completed_lessons_count(session: AsyncSession, user_id: int) -> int:
        """Количество завершенных уроков"""
        result = await session.execute(
            select(UserCourseProgress)
            .where(UserCourseProgress.user_id == user_id)
            .where(UserCourseProgress.is_completed == True)
        )
        return len(result.scalars().all())


class PaymentCRUD:
    @staticmethod
    async def create_payment(
        session: AsyncSession,
        user_id: int,
        invoice_id: str,
        amount: float,
        description: str,
        metadata: dict = None
    ) -> Payment:
        """Создание нового платежа"""
        import json
        payment = Payment(
            user_id=user_id,
            invoice_id=invoice_id,
            amount=amount,
            description=description,
            payment_metadata=json.dumps(metadata) if metadata else None
        )
        session.add(payment)
        await session.commit()
        await session.refresh(payment)
        return payment
    
    @staticmethod
    async def get_payment_by_invoice_id(session: AsyncSession, invoice_id: str) -> Optional[Payment]:
        """Получение платежа по invoice_id"""
        result = await session.execute(
            select(Payment).where(Payment.invoice_id == invoice_id)
        )
        return result.scalar_one_or_none()
    
    @staticmethod
    async def update_payment_status(
        session: AsyncSession,
        payment_id: int,
        status: str,
        robokassa_signature: str = None,
        robokassa_out_sum: float = None
    ) -> Optional[Payment]:
        """Обновление статуса платежа"""
        result = await session.execute(
            select(Payment).where(Payment.id == payment_id)
        )
        payment = result.scalar_one_or_none()
        
        if payment:
            payment.status = status
            if robokassa_signature:
                payment.robokassa_signature = robokassa_signature
            if robokassa_out_sum:
                payment.robokassa_out_sum = robokassa_out_sum
            if status == "paid":
                payment.paid_at = datetime.now()
            
            await session.commit()
            await session.refresh(payment)
        
        return payment
    
    @staticmethod
    async def get_user_payments(session: AsyncSession, user_id: int):
        """Получение всех платежей пользователя"""
        result = await session.execute(
            select(Payment)
            .where(Payment.user_id == user_id)
            .order_by(Payment.created_at.desc())
        )
        return result.scalars().all()
    
    @staticmethod
    async def get_payments_by_status(session: AsyncSession, status: str):
        """Получение платежей по статусу"""
        result = await session.execute(
            select(Payment).where(Payment.status == status)
        )
        return result.scalars().all()
        
        
class AutomatedMessageCRUD:
    @staticmethod
    async def create_message(
        session: AsyncSession, user_id: int, telegram_id: int,
        video_file_id: str, video_type: str, required_stage: str,
        scheduled_at: datetime, blocked_stages: list = None
    ) -> AutomatedMessage:
        import json
        message = AutomatedMessage(
            user_id=user_id, telegram_id=telegram_id,
            video_file_id=video_file_id, video_type=video_type,
            required_stage=required_stage,
            blocked_stages=json.dumps(blocked_stages) if blocked_stages else None,
            scheduled_at=scheduled_at, status=AutomatedMessageStatus.SCHEDULED
        )
        session.add(message)
        await session.commit()
        await session.refresh(message)
        return message
    
    @staticmethod
    async def get_pending_messages(session: AsyncSession, limit: int = 100):
        result = await session.execute(
            select(AutomatedMessage)
            .where(AutomatedMessage.status == AutomatedMessageStatus.SCHEDULED)
            .where(AutomatedMessage.scheduled_at <= datetime.now())
            .order_by(AutomatedMessage.scheduled_at).limit(limit)
        )
        return result.scalars().all()
    
    @staticmethod
    async def update_message_status(session: AsyncSession, message_id: int, 
                                   status: str, error_message: str = None):
        values = {"status": status}
        if status == AutomatedMessageStatus.SENT:
            values["sent_at"] = datetime.now()
        if error_message:
            values["error_message"] = error_message
        
        result = await session.execute(
            update(AutomatedMessage).where(AutomatedMessage.id == message_id).values(**values)
        )
        await session.commit()
        return result.rowcount > 0
    
    @staticmethod
    async def cancel_user_messages(session: AsyncSession, telegram_id: int, 
                                   video_types: list = None):
        query = update(AutomatedMessage).where(
            AutomatedMessage.telegram_id == telegram_id,
            AutomatedMessage.status == AutomatedMessageStatus.SCHEDULED
        )
        if video_types:
            query = query.where(AutomatedMessage.video_type.in_(video_types))
        query = query.values(status=AutomatedMessageStatus.CANCELLED)
        
        result = await session.execute(query)
        await session.commit()
        return result.rowcount
    
    @staticmethod
    async def get_user_scheduled_messages(session: AsyncSession, telegram_id: int):
        result = await session.execute(
            select(AutomatedMessage)
            .where(AutomatedMessage.telegram_id == telegram_id)
            .where(AutomatedMessage.status == AutomatedMessageStatus.SCHEDULED)
            .order_by(AutomatedMessage.scheduled_at)
        )
        return result.scalars().all()