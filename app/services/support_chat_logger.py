"""
Сервис для логирования чата поддержки в Google Sheets
app/services/support_chat_logger.py
"""
import logging
from datetime import datetime
import pytz
from typing import Optional
import gspread
from google.oauth2.service_account import Credentials
import os

from app.config import settings

logger = logging.getLogger(__name__)

# Московская временная зона
MSK_TZ = pytz.timezone('Europe/Moscow')


class SupportChatLogger:
    def __init__(self):
        self.scope = [
            'https://spreadsheets.google.com/feeds',
            'https://www.googleapis.com/auth/drive'
        ]
        self.creds = None
        self.client = None
        self.spreadsheet = None
        self.worksheet = None
        self.chat_buffer = {}  # user_id -> list of messages
        
    async def init(self):
        """Инициализация подключения к Google Sheets для листа 'Чат админов'"""
        try:
            # Путь к файлу ключей
            key_file_path = os.path.join(os.getcwd(), settings.GOOGLE_SHEETS_KEY)
            
            if not os.path.exists(key_file_path):
                logger.error(f"❌ Google Sheets key file not found: {key_file_path}")
                return False
            
            # Создаем credentials
            self.creds = Credentials.from_service_account_file(
                key_file_path, 
                scopes=self.scope
            )
            
            # Авторизуемся
            self.client = gspread.authorize(self.creds)
            
            # Открываем таблицу
            self.spreadsheet = self.client.open_by_key(settings.SPREADSHEET_ID)
            
            # Получаем или создаем лист "Чат админов"
            try:
                self.worksheet = self.spreadsheet.worksheet("Чат админов")
                logger.info("✅ Found existing 'Чат админов' worksheet")
                
                # Проверяем наличие заголовков
                first_row = self.worksheet.row_values(1)
                if not first_row or first_row[0] != "Telegram ID":
                    logger.info("📝 Adding headers to existing worksheet")
                    headers = [
                        "Telegram ID",
                        "Дата",
                        "Время обновления",
                        "Пол админа",
                        "Переписка"
                    ]
                    self.worksheet.insert_row(headers, 1)
                    
            except gspread.WorksheetNotFound:
                logger.info("📝 Creating new 'Чат админов' worksheet")
                self.worksheet = self.spreadsheet.add_worksheet(
                    title="Чат админов", 
                    rows="1000", 
                    cols="5"
                )
                
                # Добавляем заголовки
                headers = [
                    "Telegram ID",
                    "Дата",
                    "Время обновления",
                    "Пол админа",
                    "Переписка"
                ]
                self.worksheet.append_row(headers)
                logger.info("✅ Headers added to 'Чат админов' worksheet")
            
            logger.info("✅ Support Chat Logger initialized")
            return True
            
        except Exception as e:
            logger.error(f"❌ Error initializing Support Chat Logger: {e}")
            return False
    
    def add_message_to_buffer(self, user_id: int, sender: str, text: str, gender: str):
        """Добавление сообщения в буфер с временной меткой"""
        if user_id not in self.chat_buffer:
            self.chat_buffer[user_id] = {
                'gender': gender,
                'messages': []
            }
        
        # Получаем текущее время в МСК
        now_msk = datetime.now(MSK_TZ)
        time_str = now_msk.strftime("%H:%M МСК")
        
        # Добавляем сообщение с временной меткой
        self.chat_buffer[user_id]['messages'].append(f"[{time_str}]\n{sender}: {text}")
    
    async def find_user_row(self, user_id: int) -> Optional[int]:
        """Найти строку пользователя в таблице по Telegram ID"""
        try:
            # Получаем все значения из первого столбца (Telegram ID)
            all_values = self.worksheet.col_values(1)
            
            # Ищем строку с нужным user_id (начинаем с индекса 2, т.к. 1 - заголовок)
            for idx, value in enumerate(all_values[1:], start=2):
                if str(value).strip() == str(user_id):
                    logger.info(f"📍 Found existing row {idx} for user {user_id}")
                    return idx
            
            logger.info(f"📍 No existing row found for user {user_id}")
            return None
            
        except Exception as e:
            logger.error(f"❌ Error finding user row: {e}")
            return None
    
    async def save_chat_to_sheets(self, user_id: int, user_name: str, gender: str):
        """Сохранение накопленной переписки в Google Sheets (обновление или создание)"""
        try:
            if not self.worksheet:
                logger.error("❌ Support Chat Logger not initialized")
                return False
            
            # Проверяем есть ли сообщения
            if user_id not in self.chat_buffer or not self.chat_buffer[user_id]['messages']:
                logger.info(f"ℹ️ No messages in buffer for user {user_id}")
                return False
            
            # Получаем текущее время в МСК
            now_msk = datetime.now(MSK_TZ)
            date_str = now_msk.strftime("%d.%m.%Y")
            time_str = now_msk.strftime("%H:%M МСК")
            
            # Форматируем пол
            gender_text = "для мужчин" if gender == 'male' else "для женщин"
            
            # Собираем НОВЫЕ сообщения из буфера
            new_messages = "\n\n".join(self.chat_buffer[user_id]['messages'])
            
            # Ищем существующую строку пользователя
            user_row = await self.find_user_row(user_id)
            
            if user_row:
                # ОБНОВЛЯЕМ существующую строку
                logger.info(f"🔄 Updating existing row {user_row} for user {user_id}")
                
                # Получаем старую переписку из ячейки E (столбец 5)
                old_chat = self.worksheet.cell(user_row, 5).value or ""
                
                # Добавляем новые сообщения к старым
                if old_chat and "Пользователь:" in old_chat:
                    # Если уже есть заголовок "Пользователь:", просто добавляем сообщения
                    updated_chat = f"{old_chat}\n\n{new_messages}"
                else:
                    # Если заголовка нет, добавляем
                    updated_chat = f"Пользователь: {user_name}\n\n{new_messages}"
                
                # Обновляем ячейки (столбцы: B=2, C=3, D=4, E=5)
                self.worksheet.update_cell(user_row, 2, date_str)           # Дата
                self.worksheet.update_cell(user_row, 3, time_str)           # Время обновления
                self.worksheet.update_cell(user_row, 4, gender_text)        # Пол админа
                self.worksheet.update_cell(user_row, 5, updated_chat)       # Переписка
                
                logger.info(f"✅ Updated row {user_row} for user {user_id}")
                
            else:
                # СОЗДАЕМ новую строку
                logger.info(f"➕ Creating new row for user {user_id}")
                
                full_chat = f"Пользователь: {user_name}\n\n{new_messages}"
                
                row_data = [
                    user_id,           # Telegram ID
                    date_str,          # Дата
                    time_str,          # Время обновления
                    gender_text,       # Пол админа
                    full_chat          # Переписка
                ]
                
                self.worksheet.append_row(row_data)
                logger.info(f"✅ Created new row for user {user_id}")
            
            # Очищаем буфер для этого пользователя
            self.chat_buffer[user_id]['messages'].clear()
            
            logger.info(f"✅ Chat saved to Google Sheets for user {user_id}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Error saving chat to sheets: {e}", exc_info=True)
            return False


# Глобальный экземпляр сервиса
support_chat_logger = SupportChatLogger()


async def init_support_chat_logger():
    """Инициализация логгера чата при запуске бота"""
    logger.info("💬 Initializing Support Chat Logger...")
    success = await support_chat_logger.init()
    if success:
        logger.info("✅ Support Chat Logger initialized successfully")
    else:
        logger.warning("⚠️ Support Chat Logger initialization failed")
    return success