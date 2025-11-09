"""
Миграция базы данных для добавления системы тикетов
app/migrations/add_tickets.py
"""
import asyncio
import logging
from sqlalchemy import text
from app.database.connection import engine

logger = logging.getLogger(__name__)

async def create_tickets_tables():
    """Создание таблиц для системы тикетов"""
    
    # SQL для создания таблицы тикетов
    create_tickets_sql = """
    CREATE TABLE IF NOT EXISTS tickets (
        id SERIAL PRIMARY KEY,
        user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        telegram_id BIGINT NOT NULL,
        status VARCHAR(20) DEFAULT 'open',
        subject VARCHAR(255),
        unread_messages INTEGER DEFAULT 0,
        total_messages INTEGER DEFAULT 0,
        created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
        updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
        closed_at TIMESTAMP WITH TIME ZONE,
        last_admin_reply_at TIMESTAMP WITH TIME ZONE
    );
    """
    
    # SQL для создания таблицы сообщений тикетов
    create_ticket_messages_sql = """
    CREATE TABLE IF NOT EXISTS ticket_messages (
        id SERIAL PRIMARY KEY,
        ticket_id INTEGER NOT NULL REFERENCES tickets(id) ON DELETE CASCADE,
        from_user BOOLEAN DEFAULT TRUE,
        telegram_message_id INTEGER,
        text TEXT,
        media_type VARCHAR(50),
        media_file_id VARCHAR(255),
        is_read BOOLEAN DEFAULT FALSE,
        created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
    );
    """
    
    # Создание индексов
    create_indexes_sql = [
        "CREATE INDEX IF NOT EXISTS idx_tickets_telegram_id ON tickets(telegram_id);",
        "CREATE INDEX IF NOT EXISTS idx_tickets_status ON tickets(status);",
        "CREATE INDEX IF NOT EXISTS idx_tickets_updated_at ON tickets(updated_at);",
        "CREATE INDEX IF NOT EXISTS idx_ticket_messages_ticket_id ON ticket_messages(ticket_id);",
        "CREATE INDEX IF NOT EXISTS idx_ticket_messages_telegram_id ON ticket_messages(telegram_message_id);",
        "CREATE INDEX IF NOT EXISTS idx_ticket_messages_from_user ON ticket_messages(from_user);",
        "CREATE INDEX IF NOT EXISTS idx_ticket_messages_is_read ON ticket_messages(is_read);"
    ]
    
    # Добавление связи в таблицу users (если не существует)
    alter_users_sql = """
    -- Эта связь будет создана автоматически через SQLAlchemy relationship
    -- Но можно добавить комментарий для документации
    COMMENT ON TABLE tickets IS 'Система тикетов поддержки для пользователей';
    """
    
    try:
        async with engine.begin() as conn:
            logger.info("🔧 Creating tickets table...")
            await conn.execute(text(create_tickets_sql))
            
            logger.info("🔧 Creating ticket_messages table...")
            await conn.execute(text(create_ticket_messages_sql))
            
            logger.info("🔧 Creating indexes...")
            for index_sql in create_indexes_sql:
                await conn.execute(text(index_sql))
            
            logger.info("🔧 Adding comments...")
            await conn.execute(text(alter_users_sql))
            
            logger.info("✅ Tickets tables created successfully!")
            
    except Exception as e:
        logger.error(f"❌ Error creating tickets tables: {e}")
        raise

async def migrate_existing_support_data():
    """Миграция существующих данных поддержки (если нужно)"""
    try:
        # Здесь можно добавить логику миграции существующих данных
        # Например, создать тикеты для пользователей, которые уже писали в поддержку
        
        logger.info("📋 Checking for existing support data...")
        
        # Пример: создание тикетов для всех пользователей завершивших онбординг
        async with engine.begin() as conn:
            # Получаем пользователей которые завершили онбординг
            result = await conn.execute(text("""
                SELECT id, telegram_id, username, full_name 
                FROM users 
                WHERE onboarding_stage = 'completed'
                AND NOT EXISTS (
                    SELECT 1 FROM tickets WHERE tickets.telegram_id = users.telegram_id
                )
                LIMIT 100
            """))
            
            users = result.fetchall()
            
            if users:
                logger.info(f"📋 Found {len(users)} users without tickets")
                
                # Создаем базовые тикеты (закрытые) для истории
                for user in users:
                    await conn.execute(text("""
                        INSERT INTO tickets (user_id, telegram_id, status, subject, total_messages, created_at, closed_at)
                        VALUES (:user_id, :telegram_id, 'closed', 'Автоматически созданный тикет', 0, NOW(), NOW())
                    """), {
                        'user_id': user.id,
                        'telegram_id': user.telegram_id
                    })
                
                logger.info(f"✅ Created {len(users)} placeholder tickets")
            else:
                logger.info("ℹ️ No users need placeholder tickets")
        
    except Exception as e:
        logger.error(f"❌ Error migrating support data: {e}")
        # Не критично, продолжаем

async def run_migration():
    """Запуск миграции"""
    logger.info("🚀 Starting tickets migration...")
    
    try:
        await create_tickets_tables()
        await migrate_existing_support_data()
        
        logger.info("🎉 Tickets migration completed successfully!")
        
    except Exception as e:
        logger.error(f"💥 Migration failed: {e}")
        raise

if __name__ == "__main__":
    # Запуск миграции
    asyncio.run(run_migration())