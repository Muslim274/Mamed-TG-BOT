"""
Скрипт миграции базы данных для изменения типа telegram_id
"""
import asyncio
import asyncpg
from app.config import settings

async def migrate_database():
    """Миграция базы данных для поддержки больших Telegram ID"""
    print("🔄 Запуск миграции базы данных...")
    
    # Получаем URL подключения к PostgreSQL
    db_url = settings.DATABASE_URL.replace('postgresql://', 'postgresql://')
    
    try:
        # Подключаемся к базе данных
        conn = await asyncpg.connect(db_url)
        
        print("✅ Подключение к базе данных установлено")
        
        # Проверяем текущий тип столбца
        type_info = await conn.fetchrow("""
            SELECT data_type 
            FROM information_schema.columns 
            WHERE table_name = 'users' AND column_name = 'telegram_id'
        """)
        
        if type_info:
            current_type = type_info['data_type']
            print(f"📋 Текущий тип telegram_id: {current_type}")
            
            if current_type == 'integer':
                print("🔧 Изменение типа с integer на bigint...")
                
                # Изменяем тип столбца
                await conn.execute("""
                    ALTER TABLE users 
                    ALTER COLUMN telegram_id TYPE BIGINT;
                """)
                
                print("✅ Тип столбца telegram_id изменен на BIGINT")
            else:
                print("✅ Столбец telegram_id уже имеет правильный тип")
        else:
            print("❌ Таблица users или столбец telegram_id не найдены")
        
        # Закрываем соединение
        await conn.close()
        print("✅ Миграция завершена успешно")
        
    except Exception as e:
        print(f"❌ Ошибка миграции: {e}")
        raise

if __name__ == "__main__":
    asyncio.run(migrate_database())