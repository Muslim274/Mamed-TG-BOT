#!/bin/bash

# Конфигурация
PROJECT_DIR="/root/telegram-referral-bot"
BACKUP_DIR="/root/telegram-referral-bot/backups"
DATE=$(date +%A)  # День недели
BACKUP_FILE="$BACKUP_DIR/project_files_${DATE}.tar.gz"

echo "🔄 [$(date)] Создание бэкапа файлов проекта для $DATE..."

# Создаем архив файлов проекта (исключаем ненужное)
tar -czf $BACKUP_FILE \
    --exclude='backups' \
    --exclude='__pycache__' \
    --exclude='.git' \
    --exclude='venv' \
    --exclude='logs' \
    --exclude='*.log' \
    --exclude='*.pyc' \
    --exclude='.env' \
    -C /root telegram-referral-bot

# Проверяем успешность
if [ $? -eq 0 ]; then
    echo "✅ [$(date)] Бэкап файлов создан: $BACKUP_FILE"
    echo "📊 [$(date)] Размер архива: $(du -h $BACKUP_FILE | cut -f1)"
    
    # Показываем содержимое архива (первые 10 файлов)
    echo "📁 [$(date)] Содержимое архива (примеры):"
    tar -tzf $BACKUP_FILE | head -10
    echo "..."
    
    # Показываем все файловые бэкапы
    echo "📋 [$(date)] Файловые бэкапы по дням:"
    ls -lh $BACKUP_DIR/project_files_*.tar.gz 2>/dev/null || echo "Это первый файловый бэкап!"
    
else
    echo "❌ [$(date)] ОШИБКА создания файлового бэкапа!"
    exit 1
fi
