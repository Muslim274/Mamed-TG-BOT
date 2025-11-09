#!/bin/bash

# Конфигурация
DB_NAME="referral_bot"
DB_USER="postgres"
DB_HOST="localhost"
DB_PORT="5432"
BACKUP_DIR="/root/telegram-referral-bot/backups"
DATE=$(date +%A)  # Используем день недели (Monday, Tuesday, etc.)
BACKUP_FILE="$BACKUP_DIR/${DB_NAME}_${DATE}.sql"

# Создаем директорию если не существует
mkdir -p $BACKUP_DIR

echo "🔄 [$(date)] Создание бэкапа базы данных $DB_NAME для $DATE..."

# Создаем дамп
PGPASSWORD="SKQZn5C" pg_dump -h $DB_HOST -p $DB_PORT -U $DB_USER -d $DB_NAME > $BACKUP_FILE

# Проверяем успешность
if [ $? -eq 0 ]; then
    echo "✅ [$(date)] Бэкап создан: $BACKUP_FILE"
    
    # Сжимаем файл (перезаписываем существующий)
    gzip -f $BACKUP_FILE
    echo "📦 [$(date)] Бэкап сжат: ${BACKUP_FILE}.gz"
    
    # Показываем размер
    echo "📊 [$(date)] Размер бэкапа: $(du -h ${BACKUP_FILE}.gz | cut -f1)"
    
    # Показываем все бэкапы по дням недели
    echo "📋 [$(date)] Текущие бэкапы по дням:"
    ls -lh $BACKUP_DIR/${DB_NAME}_*.sql.gz 2>/dev/null || echo "Это первый бэкап!"
    
else
    echo "❌ [$(date)] ОШИБКА создания бэкапа!"
    exit 1
fi
