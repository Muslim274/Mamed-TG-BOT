"""
CRUD операции для системы тикетов
app/database/ticket_crud.py
"""
from sqlalchemy import select, update, func, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from datetime import datetime
from typing import Optional, List

from app.database.models import Ticket, TicketMessage, TicketStatus, User


class TicketCRUD:
    """CRUD операции для тикетов"""
    
    @staticmethod
    async def get_or_create_ticket(session: AsyncSession, telegram_id: int) -> Ticket:
        """Получить или создать тикет для пользователя"""
        # Ищем активный тикет
        result = await session.execute(
            select(Ticket)
            .where(Ticket.telegram_id == telegram_id)
            .where(Ticket.status == TicketStatus.OPEN)
            .order_by(Ticket.updated_at.desc())
        )
        ticket = result.scalar_one_or_none()
        
        if ticket:
            return ticket
        
        # Ищем закрытый тикет для реактивации
        result = await session.execute(
            select(Ticket)
            .where(Ticket.telegram_id == telegram_id)
            .where(Ticket.status == TicketStatus.CLOSED)
            .order_by(Ticket.updated_at.desc())
        )
        closed_ticket = result.scalar_one_or_none()
        
        if closed_ticket:
            # Реактивируем закрытый тикет
            closed_ticket.status = TicketStatus.OPEN
            closed_ticket.updated_at = datetime.now()
            closed_ticket.closed_at = None
            await session.commit()
            await session.refresh(closed_ticket)
            return closed_ticket
        
        # Создаем новый тикет
        # Получаем user_id
        user_result = await session.execute(
            select(User).where(User.telegram_id == telegram_id)
        )
        user = user_result.scalar_one_or_none()
        
        if not user:
            raise ValueError(f"User with telegram_id {telegram_id} not found")
        
        ticket = Ticket(
            user_id=user.id,
            telegram_id=telegram_id,
            status=TicketStatus.OPEN
        )
        session.add(ticket)
        await session.commit()
        await session.refresh(ticket)
        return ticket
    
    @staticmethod
    async def add_message(
        session: AsyncSession,
        ticket_id: int,
        text: str = None,
        from_user: bool = True,
        telegram_message_id: int = None,
        media_type: str = None,
        media_file_id: str = None
    ) -> TicketMessage:
        """Добавить сообщение в тикет"""
        message = TicketMessage(
            ticket_id=ticket_id,
            text=text,
            from_user=from_user,
            telegram_message_id=telegram_message_id,
            media_type=media_type,
            media_file_id=media_file_id,
            is_read=not from_user  # Сообщения админа сразу помечаем прочитанными
        )
        session.add(message)
        
        # Обновляем тикет
        ticket_result = await session.execute(
            select(Ticket).where(Ticket.id == ticket_id)
        )
        ticket = ticket_result.scalar_one()
        
        ticket.total_messages += 1
        ticket.updated_at = datetime.now()
        
        if from_user:
            ticket.unread_messages += 1
            # Устанавливаем тему тикета из первого сообщения
            if not ticket.subject and text:
                ticket.subject = text[:50] + "..." if len(text) > 50 else text
        else:
            ticket.last_admin_reply_at = datetime.now()
        
        await session.commit()
        await session.refresh(message)
        return message
    
    @staticmethod
    async def mark_messages_read(session: AsyncSession, ticket_id: int) -> int:
        """Отметить все сообщения тикета как прочитанные"""
        # Обновляем непрочитанные сообщения
        result = await session.execute(
            update(TicketMessage)
            .where(and_(
                TicketMessage.ticket_id == ticket_id,
                TicketMessage.from_user == True,
                TicketMessage.is_read == False
            ))
            .values(is_read=True)
        )
        
        # Сбрасываем счетчик непрочитанных
        await session.execute(
            update(Ticket)
            .where(Ticket.id == ticket_id)
            .values(unread_messages=0)
        )
        
        await session.commit()
        return result.rowcount
    
    @staticmethod
    async def close_ticket(session: AsyncSession, ticket_id: int) -> bool:
        """Закрыть тикет"""
        result = await session.execute(
            update(Ticket)
            .where(Ticket.id == ticket_id)
            .values(
                status=TicketStatus.CLOSED,
                closed_at=datetime.now(),
                unread_messages=0
            )
        )
        await session.commit()
        return result.rowcount > 0
    
    @staticmethod
    async def get_open_tickets(session: AsyncSession) -> List[Ticket]:
        """Получить все открытые тикеты"""
        result = await session.execute(
            select(Ticket)
            .options(selectinload(Ticket.user))
            .where(Ticket.status == TicketStatus.OPEN)
            .order_by(Ticket.updated_at.desc())
        )
        return list(result.scalars().all())
    
    @staticmethod
    async def get_closed_tickets(session: AsyncSession, limit: int = 20) -> List[Ticket]:
        """Получить закрытые тикеты"""
        result = await session.execute(
            select(Ticket)
            .options(selectinload(Ticket.user))
            .where(Ticket.status == TicketStatus.CLOSED)
            .order_by(Ticket.closed_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())
    
    @staticmethod
    async def get_ticket_messages(session: AsyncSession, ticket_id: int, limit: int = 50) -> List[TicketMessage]:
        """Получить сообщения тикета"""
        result = await session.execute(
            select(TicketMessage)
            .where(TicketMessage.ticket_id == ticket_id)
            .order_by(TicketMessage.created_at.asc())
            .limit(limit)
        )
        return list(result.scalars().all())
    
    @staticmethod
    async def get_ticket_by_telegram_id(session: AsyncSession, telegram_id: int) -> Optional[Ticket]:
        """Получить активный тикет пользователя"""
        result = await session.execute(
            select(Ticket)
            .options(selectinload(Ticket.user))
            .where(and_(
                Ticket.telegram_id == telegram_id,
                Ticket.status == TicketStatus.OPEN
            ))
            .order_by(Ticket.updated_at.desc())
        )
        return result.scalar_one_or_none()
    
    @staticmethod
    async def find_ticket_by_message_id(session: AsyncSession, telegram_message_id: int) -> Optional[Ticket]:
        """Найти тикет по ID сообщения Telegram"""
        result = await session.execute(
            select(Ticket)
            .join(TicketMessage)
            .where(TicketMessage.telegram_message_id == telegram_message_id)
        )
        return result.scalar_one_or_none()
    
    @staticmethod
    async def get_ticket_stats(session: AsyncSession) -> dict:
        """Получить статистику тикетов"""
        # Открытые тикеты
        open_result = await session.execute(
            select(func.count(Ticket.id))
            .where(Ticket.status == TicketStatus.OPEN)
        )
        open_count = open_result.scalar()
        
        # Непрочитанные сообщения
        unread_result = await session.execute(
            select(func.sum(Ticket.unread_messages))
            .where(Ticket.status == TicketStatus.OPEN)
        )
        unread_count = unread_result.scalar() or 0
        
        # Закрытые за последние 24 часа
        from datetime import timedelta
        yesterday = datetime.now() - timedelta(hours=24)
        
        closed_today_result = await session.execute(
            select(func.count(Ticket.id))
            .where(and_(
                Ticket.status == TicketStatus.CLOSED,
                Ticket.closed_at >= yesterday
            ))
        )
        closed_today = closed_today_result.scalar()
        
        return {
            "open_tickets": open_count,
            "unread_messages": unread_count,
            "closed_today": closed_today
        }