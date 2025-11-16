"""
Миграция для добавления полей автоматической рассылки
"""
from sqlalchemy import text
import asyncio
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))
from app.database.connection import AsyncSessionLocal  # ИСПРАВЛЕНО


async def run_migration():
    """Выполнение миграции"""
    async with AsyncSessionLocal() as session:  # ИСПРАВЛЕНО
        try:
            print("Adding stage timestamp fields to users table...")
            
            await session.execute(text("""
                ALTER TABLE users 
                ADD COLUMN IF NOT EXISTS stage_new_user_at TIMESTAMP WITH TIME ZONE,
                ADD COLUMN IF NOT EXISTS stage_intro_shown_at TIMESTAMP WITH TIME ZONE,
                ADD COLUMN IF NOT EXISTS stage_wait_payment_at TIMESTAMP WITH TIME ZONE,
                ADD COLUMN IF NOT EXISTS stage_payment_ok_at TIMESTAMP WITH TIME ZONE,
                ADD COLUMN IF NOT EXISTS stage_want_join_at TIMESTAMP WITH TIME ZONE,
                ADD COLUMN IF NOT EXISTS stage_completed_at TIMESTAMP WITH TIME ZONE
            """))
            
            print("✓ Stage timestamp fields added")
            
            print("Creating automated_messages table...")
            
            await session.execute(text("""
                CREATE TABLE IF NOT EXISTS automated_messages (
                    id SERIAL PRIMARY KEY,
                    user_id INTEGER NOT NULL REFERENCES users(id),
                    telegram_id BIGINT NOT NULL,
                    video_file_id VARCHAR NOT NULL,
                    video_type VARCHAR NOT NULL,
                    required_stage VARCHAR NOT NULL,
                    blocked_stages TEXT,
                    scheduled_at TIMESTAMP WITH TIME ZONE NOT NULL,
                    sent_at TIMESTAMP WITH TIME ZONE,
                    status VARCHAR NOT NULL DEFAULT 'scheduled',
                    error_message TEXT,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                    updated_at TIMESTAMP WITH TIME ZONE
                )
            """))
            
            print("✓ automated_messages table created")
            
            print("Creating indexes...")
            
            await session.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_automated_messages_telegram_id 
                ON automated_messages(telegram_id)
            """))
            
            await session.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_automated_messages_status_scheduled 
                ON automated_messages(status, scheduled_at)
            """))
            
            await session.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_automated_messages_scheduled_at 
                ON automated_messages(scheduled_at)
            """))
            
            print("✓ Indexes created")
            
            await session.commit()
            print("\n✅ Migration completed successfully!")
            
        except Exception as e:
            await session.rollback()
            print(f"\n❌ Migration failed: {e}")
            raise


if __name__ == "__main__":
    asyncio.run(run_migration())