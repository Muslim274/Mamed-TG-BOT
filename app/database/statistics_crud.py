"""
CRUD функции для статистики и сегментации пользователей
"""
from datetime import datetime, timedelta
from sqlalchemy import select, and_, or_, func
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Dict, Optional
from app.database.models import User, Sale, Payment, OnboardingStage


class StatisticsCRUD:
    """CRUD операции для статистики"""

    @staticmethod
    async def get_daily_sales(session: AsyncSession, date: datetime = None) -> Dict:
        """
        Получить продажи за день

        Args:
            session: Сессия БД
            date: Дата (по умолчанию сегодня)

        Returns:
            Dict с информацией о продажах
        """
        if date is None:
            date = datetime.now()

        start_of_day = date.replace(hour=0, minute=0, second=0, microsecond=0)
        end_of_day = start_of_day + timedelta(days=1)

        # Получаем продажи за день
        stmt = select(Sale).where(
            and_(
                Sale.created_at >= start_of_day,
                Sale.created_at < end_of_day
            )
        )
        result = await session.execute(stmt)
        sales = result.scalars().all()

        total_amount = sum(sale.amount for sale in sales)
        total_commission = sum(sale.commission_amount for sale in sales)

        return {
            "count": len(sales),
            "total_amount": total_amount,
            "total_commission": total_commission,
            "sales": sales
        }

    @staticmethod
    async def get_daily_buyers(session: AsyncSession, date: datetime = None) -> List[Dict]:
        """
        Получить список покупателей за день

        Args:
            session: Сессия БД
            date: Дата (по умолчанию сегодня)

        Returns:
            List с информацией о покупателях
        """
        if date is None:
            date = datetime.now()

        start_of_day = date.replace(hour=0, minute=0, second=0, microsecond=0)
        end_of_day = start_of_day + timedelta(days=1)

        # Получаем пользователей, которые оплатили за день
        stmt = select(User, Payment).join(
            Payment, User.id == Payment.user_id
        ).where(
            and_(
                Payment.paid_at >= start_of_day,
                Payment.paid_at < end_of_day,
                Payment.status == "paid"
            )
        )

        result = await session.execute(stmt)
        buyers_data = result.all()

        buyers = []
        for user, payment in buyers_data:
            buyers.append({
                "user_id": user.id,
                "telegram_id": user.telegram_id,
                "username": user.username,
                "full_name": user.full_name,
                "amount": payment.amount,
                "purchased_at": payment.paid_at,
                "product": "Партнерская программа"
            })

        return buyers

    @staticmethod
    async def get_new_leads(session: AsyncSession, date: datetime = None) -> List[User]:
        """
        Получить новых лидов (новых пользователей) за день

        Args:
            session: Сессия БД
            date: Дата (по умолчанию сегодня)

        Returns:
            List пользователей
        """
        if date is None:
            date = datetime.now()

        start_of_day = date.replace(hour=0, minute=0, second=0, microsecond=0)
        end_of_day = start_of_day + timedelta(days=1)

        stmt = select(User).where(
            and_(
                User.created_at >= start_of_day,
                User.created_at < end_of_day
            )
        )

        result = await session.execute(stmt)
        return result.scalars().all()

    @staticmethod
    async def get_new_partners(session: AsyncSession, date: datetime = None) -> List[User]:
        """
        Получить новых партнеров (кто завершил онбординг) за день

        Args:
            session: Сессия БД
            date: Дата (по умолчанию сегодня)

        Returns:
            List пользователей
        """
        if date is None:
            date = datetime.now()

        start_of_day = date.replace(hour=0, minute=0, second=0, microsecond=0)
        end_of_day = start_of_day + timedelta(days=1)

        stmt = select(User).where(
            and_(
                User.stage_completed_at >= start_of_day,
                User.stage_completed_at < end_of_day,
                User.onboarding_stage == OnboardingStage.COMPLETED
            )
        )

        result = await session.execute(stmt)
        return result.scalars().all()

    @staticmethod
    async def get_partners_without_team(session: AsyncSession, date: datetime = None) -> List[User]:
        """
        Получить партнеров, которые купили но не нажали кнопку "Команда"

        Args:
            session: Сессия БД
            date: Дата (по умолчанию сегодня, None = все время)

        Returns:
            List пользователей
        """
        conditions = [
            User.payment_completed == True,
            User.onboarding_stage != OnboardingStage.COMPLETED
        ]

        if date is not None:
            start_of_day = date.replace(hour=0, minute=0, second=0, microsecond=0)
            end_of_day = start_of_day + timedelta(days=1)
            conditions.extend([
                User.stage_payment_ok_at >= start_of_day,
                User.stage_payment_ok_at < end_of_day
            ])

        stmt = select(User).where(and_(*conditions))

        result = await session.execute(stmt)
        return result.scalars().all()

    @staticmethod
    async def get_period_sales(session: AsyncSession, start_date: datetime, end_date: datetime) -> Dict:
        """
        Получить продажи за период

        Args:
            session: Сессия БД
            start_date: Начальная дата
            end_date: Конечная дата

        Returns:
            Dict с информацией о продажах
        """
        start = start_date.replace(hour=0, minute=0, second=0, microsecond=0)
        end = end_date.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)

        stmt = select(Sale).where(
            and_(
                Sale.created_at >= start,
                Sale.created_at < end
            )
        )
        result = await session.execute(stmt)
        sales = result.scalars().all()

        total_amount = sum(sale.amount for sale in sales)
        total_commission = sum(sale.commission_amount for sale in sales)

        return {
            "count": len(sales),
            "total_amount": total_amount,
            "total_commission": total_commission,
            "sales": sales
        }

    @staticmethod
    async def get_period_buyers(session: AsyncSession, start_date: datetime, end_date: datetime) -> List[Dict]:
        """
        Получить список покупателей за период

        Args:
            session: Сессия БД
            start_date: Начальная дата
            end_date: Конечная дата

        Returns:
            List с информацией о покупателях
        """
        start = start_date.replace(hour=0, minute=0, second=0, microsecond=0)
        end = end_date.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)

        stmt = select(User, Payment).join(
            Payment, User.id == Payment.user_id
        ).where(
            and_(
                Payment.paid_at >= start,
                Payment.paid_at < end,
                Payment.status == "paid"
            )
        )

        result = await session.execute(stmt)
        buyers_data = result.all()

        buyers = []
        for user, payment in buyers_data:
            buyers.append({
                "user_id": user.id,
                "telegram_id": user.telegram_id,
                "username": user.username,
                "full_name": user.full_name,
                "amount": payment.amount,
                "purchased_at": payment.paid_at,
                "product": "Партнерская программа"
            })

        return buyers

    @staticmethod
    async def get_period_leads(session: AsyncSession, start_date: datetime, end_date: datetime) -> List[User]:
        """
        Получить новых лидов за период

        Args:
            session: Сессия БД
            start_date: Начальная дата
            end_date: Конечная дата

        Returns:
            List пользователей
        """
        start = start_date.replace(hour=0, minute=0, second=0, microsecond=0)
        end = end_date.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)

        stmt = select(User).where(
            and_(
                User.created_at >= start,
                User.created_at < end
            )
        )

        result = await session.execute(stmt)
        return result.scalars().all()

    @staticmethod
    async def get_period_partners(session: AsyncSession, start_date: datetime, end_date: datetime) -> List[User]:
        """
        Получить новых партнеров за период

        Args:
            session: Сессия БД
            start_date: Начальная дата
            end_date: Конечная дата

        Returns:
            List пользователей
        """
        start = start_date.replace(hour=0, minute=0, second=0, microsecond=0)
        end = end_date.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)

        stmt = select(User).where(
            and_(
                User.stage_completed_at >= start,
                User.stage_completed_at < end,
                User.onboarding_stage == OnboardingStage.COMPLETED
            )
        )

        result = await session.execute(stmt)
        return result.scalars().all()

    @staticmethod
    async def get_period_partners_without_team(session: AsyncSession, start_date: datetime, end_date: datetime) -> List[User]:
        """
        Получить партнеров без команды за период

        Args:
            session: Сессия БД
            start_date: Начальная дата
            end_date: Конечная дата

        Returns:
            List пользователей
        """
        start = start_date.replace(hour=0, minute=0, second=0, microsecond=0)
        end = end_date.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)

        stmt = select(User).where(
            and_(
                User.payment_completed == True,
                User.onboarding_stage != OnboardingStage.COMPLETED,
                User.stage_payment_ok_at >= start,
                User.stage_payment_ok_at < end
            )
        )

        result = await session.execute(stmt)
        return result.scalars().all()

    @staticmethod
    async def get_all_time_sales(session: AsyncSession) -> Dict:
        """
        Получить все продажи за всё время

        Returns:
            Dict с информацией о продажах
        """
        stmt = select(Sale)
        result = await session.execute(stmt)
        sales = result.scalars().all()

        total_amount = sum(sale.amount for sale in sales)
        total_commission = sum(sale.commission_amount for sale in sales)

        return {
            "count": len(sales),
            "total_amount": total_amount,
            "total_commission": total_commission,
            "sales": sales
        }

    @staticmethod
    async def get_all_time_buyers(session: AsyncSession) -> List[Dict]:
        """
        Получить всех покупателей за всё время

        Returns:
            List с информацией о покупателях
        """
        stmt = select(User, Payment).join(
            Payment, User.id == Payment.user_id
        ).where(Payment.status == "paid")

        result = await session.execute(stmt)
        buyers_data = result.all()

        buyers = []
        for user, payment in buyers_data:
            buyers.append({
                "user_id": user.id,
                "telegram_id": user.telegram_id,
                "username": user.username,
                "full_name": user.full_name,
                "amount": payment.amount,
                "purchased_at": payment.paid_at,
                "product": "Партнерская программа"
            })

        return buyers

    @staticmethod
    async def get_all_time_leads(session: AsyncSession) -> List[User]:
        """
        Получить всех лидов за всё время

        Returns:
            List пользователей
        """
        stmt = select(User)
        result = await session.execute(stmt)
        return result.scalars().all()

    @staticmethod
    async def get_all_time_partners(session: AsyncSession) -> List[User]:
        """
        Получить всех партнеров за всё время

        Returns:
            List пользователей
        """
        stmt = select(User).where(
            User.onboarding_stage == OnboardingStage.COMPLETED
        )

        result = await session.execute(stmt)
        return result.scalars().all()

    @staticmethod
    async def get_all_time_partners_without_team(session: AsyncSession) -> List[User]:
        """
        Получить всех партнеров без команды за всё время

        Returns:
            List пользователей
        """
        stmt = select(User).where(
            and_(
                User.payment_completed == True,
                User.onboarding_stage != OnboardingStage.COMPLETED
            )
        )

        result = await session.execute(stmt)
        return result.scalars().all()


class UserSegmentCRUD:
    """CRUD для сегментации пользователей"""

    @staticmethod
    async def get_segment_new_leads(session: AsyncSession) -> List[User]:
        """Получить сегмент: новые лиды (не оплатили)"""
        stmt = select(User).where(
            and_(
                User.payment_completed == False,
                User.onboarding_stage.in_([
                    OnboardingStage.NEW_USER,
                    OnboardingStage.INTRO_SHOWN,
                    OnboardingStage.WAIT_PAYMENT
                ])
            )
        )

        result = await session.execute(stmt)
        return result.scalars().all()

    @staticmethod
    async def get_segment_buyers(session: AsyncSession) -> List[User]:
        """Получить сегмент: покупатели (оплатили)"""
        stmt = select(User).where(
            User.payment_completed == True
        )

        result = await session.execute(stmt)
        return result.scalars().all()

    @staticmethod
    async def get_segment_partners(session: AsyncSession) -> List[User]:
        """Получить сегмент: партнеры (завершили онбординг)"""
        stmt = select(User).where(
            User.onboarding_stage == OnboardingStage.COMPLETED
        )

        result = await session.execute(stmt)
        return result.scalars().all()

    @staticmethod
    async def get_segment_partners_without_team(session: AsyncSession) -> List[User]:
        """Получить сегмент: партнеры без команды (купили, но не завершили)"""
        stmt = select(User).where(
            and_(
                User.payment_completed == True,
                User.onboarding_stage != OnboardingStage.COMPLETED,
                User.onboarding_stage != OnboardingStage.GOT_LINK
            )
        )

        result = await session.execute(stmt)
        return result.scalars().all()

    @staticmethod
    async def get_segment_partners_completed(session: AsyncSession) -> List[User]:
        """Получить сегмент: партнёры, завершившие обучение"""
        stmt = select(User).where(
            User.onboarding_stage == OnboardingStage.COMPLETED
        )

        result = await session.execute(stmt)
        return result.scalars().all()

    @staticmethod
    async def get_segment_partners_in_team(session: AsyncSession) -> List[User]:
        """Получить сегмент: партнёры, вступившие в команду (получили ссылку)"""
        stmt = select(User).where(
            User.onboarding_stage == OnboardingStage.GOT_LINK
        )

        result = await session.execute(stmt)
        return result.scalars().all()

    @staticmethod
    async def get_segment_learning_users(session: AsyncSession) -> List[User]:
        """Получить сегмент: пользователи, которые еще обучаются"""
        stmt = select(User).where(
            User.onboarding_stage.in_([
                OnboardingStage.WANT_JOIN,
                OnboardingStage.READY_START,
                OnboardingStage.PARTNER_LESSON,
                OnboardingStage.LESSON_DONE
            ])
        )

        result = await session.execute(stmt)
        return result.scalars().all()

    @staticmethod
    async def get_segment_count(session: AsyncSession, segment_name: str) -> int:
        """Получить количество пользователей в сегменте"""
        if segment_name == "new_leads":
            stmt = select(func.count(User.id)).where(
                and_(
                    User.payment_completed == False,
                    User.onboarding_stage.in_([
                        OnboardingStage.NEW_USER,
                        OnboardingStage.INTRO_SHOWN,
                        OnboardingStage.WAIT_PAYMENT
                    ])
                )
            )
        elif segment_name == "buyers":
            stmt = select(func.count(User.id)).where(
                User.payment_completed == True
            )
        elif segment_name == "partners":
            stmt = select(func.count(User.id)).where(
                User.onboarding_stage == OnboardingStage.COMPLETED
            )
        elif segment_name == "partners_without_team":
            stmt = select(func.count(User.id)).where(
                and_(
                    User.payment_completed == True,
                    User.onboarding_stage != OnboardingStage.COMPLETED
                )
            )
        else:
            return 0

        result = await session.execute(stmt)
        return result.scalar() or 0
