#!/bin/bash

# Переходим в директорию проекта
cd /root/telegram-referral-bot

# Запускаем с Python из venv (абсолютный путь)
/root/telegram-referral-bot/venv/bin/python conversion_analytics.py --mode incremental

# Логируем результат
echo "$(date): Analytics executed with exit code $?" >> /root/telegram-referral-bot/execution.log
