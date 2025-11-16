# Инструкция по развертыванию бота на Ubuntu Server

## 1. Подготовка файлов на локальной машине

Убедитесь что файл `.env` настроен правильно с вашими данными:
- BOT_TOKEN
- DATABASE_URL (или SSH_TUNNEL настройки)
- ADMIN_ID
- и другие параметры

## 2. Перенос файлов через WinSCP

### Файлы и папки которые НУЖНО перенести:
```
/root/bot_deploy/
├── app/                    # Вся папка с кодом
├── migrations/             # Миграции БД
├── requirements.txt        # Зависимости Python
├── .env                    # Файл с настройками (ВАЖНО!)
├── bot.service            # Systemd service
└── install.sh             # Скрипт установки
```

### Файлы которые НЕ нужно переносить:
- __pycache__/
- venv/
- *.log файлы
- *.db файлы (если есть локальная БД)
- test_*.py

## 3. Подключение к серверу через WinSCP

1. Откройте WinSCP
2. Создайте новое подключение:
   - Протокол: SFTP
   - Хост: [IP вашего сервера]
   - Порт: 22
   - Имя пользователя: root
   - Пароль: [ваш пароль]

3. Перенесите все файлы в `/root/bot_deploy/`

## 4. Установка на сервере

Подключитесь к серверу через SSH или используйте консоль WinSCP:

```bash
# Перейти в папку с ботом
cd /root/bot_deploy

# Дать права на выполнение скрипту
chmod +x install.sh

# Запустить установку
./install.sh
```

## 5. Запуск бота

```bash
# Запустить бота
systemctl start bot

# Проверить статус
systemctl status bot

# Посмотреть логи
tail -f /root/bot_deploy/bot.log
```

## 6. Управление ботом

```bash
# Остановить бота
systemctl stop bot

# Перезапустить бота
systemctl restart bot

# Посмотреть логи ошибок
tail -f /root/bot_deploy/bot_error.log

# Отключить автозапуск
systemctl disable bot

# Включить автозапуск
systemctl enable bot
```

## 7. Обновление бота

Когда нужно обновить код:

```bash
# Остановить бота
systemctl stop bot

# Обновить файлы через WinSCP

# Если изменились зависимости
cd /root/bot_deploy
source venv/bin/activate
pip install -r requirements.txt

# Запустить бота
systemctl start bot
```

## 8. Проверка работы

1. Проверьте статус: `systemctl status bot`
2. Посмотрите логи: `tail -100 /root/bot_deploy/bot.log`
3. Напишите боту в Telegram

## Решение проблем

### Бот не запускается:
```bash
# Посмотрите ошибки
journalctl -u bot -n 50

# Или в логах
tail -100 /root/bot_deploy/bot_error.log
```

### Проблемы с SSH туннелем к БД:
Убедитесь что в `.env` правильно настроены:
```
SSH_TUNNEL_ENABLED=True
SSH_HOST=62.217.181.207
SSH_PORT=22
SSH_USERNAME=root
SSH_PASSWORD=vqGB!SKQZn5C
```

### Проблемы с правами:
```bash
# Дать права на файлы
chmod -R 755 /root/bot_deploy
chown -R root:root /root/bot_deploy
```
