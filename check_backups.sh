#!/bin/bash

BACKUP_DIR="/root/telegram-referral-bot/backups"

echo "📊 СТАТУС СИСТЕМЫ БЭКАПОВ"
echo "=========================="
echo "🕐 Текущее время: $(date)"
echo "📅 Сегодня: $(date +%A)"
echo ""

# Проверяем бэкапы БД
echo "🗄️  БЭКАПЫ БАЗЫ ДАННЫХ:"
for day in Monday Tuesday Wednesday Thursday Friday Saturday Sunday; do
    file="$BACKUP_DIR/referral_bot_${day}.sql.gz"
    if [ -f "$file" ]; then
        size=$(du -h "$file" | cut -f1)
        date_modified=$(ls -l "$file" | awk '{print $6, $7, $8}')
        echo "   ✅ $day: $size ($date_modified)"
    else
        echo "   ❌ $day: не создан"
    fi
done

echo ""

# Проверяем бэкапы файлов
echo "📁 БЭКАПЫ ФАЙЛОВ ПРОЕКТА:"
for day in Monday Tuesday Wednesday Thursday Friday Saturday Sunday; do
    file="$BACKUP_DIR/project_files_${day}.tar.gz"
    if [ -f "$file" ]; then
        size=$(du -h "$file" | cut -f1)
        date_modified=$(ls -l "$file" | awk '{print $6, $7, $8}')
        echo "   ✅ $day: $size ($date_modified)"
    else
        echo "   ❌ $day: не создан"
    fi
done

echo ""

# Общая статистика
total_size=$(du -sh "$BACKUP_DIR" 2>/dev/null | cut -f1)
file_count=$(ls -1 "$BACKUP_DIR"/*.gz 2>/dev/null | wc -l)
echo "📊 ОБЩАЯ СТАТИСТИКА:"
echo "   💾 Общий размер: $total_size"
echo "   📄 Количество файлов: $file_count"

# Проверяем расписание
echo ""
echo "⏰ РАСПИСАНИЕ CRON:"
crontab -l | grep backup

# Проверяем свободное место
echo ""
echo "💿 СВОБОДНОЕ МЕСТО НА ДИСКЕ:"
df -h / | tail -1 | awk '{print "   Использовано: " $5 " из " $2 " (свободно: " $4 ")"}'
