#!/bin/bash

# Скрипт для запуска анализа конверсий
# Можно добавить в cron для регулярного запуска

# Переходим в директорию проекта
cd /root/telegram-referral-bot

# Активируем виртуальное окружение если есть
if [ -d "venv" ]; then
    source venv/bin/activate
fi

# Запускаем скрипт анализа
echo "🚀 Starting conversion analytics at $(date)"
python3 conversion_analytics.py

# Проверяем код возврата
if [ $? -eq 0 ]; then
    echo "✅ Conversion analytics completed successfully at $(date)"
else
    echo "❌ Conversion analytics failed at $(date)"
    # Можно добавить уведомление админу через telegram
fi

# Для добавления в cron (ежедневный запуск в 00:00):
# 0 0 * * * /root/telegram-referral-bot/run_conversion_analytics.sh >> /root/telegram-referral-bot/cron_conversion.log 2>&1

# Для запуска каждые 6 часов:
# 0 */6 * * * /root/telegram-referral-bot/run_conversion_analytics.sh >> /root/telegram-referral-bot/cron_conversion.log 2>&1

# Для запуска каждый час:
# 0 * * * * /root/telegram-referral-bot/run_conversion_analytics.sh >> /root/telegram-referral-bot/cron_conversion.log 2>&1