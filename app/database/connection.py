"""
Подключение к базе данных PostgreSQL через psycopg2 и SQLAlchemy
С поддержкой SSH туннеля
"""
import psycopg2
from psycopg2.extras import RealDictCursor
import logging
from contextlib import contextmanager
from typing import Generator, Optional

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base

from app.config import settings

logger = logging.getLogger(__name__)

# SSH Tunnel support
_ssh_tunnel: Optional['SSHTunnelForwarder'] = None

def get_ssh_tunnel():
    """Получение или создание SSH туннеля"""
    global _ssh_tunnel

    if not settings.SSH_TUNNEL_ENABLED:
        return None

    if _ssh_tunnel is not None and _ssh_tunnel.is_active:
        return _ssh_tunnel

    try:
        from sshtunnel import SSHTunnelForwarder

        logger.info(f"🔗 Creating SSH tunnel to {settings.SSH_HOST}:{settings.SSH_PORT}")

        _ssh_tunnel = SSHTunnelForwarder(
            (settings.SSH_HOST, settings.SSH_PORT),
            ssh_username=settings.SSH_USERNAME,
            ssh_password=settings.SSH_PASSWORD,
            remote_bind_address=('127.0.0.1', 5432)
        )

        _ssh_tunnel.start()
        logger.info(f"✅ SSH tunnel started on local port: {_ssh_tunnel.local_bind_port}")

        return _ssh_tunnel

    except Exception as e:
        logger.error(f"❌ Failed to create SSH tunnel: {e}")
        raise

def stop_ssh_tunnel():
    """Остановка SSH туннеля"""
    global _ssh_tunnel
    if _ssh_tunnel is not None and _ssh_tunnel.is_active:
        _ssh_tunnel.stop()
        logger.info("🚪 SSH tunnel stopped")
        _ssh_tunnel = None

# SQLAlchemy Base
Base = declarative_base()

# Глобальные переменные для движков (будут инициализированы позже)
async_engine = None
AsyncSessionLocal = None

def init_engines():
    """Инициализация движков БД с учетом SSH туннеля"""
    global async_engine, AsyncSessionLocal

    # Запускаем SSH туннель если нужно
    tunnel = get_ssh_tunnel()

    # Формируем URL для подключения
    if tunnel and settings.SSH_TUNNEL_ENABLED:
        # Подключаемся через локальный порт туннеля
        db_url = f"postgresql://postgres:SKQZn5C@127.0.0.1:{tunnel.local_bind_port}/referral_bot"
        logger.info(f"🔗 Using SSH tunnel connection: localhost:{tunnel.local_bind_port}")
    else:
        db_url = settings.DATABASE_URL
        logger.info(f"🔗 Using direct connection")

    # Создаем асинхронный движок
    async_engine = create_async_engine(
        db_url.replace('postgresql://', 'postgresql+asyncpg://'),
        echo=False,
        pool_pre_ping=True,
        pool_size=10,
        max_overflow=20
    )

    # Фабрика асинхронных сессий
    AsyncSessionLocal = async_sessionmaker(
        async_engine,
        class_=AsyncSession,
        expire_on_commit=False
    )

    logger.info("✅ Database engines initialized")

# Инициализируем движки при импорте (если туннель нужен, он будет создан)
try:
    init_engines()
except Exception as e:
    logger.warning(f"⚠️ Failed to initialize engines on import: {e}")


def parse_database_url(database_url: str) -> dict:
    """
    Парсинг DATABASE_URL в параметры подключения

    Формат: postgresql://user:password@host:port/database
    """
    try:
        # Убираем префикс postgresql://
        if database_url.startswith('postgresql://'):
            database_url = database_url.replace('postgresql://', '')
        elif database_url.startswith('postgresql+asyncpg://'):
            database_url = database_url.replace('postgresql+asyncpg://', '')

        # Разбираем строку подключения
        # user:password@host:port/database
        auth_part, location_part = database_url.split('@')
        user, password = auth_part.split(':')
        host_port, database = location_part.split('/')

        if ':' in host_port:
            host, port = host_port.split(':')
        else:
            host = host_port
            port = '5432'

        return {
            'host': host,
            'port': int(port),
            'database': database,
            'user': user,
            'password': password
        }
    except Exception as e:
        logger.error(f"Ошибка парсинга DATABASE_URL: {e}")
        raise


def get_db_params() -> dict:
    """Получение параметров подключения с учетом SSH туннеля"""
    tunnel = get_ssh_tunnel()

    if tunnel and settings.SSH_TUNNEL_ENABLED:
        # Используем локальный порт туннеля
        return {
            'host': '127.0.0.1',
            'port': tunnel.local_bind_port,
            'database': 'referral_bot',
            'user': 'postgres',
            'password': 'SKQZn5C'
        }
    else:
        # Используем стандартные параметры из DATABASE_URL
        return parse_database_url(settings.DATABASE_URL)


def get_connection():
    """
    Создание подключения к PostgreSQL

    Использование:
        conn = get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM users")
            result = cursor.fetchall()
        finally:
            conn.close()

    Returns:
        psycopg2.connection: Подключение к БД
    """
    try:
        db_params = get_db_params()
        conn = psycopg2.connect(
            host=db_params['host'],
            port=db_params['port'],
            database=db_params['database'],
            user=db_params['user'],
            password=db_params['password']
        )
        return conn
    except Exception as e:
        logger.error(f"Ошибка подключения к PostgreSQL: {e}")
        raise


def get_dict_connection():
    """
    Создание подключения к PostgreSQL с RealDictCursor
    (результаты запросов возвращаются как словари)

    Returns:
        psycopg2.connection: Подключение к БД с RealDictCursor
    """
    try:
        db_params = get_db_params()
        conn = psycopg2.connect(
            host=db_params['host'],
            port=db_params['port'],
            database=db_params['database'],
            user=db_params['user'],
            password=db_params['password'],
            cursor_factory=RealDictCursor
        )
        return conn
    except Exception as e:
        logger.error(f"Ошибка подключения к PostgreSQL: {e}")
        raise


@contextmanager
def get_db_connection() -> Generator:
    """
    Context manager для автоматического управления подключением

    Использование:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM users")
            result = cursor.fetchall()

    Yields:
        psycopg2.connection: Подключение к БД
    """
    conn = None
    try:
        conn = get_connection()
        yield conn
        conn.commit()  # Автоматический commit при успехе
    except Exception as e:
        if conn:
            conn.rollback()  # Автоматический rollback при ошибке
        logger.error(f"Ошибка в транзакции БД: {e}")
        raise
    finally:
        if conn:
            conn.close()


@contextmanager
def get_db_dict_connection() -> Generator:
    """
    Context manager для автоматического управления подключением с RealDictCursor

    Использование:
        with get_db_dict_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM users WHERE id = %s", (user_id,))
            user = cursor.fetchone()
            # user будет словарем: {'id': 1, 'name': 'John', ...}

    Yields:
        psycopg2.connection: Подключение к БД с RealDictCursor
    """
    conn = None
    try:
        conn = get_dict_connection()
        yield conn
        conn.commit()
    except Exception as e:
        if conn:
            conn.rollback()
        logger.error(f"Ошибка в транзакции БД: {e}")
        raise
    finally:
        if conn:
            conn.close()


def init_db():
    """
    Инициализация базы данных - создание таблиц

    Запускается при старте бота для создания всех необходимых таблиц
    """
    logger.info("Инициализация базы данных...")

    with get_db_connection() as conn:
        cursor = conn.cursor()

        # Создаем таблицу users
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                telegram_id BIGINT UNIQUE NOT NULL,
                username VARCHAR(255),
                full_name VARCHAR(255) NOT NULL,
                ref_code VARCHAR(255) UNIQUE NOT NULL,
                referred_by VARCHAR(255),
                email VARCHAR(255),
                phone VARCHAR(255),
                status VARCHAR(50) DEFAULT 'active',
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,

                -- Onboarding поля
                onboarding_stage VARCHAR(50) DEFAULT 'new_user',
                payment_completed BOOLEAN DEFAULT FALSE,
                current_course_step INTEGER DEFAULT 0,
                course_completed_at TIMESTAMP WITH TIME ZONE,
                partner_offer_shown_at TIMESTAMP WITH TIME ZONE,
                onboarding_completed_at TIMESTAMP WITH TIME ZONE,
                gender VARCHAR(20),

                -- Временные метки переходов между стадиями
                stage_new_user_at TIMESTAMP WITH TIME ZONE,
                stage_intro_shown_at TIMESTAMP WITH TIME ZONE,
                stage_wait_payment_at TIMESTAMP WITH TIME ZONE,
                stage_payment_ok_at TIMESTAMP WITH TIME ZONE,
                stage_want_join_at TIMESTAMP WITH TIME ZONE,
                stage_completed_at TIMESTAMP WITH TIME ZONE
            );
        """)

        # Создаем индексы для users
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_users_telegram_id ON users(telegram_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_users_ref_code ON users(ref_code);")

        # Создаем таблицу clicks
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS clicks (
                id SERIAL PRIMARY KEY,
                ref_code VARCHAR(255) NOT NULL,
                ip_address VARCHAR(50),
                user_agent TEXT,
                source VARCHAR(255),
                user_telegram_id BIGINT,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (ref_code) REFERENCES users(ref_code) ON DELETE CASCADE
            );
        """)

        cursor.execute("CREATE INDEX IF NOT EXISTS idx_clicks_ref_code ON clicks(ref_code);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_clicks_user_telegram_id ON clicks(user_telegram_id);")

        # Создаем таблицу sales
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS sales (
                id SERIAL PRIMARY KEY,
                ref_code VARCHAR(255) NOT NULL,
                amount FLOAT NOT NULL,
                commission_percent FLOAT NOT NULL,
                commission_amount FLOAT NOT NULL,
                status VARCHAR(50) DEFAULT 'pending',
                customer_email VARCHAR(255),
                product VARCHAR(255),
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (ref_code) REFERENCES users(ref_code) ON DELETE CASCADE
            );
        """)

        cursor.execute("CREATE INDEX IF NOT EXISTS idx_sales_ref_code ON sales(ref_code);")

        # Создаем таблицу withdrawals
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS withdrawals (
                id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL,
                amount FLOAT NOT NULL,
                method VARCHAR(100),
                requisites VARCHAR(255),
                status VARCHAR(50) DEFAULT 'pending',
                comment TEXT,
                requested_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                processed_at TIMESTAMP WITH TIME ZONE,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            );
        """)

        # Создаем таблицу course_videos
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS course_videos (
                id SERIAL PRIMARY KEY,
                lesson_number INTEGER UNIQUE NOT NULL,
                title VARCHAR(255) NOT NULL,
                description TEXT,
                video_file_id VARCHAR(255) NOT NULL,
                duration_seconds INTEGER,
                is_active BOOLEAN DEFAULT TRUE,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
            );
        """)

        # Создаем таблицу user_course_progress
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS user_course_progress (
                id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL,
                lesson_number INTEGER NOT NULL,
                started_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                completed_at TIMESTAMP WITH TIME ZONE,
                is_completed BOOLEAN DEFAULT FALSE,
                watch_time_seconds INTEGER DEFAULT 0,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                FOREIGN KEY (lesson_number) REFERENCES course_videos(lesson_number) ON DELETE CASCADE
            );
        """)

        # Создаем таблицу payments
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS payments (
                id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL,
                invoice_id VARCHAR(255) UNIQUE NOT NULL,
                amount FLOAT NOT NULL,
                description VARCHAR(255),
                status VARCHAR(50) DEFAULT 'created',
                robokassa_signature VARCHAR(255),
                robokassa_out_sum FLOAT,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP WITH TIME ZONE,
                paid_at TIMESTAMP WITH TIME ZONE,
                payment_metadata TEXT,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            );
        """)

        cursor.execute("CREATE INDEX IF NOT EXISTS idx_payments_invoice_id ON payments(invoice_id);")

        # Создаем таблицу tickets
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS tickets (
                id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL,
                telegram_id BIGINT NOT NULL,
                status VARCHAR(50) DEFAULT 'open',
                subject VARCHAR(255),
                unread_messages INTEGER DEFAULT 0,
                total_messages INTEGER DEFAULT 0,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                closed_at TIMESTAMP WITH TIME ZONE,
                last_admin_reply_at TIMESTAMP WITH TIME ZONE,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            );
        """)

        cursor.execute("CREATE INDEX IF NOT EXISTS idx_tickets_telegram_id ON tickets(telegram_id);")

        # Создаем таблицу ticket_messages
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS ticket_messages (
                id SERIAL PRIMARY KEY,
                ticket_id INTEGER NOT NULL,
                from_user BOOLEAN DEFAULT TRUE,
                telegram_message_id INTEGER,
                text TEXT,
                media_type VARCHAR(50),
                media_file_id VARCHAR(255),
                is_read BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (ticket_id) REFERENCES tickets(id) ON DELETE CASCADE
            );
        """)

        # Создаем таблицу referral_history
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS referral_history (
                id SERIAL PRIMARY KEY,
                user_telegram_id BIGINT NOT NULL,
                ref_code VARCHAR(255) NOT NULL,
                action_type VARCHAR(50) NOT NULL,
                ip_address VARCHAR(50),
                user_agent TEXT,
                amount FLOAT,
                commission_amount FLOAT,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
            );
        """)

        cursor.execute("CREATE INDEX IF NOT EXISTS idx_referral_history_user_created ON referral_history(user_telegram_id, created_at);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_referral_history_ref_code ON referral_history(ref_code);")

        # Создаем таблицу automated_messages
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS automated_messages (
                id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL,
                telegram_id BIGINT NOT NULL,
                video_file_id VARCHAR(255) NOT NULL,
                video_type VARCHAR(50) NOT NULL,
                required_stage VARCHAR(50) NOT NULL,
                blocked_stages TEXT,
                scheduled_at TIMESTAMP WITH TIME ZONE NOT NULL,
                sent_at TIMESTAMP WITH TIME ZONE,
                status VARCHAR(50) DEFAULT 'scheduled',
                error_message TEXT,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP WITH TIME ZONE,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            );
        """)

        cursor.execute("CREATE INDEX IF NOT EXISTS idx_automated_messages_telegram_id ON automated_messages(telegram_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_automated_messages_scheduled_at ON automated_messages(scheduled_at);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_automated_messages_status ON automated_messages(status);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_automated_messages_status_scheduled ON automated_messages(status, scheduled_at);")

        logger.info("✅ База данных успешно инициализирована!")


def test_connection():
    """
    Тестирование подключения к базе данных

    Returns:
        bool: True если подключение успешно, False иначе
    """
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT 1")
            result = cursor.fetchone()
            logger.info(f"✅ Подключение к PostgreSQL успешно! Результат теста: {result}")
            return True
    except Exception as e:
        logger.error(f"❌ Ошибка подключения к PostgreSQL: {e}")
        return False
