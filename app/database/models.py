"""
Модели базы данных - обновленная версия с онбордингом
"""
from sqlalchemy import Column, Integer, String, DateTime, Float, Boolean, ForeignKey, BigInteger, Text, Index
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from enum import Enum

from app.database.connection import Base


    
class OnboardingStage(str, Enum):
    """Стадии онбординга"""
    NEW_USER = "new_user"
    INTRO_SHOWN = "intro_shown"
    WAIT_PAYMENT = "wait_payment"
    PAYMENT_OK = "payment_ok"
    WANT_JOIN = "want_join"
    READY_START = "ready_start"
    PARTNER_LESSON = "partner_lesson"
    LESSON_DONE = "lesson_done"
    GOT_LINK = "got_link"
    AWAITING_APPROVAL = "awaiting_approval"  # НОВАЯ СТАДИЯ
    COMPLETED = "completed"


class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True)
    telegram_id = Column(BigInteger, unique=True, index=True)
    username = Column(String, nullable=True)
    full_name = Column(String)
    ref_code = Column(String, unique=True, index=True)
    referred_by = Column(String, nullable=True)
    email = Column(String, nullable=True)
    phone = Column(String, nullable=True)
    status = Column(String, default="active")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    tickets = relationship("Ticket", back_populates="user")
    
    # 🆕 Onboarding fields
    onboarding_stage = Column(String, default=OnboardingStage.NEW_USER)
    payment_completed = Column(Boolean, default=False)
    current_course_step = Column(Integer, default=0)
    course_completed_at = Column(DateTime(timezone=True), nullable=True)
    partner_offer_shown_at = Column(DateTime(timezone=True), nullable=True)
    onboarding_completed_at = Column(DateTime(timezone=True), nullable=True)
    
    # Relationships
    clicks = relationship("Click", back_populates="user")
    sales = relationship("Sale", back_populates="user")
    withdrawals = relationship("Withdrawal", back_populates="user")
    course_progress = relationship("UserCourseProgress", back_populates="user")
    payments = relationship("Payment", back_populates="user")
    
    gender = Column(String, nullable=True)  # 'male', 'female', None
    
    # Временные метки переходов между стадиями
    stage_new_user_at = Column(DateTime(timezone=True), nullable=True)
    stage_intro_shown_at = Column(DateTime(timezone=True), nullable=True)
    stage_wait_payment_at = Column(DateTime(timezone=True), nullable=True)
    stage_payment_ok_at = Column(DateTime(timezone=True), nullable=True)
    stage_want_join_at = Column(DateTime(timezone=True), nullable=True)
    stage_completed_at = Column(DateTime(timezone=True), nullable=True)



class Sale(Base):
    __tablename__ = "sales"
    
    id = Column(Integer, primary_key=True)
    ref_code = Column(String, ForeignKey("users.ref_code"))
    amount = Column(Float)
    commission_percent = Column(Float)
    commission_amount = Column(Float)
    status = Column(String, default="pending")
    customer_email = Column(String)
    product = Column(String)
    # УБРАЛИ: payment_id = Column(Integer, ForeignKey("payments.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    user = relationship("User", back_populates="sales")
    # УБРАЛИ: payment = relationship("Payment", back_populates="sale")


class Withdrawal(Base):
    __tablename__ = "withdrawals"
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    amount = Column(Float)
    method = Column(String)
    requisites = Column(String)
    status = Column(String, default="pending")
    comment = Column(String, nullable=True)
    requested_at = Column(DateTime(timezone=True), server_default=func.now())
    processed_at = Column(DateTime(timezone=True), nullable=True)
    
    # Relationships
    user = relationship("User", back_populates="withdrawals")


# 🆕 Новые модели для онбординга

class CourseVideo(Base):
    __tablename__ = "course_videos"
    
    id = Column(Integer, primary_key=True)
    lesson_number = Column(Integer, nullable=False, unique=True)
    title = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    video_file_id = Column(String, nullable=False)
    duration_seconds = Column(Integer, nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    progress_records = relationship("UserCourseProgress", back_populates="video")


class UserCourseProgress(Base):
    __tablename__ = "user_course_progress"
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    lesson_number = Column(Integer, ForeignKey("course_videos.lesson_number"))
    started_at = Column(DateTime(timezone=True), server_default=func.now())
    completed_at = Column(DateTime(timezone=True), nullable=True)
    is_completed = Column(Boolean, default=False)
    watch_time_seconds = Column(Integer, default=0)
    
    # Relationships
    user = relationship("User", back_populates="course_progress")
    video = relationship("CourseVideo", back_populates="progress_records")
    
# Добавьте эти строки в конец файла app/database/models.py

class Payment(Base):
    """Модель для хранения информации о платежах"""
    __tablename__ = "payments"
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    
    # Robokassa данные
    invoice_id = Column(String, unique=True, index=True)
    amount = Column(Float)
    description = Column(String)
    
    # Статусы платежа
    status = Column(String, default="created")
    
    # Данные от Robokassa
    robokassa_signature = Column(String, nullable=True)
    robokassa_out_sum = Column(Float, nullable=True)
    
    # Метаданные
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    paid_at = Column(DateTime(timezone=True), nullable=True)
    
    # Additional data
    payment_metadata = Column(Text, nullable=True)
    
    # Relationships
    user = relationship("User", back_populates="payments")
    # УБРАЛИ: sale = relationship("Sale", back_populates="payment", uselist=False)


"""
Модель тикетов для системы поддержки
app/database/models.py (добавить к существующим моделям)
"""


class TicketStatus(str, Enum):
    """Статусы тикетов"""
    OPEN = "open"
    CLOSED = "closed"


class Ticket(Base):
    """Модель тикета поддержки"""
    __tablename__ = "tickets"
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    telegram_id = Column(BigInteger, nullable=False, index=True)  # Дубль для быстрого поиска
    
    status = Column(String, default=TicketStatus.OPEN)
    subject = Column(String, nullable=True)  # Тема тикета (первые слова сообщения)
    
    # Счетчики сообщений
    unread_messages = Column(Integer, default=0)  # Непрочитанные админом
    total_messages = Column(Integer, default=0)   # Всего сообщений в тикете
    
    # Временные метки
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), default=func.now())
    closed_at = Column(DateTime(timezone=True), nullable=True)
    last_admin_reply_at = Column(DateTime(timezone=True), nullable=True)
    
    # Связи
    user = relationship("User", back_populates="tickets")
    messages = relationship("TicketMessage", back_populates="ticket", cascade="all, delete-orphan")


class TicketMessage(Base):
    """Сообщения в тикете"""
    __tablename__ = "ticket_messages"
    
    id = Column(Integer, primary_key=True)
    ticket_id = Column(Integer, ForeignKey("tickets.id"), nullable=False)
    
    # Автор сообщения
    from_user = Column(Boolean, default=True)  # True = от пользователя, False = от админа
    telegram_message_id = Column(Integer, nullable=True)  # ID сообщения в Telegram
    
    # Содержимое
    text = Column(Text, nullable=True)
    media_type = Column(String, nullable=True)  # photo, voice, video, document
    media_file_id = Column(String, nullable=True)  # file_id для медиа
    
    # Статус прочтения
    is_read = Column(Boolean, default=False)
    
    # Временные метки
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Связи
    ticket = relationship("Ticket", back_populates="messages")


# Добавить к модели User связь с тикетами
# В классе User добавить:
# tickets = relationship("Ticket", back_populates="user")


# Добавляем в models.py новые поля и таблицу

# 1. Обновляем модель Click - добавляем поле user_telegram_id
class Click(Base):
    __tablename__ = "clicks"
    
    id = Column(Integer, primary_key=True)
    ref_code = Column(String, ForeignKey("users.ref_code"))
    ip_address = Column(String)
    user_agent = Column(String)
    source = Column(String, nullable=True)
    user_telegram_id = Column(BigInteger, nullable=True)  # НОВОЕ ПОЛЕ
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    user = relationship("User", back_populates="clicks")


# 2. Добавляем новую модель для аналитики
class ReferralHistory(Base):
    __tablename__ = "referral_history"
    
    id = Column(Integer, primary_key=True)
    user_telegram_id = Column(BigInteger, nullable=False)
    ref_code = Column(String, nullable=False)
    action_type = Column(String, nullable=False)  # "click", "payment"
    ip_address = Column(String, nullable=True)
    user_agent = Column(String, nullable=True)
    amount = Column(Float, nullable=True)  # для action_type="payment"
    commission_amount = Column(Float, nullable=True)  # для action_type="payment"
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Indexes для быстрого поиска
    __table_args__ = (
        Index('idx_referral_history_user_created', 'user_telegram_id', 'created_at'),
        Index('idx_referral_history_ref_code', 'ref_code'),
    )

class AutomatedMessageStatus(str, Enum):
    SCHEDULED = "scheduled"
    SENT = "sent"
    CANCELLED = "cancelled"
    FAILED = "failed"


class AutomatedMessage(Base):
    __tablename__ = "automated_messages"
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    telegram_id = Column(BigInteger, nullable=False, index=True)
    video_file_id = Column(String, nullable=False)
    video_type = Column(String, nullable=False)
    required_stage = Column(String, nullable=False)
    blocked_stages = Column(Text, nullable=True)
    scheduled_at = Column(DateTime(timezone=True), nullable=False, index=True)
    sent_at = Column(DateTime(timezone=True), nullable=True)
    status = Column(String, default=AutomatedMessageStatus.SCHEDULED, index=True)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    __table_args__ = (
        Index('idx_automated_messages_status_scheduled', 'status', 'scheduled_at'),
    )