"""
================================================================================
МОДЕЛИ БАЗЫ ДАННЫХ
================================================================================

НАЗНАЧЕНИЕ:
    Описание всех таблиц базы данных для Telegram-бота партнерской программы.
    Содержит Enum-классы и SQLAlchemy модели для работы с БД.

ЧТО МОЖНО МЕНЯТЬ:
    ✅ Можно добавлять новые Enum значения (с осторожностью!)
    ❌ НЕ МЕНЯЙТЕ:
       - Названия таблиц (__tablename__)
       - Названия колонок (может сломать весь бот)
       - Типы данных колонок
       - Связи ForeignKey

ОСНОВНЫЕ ТАБЛИЦЫ:
    1. users - пользователи бота
    2. clicks - клики по реферальным ссылкам
    3. sales - продажи и комиссии
    4. payments - платежи за курс
    5. course_videos - видео уроки
    6. automated_messages - автоматические сообщения
    7. tickets - тикеты поддержки

ENUM КЛАССЫ:
    - OnboardingStage - этапы обучения пользователя
    - TicketStatus - статусы тикетов (открыт/закрыт)
    - AutomatedMessageStatus - статусы автосообщений

СВЯЗЬ С ДРУГИМИ ФАЙЛАМИ:
    - Используется в crud.py для операций с БД
    - Используется в handlers для работы с пользователями
    - Связано с connection.py (создание таблиц)

ВАЖНО:
    Изменение моделей требует создания миграции БД!

================================================================================
"""

from enum import Enum
from sqlalchemy import Column, Integer, String, BigInteger, Float, Boolean, Text, ForeignKey, TIMESTAMP
from sqlalchemy.sql import func
from app.database.connection import Base


# ============================================================================
# ENUM КЛАССЫ (константы-перечисления)
# ============================================================================

class OnboardingStage(str, Enum):
    """
    Стадии онбординга (обучения) пользователя

    Порядок прохождения:
    1. NEW_USER - новый пользователь (только зарегистрировался)
    2. INTRO_SHOWN - показано вступительное видео
    3. WAIT_PAYMENT - ожидает оплаты курса
    4. PAYMENT_OK - оплата прошла успешно
    5. WANT_JOIN - хочет стать партнером
    6. READY_START - готов начать обучение
    7. PARTNER_LESSON - проходит партнерский урок
    8. LESSON_DONE - урок завершен
    9. GOT_LINK - получил реферальную ссылку
    10. AWAITING_APPROVAL - ожидает подтверждения аккаунта
    11. COMPLETED - онбординг завершен
    """
    NEW_USER = "new_user"               # Новый пользователь
    INTRO_SHOWN = "intro_shown"         # Показано вступление
    WAIT_PAYMENT = "wait_payment"       # Ожидает оплаты
    PAYMENT_OK = "payment_ok"           # Оплата успешна
    WANT_JOIN = "want_join"             # Хочет присоединиться
    READY_START = "ready_start"         # Готов начать
    PARTNER_LESSON = "partner_lesson"   # Проходит урок
    LESSON_DONE = "lesson_done"         # Урок завершен
    GOT_LINK = "got_link"               # Получил ссылку
    AWAITING_APPROVAL = "awaiting_approval"  # Ждет подтверждения
    COMPLETED = "completed"             # Завершено


class TicketStatus(str, Enum):
    """
    Статусы тикетов техподдержки

    - OPEN - тикет открыт (ожидает ответа)
    - CLOSED - тикет закрыт (вопрос решен)
    """
    OPEN = "open"       # Открыт
    CLOSED = "closed"   # Закрыт


class AutomatedMessageStatus(str, Enum):
    """
    Статусы автоматических сообщений (дожимающие видео)

    - SCHEDULED - запланировано (еще не отправлено)
    - SENT - отправлено успешно
    - CANCELLED - отменено (пользователь продвинулся дальше)
    - FAILED - ошибка отправки
    """
    SCHEDULED = "scheduled"     # Запланировано
    SENT = "sent"               # Отправлено
    CANCELLED = "cancelled"     # Отменено
    FAILED = "failed"           # Ошибка


# ============================================================================
# МОДЕЛИ ТАБЛИЦ БД (SQLAlchemy ORM)
# ============================================================================

class User(Base):
    """
    ТАБЛИЦА: users

    НАЗНАЧЕНИЕ:
        Хранит информацию о всех пользователях бота

    ОСНОВНЫЕ ПОЛЯ:
        - telegram_id: ID пользователя в Telegram (уникальный)
        - username: Username в Telegram (@username)
        - full_name: Полное имя пользователя
        - ref_code: Уникальный реферальный код (например: ref_123456)
        - referred_by: Кто пригласил пользователя (ref_code пригласившего)
        - onboarding_stage: Текущий этап обучения
        - payment_completed: Оплатил ли курс (True/False)
        - gender: Пол (male/female) - для направления к нужному админу

    МОЖНО МЕНЯТЬ:
        ❌ НЕ МЕНЯЙТЕ названия полей!
    """
    __tablename__ = 'users'

    # Основные поля
    id = Column(Integer, primary_key=True)                          # ID в БД (автоинкремент)
    telegram_id = Column(BigInteger, unique=True, nullable=False)   # Telegram ID (уникальный!)
    username = Column(String(255))                                  # @username
    full_name = Column(String(255), nullable=False)                 # Имя Фамилия
    ref_code = Column(String(255), unique=True, nullable=False)     # Реферальный код (уникальный!)
    referred_by = Column(String(255))                               # Кто пригласил (ref_code)
    email = Column(String(255))                                     # Email (необязательно)
    phone = Column(String(255))                                     # Телефон (необязательно)
    status = Column(String(50), default='active')                   # Статус (active/blocked)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())  # Дата регистрации

    # Поля онбординга
    onboarding_stage = Column(String(50), default='new_user')       # Текущий этап обучения
    payment_completed = Column(Boolean, default=False)              # Оплатил курс?
    current_course_step = Column(Integer, default=0)                # Номер текущего урока
    course_completed_at = Column(TIMESTAMP(timezone=True))          # Когда завершил курс
    partner_offer_shown_at = Column(TIMESTAMP(timezone=True))       # Когда показали партнерку
    onboarding_completed_at = Column(TIMESTAMP(timezone=True))      # Когда завершил онбординг
    gender = Column(String(20))                                     # Пол (male/female)

    # Временные метки переходов между стадиями (для аналитики)
    stage_new_user_at = Column(TIMESTAMP(timezone=True))
    stage_intro_shown_at = Column(TIMESTAMP(timezone=True))
    stage_wait_payment_at = Column(TIMESTAMP(timezone=True))
    stage_payment_ok_at = Column(TIMESTAMP(timezone=True))
    stage_want_join_at = Column(TIMESTAMP(timezone=True))
    stage_completed_at = Column(TIMESTAMP(timezone=True))


class Click(Base):
    """
    ТАБЛИЦА: clicks

    НАЗНАЧЕНИЕ:
        Хранит все клики (переходы) по реферальным ссылкам

    ОСНОВНЫЕ ПОЛЯ:
        - ref_code: По чьей ссылке перешли
        - user_telegram_id: Кто перешел (Telegram ID)
        - ip_address: IP адрес
        - source: Откуда пришел (telegram/web)

    ИСПОЛЬЗУЕТСЯ:
        - Для подсчета переходов по ссылке
        - Для аналитики эффективности партнеров
    """
    __tablename__ = 'clicks'

    id = Column(Integer, primary_key=True)
    ref_code = Column(String(255), ForeignKey('users.ref_code', ondelete='CASCADE'), nullable=False)  # Чья ссылка
    ip_address = Column(String(50))                         # IP адрес
    user_agent = Column(Text)                               # User Agent браузера
    source = Column(String(255))                            # Источник (telegram/web)
    user_telegram_id = Column(BigInteger)                   # Кто кликнул (Telegram ID)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())  # Когда кликнули


class Sale(Base):
    """
    ТАБЛИЦА: sales

    НАЗНАЧЕНИЕ:
        Хранит все продажи и начисленные комиссии партнерам

    ОСНОВНЫЕ ПОЛЯ:
        - ref_code: Кому начислить комиссию
        - amount: Сумма продажи
        - commission_amount: Сумма комиссии партнера
        - status: Статус (pending/confirmed/cancelled)

    ИСПОЛЬЗУЕТСЯ:
        - Для начисления комиссий партнерам
        - Для статистики заработка
    """
    __tablename__ = 'sales'

    id = Column(Integer, primary_key=True)
    ref_code = Column(String(255), ForeignKey('users.ref_code', ondelete='CASCADE'), nullable=False)  # Кому комиссия
    amount = Column(Float, nullable=False)                  # Сумма продажи
    commission_percent = Column(Float, nullable=False)      # Процент комиссии
    commission_amount = Column(Float, nullable=False)       # Сумма комиссии
    status = Column(String(50), default='pending')          # pending/confirmed/cancelled
    customer_email = Column(String(255))                    # Email покупателя
    product = Column(String(255))                           # Название продукта
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())  # Дата продажи


class Withdrawal(Base):
    """
    ТАБЛИЦА: withdrawals

    НАЗНАЧЕНИЕ:
        Заявки на вывод средств партнерами

    ОСНОВНЫЕ ПОЛЯ:
        - user_id: Кто выводит
        - amount: Сумма вывода
        - method: Способ вывода (карта/paypal и т.д.)
        - status: Статус (pending/completed/rejected)
    """
    __tablename__ = 'withdrawals'

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    amount = Column(Float, nullable=False)                  # Сумма вывода
    method = Column(String(100))                            # Способ (card/paypal/etc)
    requisites = Column(String(255))                        # Реквизиты (номер карты и т.д.)
    status = Column(String(50), default='pending')          # pending/completed/rejected
    comment = Column(Text)                                  # Комментарий админа
    requested_at = Column(TIMESTAMP(timezone=True), server_default=func.now())  # Когда запросил
    processed_at = Column(TIMESTAMP(timezone=True))         # Когда обработали


class CourseVideo(Base):
    """
    ТАБЛИЦА: course_videos

    НАЗНАЧЕНИЕ:
        Хранит информацию о видео-уроках курса

    ОСНОВНЫЕ ПОЛЯ:
        - lesson_number: Номер урока (1, 2, 3...)
        - title: Название урока
        - video_file_id: File ID видео в Telegram
        - is_active: Активен ли урок (можно отключать)
    """
    __tablename__ = 'course_videos'

    id = Column(Integer, primary_key=True)
    lesson_number = Column(Integer, unique=True, nullable=False)    # Номер урока (уникальный)
    title = Column(String(255), nullable=False)             # Название урока
    description = Column(Text)                              # Описание урока
    video_file_id = Column(String(255), nullable=False)     # File ID из Telegram
    duration_seconds = Column(Integer)                      # Длительность в секундах
    is_active = Column(Boolean, default=True)               # Активен ли урок
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())


class UserCourseProgress(Base):
    """
    ТАБЛИЦА: user_course_progress

    НАЗНАЧЕНИЕ:
        Прогресс пользователя по урокам курса

    ОСНОВНЫЕ ПОЛЯ:
        - user_id: ID пользователя
        - lesson_number: Номер урока
        - is_completed: Завершен ли урок
        - watch_time_seconds: Сколько секунд посмотрел
    """
    __tablename__ = 'user_course_progress'

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    lesson_number = Column(Integer, ForeignKey('course_videos.lesson_number', ondelete='CASCADE'), nullable=False)
    started_at = Column(TIMESTAMP(timezone=True), server_default=func.now())    # Когда начал
    completed_at = Column(TIMESTAMP(timezone=True))         # Когда завершил
    is_completed = Column(Boolean, default=False)           # Завершен?
    watch_time_seconds = Column(Integer, default=0)         # Время просмотра


class Payment(Base):
    """
    ТАБЛИЦА: payments

    НАЗНАЧЕНИЕ:
        Платежи пользователей за курс (через Robokassa)

    ОСНОВНЫЕ ПОЛЯ:
        - user_id: Кто платит
        - invoice_id: ID счета (уникальный)
        - amount: Сумма платежа
        - status: Статус (created/pending/paid/failed)
    """
    __tablename__ = 'payments'

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    invoice_id = Column(String(255), unique=True, nullable=False)   # ID счета (уникальный)
    amount = Column(Float, nullable=False)                  # Сумма платежа
    description = Column(String(255))                       # Описание платежа
    status = Column(String(50), default='created')          # created/pending/paid/failed
    robokassa_signature = Column(String(255))               # Подпись Robokassa
    robokassa_out_sum = Column(Float)                       # Сумма от Robokassa
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())    # Создан
    updated_at = Column(TIMESTAMP(timezone=True))           # Обновлен
    paid_at = Column(TIMESTAMP(timezone=True))              # Оплачен
    payment_metadata = Column(Text)                         # Доп. данные (JSON)


class ReferralHistory(Base):
    """
    ТАБЛИЦА: referral_history

    НАЗНАЧЕНИЕ:
        История действий по реферальной программе (для аналитики)

    ОСНОВНЫЕ ПОЛЯ:
        - user_telegram_id: Кто совершил действие
        - ref_code: По чьей ссылке
        - action_type: Тип действия (click/registration/payment)
        - amount: Сумма (для платежей)
    """
    __tablename__ = 'referral_history'

    id = Column(Integer, primary_key=True)
    user_telegram_id = Column(BigInteger, nullable=False)   # Кто
    ref_code = Column(String(255), nullable=False)          # Чья ссылка
    action_type = Column(String(50), nullable=False)        # click/registration/payment
    ip_address = Column(String(50))                         # IP
    user_agent = Column(Text)                               # User Agent
    amount = Column(Float)                                  # Сумма (для payment)
    commission_amount = Column(Float)                       # Комиссия (для payment)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())


class AutomatedMessage(Base):
    """
    ТАБЛИЦА: automated_messages

    НАЗНАЧЕНИЕ:
        Автоматические сообщения (дожимающие видео) для мотивации к покупке

    ОСНОВНЫЕ ПОЛЯ:
        - user_id: Кому отправить
        - video_file_id: File ID видео
        - required_stage: На каком этапе отправить
        - scheduled_at: Когда отправить
        - status: Статус (scheduled/sent/cancelled/failed)

    ЛОГИКА:
        Система автоматически отправляет видео через определенное время,
        если пользователь застрял на одном этапе
    """
    __tablename__ = 'automated_messages'

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    telegram_id = Column(BigInteger, nullable=False)        # Telegram ID для отправки
    video_file_id = Column(String(255), nullable=False)     # File ID видео
    video_type = Column(String(50), nullable=False)         # Тип видео (krug_1, krug_2...)
    required_stage = Column(String(50), nullable=False)     # На каком этапе отправить
    blocked_stages = Column(Text)                           # На каких этапах НЕ отправлять
    scheduled_at = Column(TIMESTAMP(timezone=True), nullable=False)  # Когда отправить
    sent_at = Column(TIMESTAMP(timezone=True))              # Когда отправлено
    status = Column(String(50), default='scheduled')        # scheduled/sent/cancelled/failed
    error_message = Column(Text)                            # Текст ошибки (если failed)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
    updated_at = Column(TIMESTAMP(timezone=True))


class Ticket(Base):
    """
    ТАБЛИЦА: tickets

    НАЗНАЧЕНИЕ:
        Тикеты техподдержки от пользователей

    ОСНОВНЫЕ ПОЛЯ:
        - user_id: Кто создал тикет
        - status: Статус (open/closed)
        - unread_messages: Количество непрочитанных сообщений
        - total_messages: Всего сообщений в тикете
    """
    __tablename__ = 'tickets'

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    telegram_id = Column(BigInteger, nullable=False)        # Telegram ID пользователя
    status = Column(String(50), default='open')             # open/closed
    subject = Column(String(255))                           # Тема обращения
    unread_messages = Column(Integer, default=0)            # Непрочитанных сообщений
    total_messages = Column(Integer, default=0)             # Всего сообщений
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())    # Создан
    updated_at = Column(TIMESTAMP(timezone=True), server_default=func.now())    # Обновлен
    closed_at = Column(TIMESTAMP(timezone=True))            # Закрыт
    last_admin_reply_at = Column(TIMESTAMP(timezone=True))  # Последний ответ админа


class TicketMessage(Base):
    """
    ТАБЛИЦА: ticket_messages

    НАЗНАЧЕНИЕ:
        Сообщения в тикетах (переписка пользователь-админ)

    ОСНОВНЫЕ ПОЛЯ:
        - ticket_id: К какому тикету относится
        - from_user: От пользователя (True) или от админа (False)
        - text: Текст сообщения
        - is_read: Прочитано ли сообщение
    """
    __tablename__ = 'ticket_messages'

    id = Column(Integer, primary_key=True)
    ticket_id = Column(Integer, ForeignKey('tickets.id', ondelete='CASCADE'), nullable=False)
    from_user = Column(Boolean, default=True)               # True - от пользователя, False - от админа
    telegram_message_id = Column(Integer)                   # ID сообщения в Telegram
    text = Column(Text)                                     # Текст сообщения
    media_type = Column(String(50))                         # Тип медиа (photo/video/document)
    media_file_id = Column(String(255))                     # File ID медиа
    is_read = Column(Boolean, default=False)                # Прочитано?
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())  # Создано
