#!/bin/bash

echo "=========================================="
echo "Ручной запуск бота (без systemd)"
echo "=========================================="

cd /root/bot_deploy

# Проверяем виртуальное окружение
if [ ! -d "venv" ]; then
    echo "ERROR: Virtual environment not found!"
    echo "Run install.sh first:"
    echo "  ./install.sh"
    exit 1
fi

# Активируем виртуальное окружение
source venv/bin/activate

echo "Starting bot..."
echo "Press Ctrl+C to stop"
echo ""

# Запускаем бота
python -m app.bot
