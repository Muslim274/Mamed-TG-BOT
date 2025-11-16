"""
Сервис для работы с Google Sheets - обновленная версия
"""
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime
import asyncio
import logging
from typing import Dict, Any
import json
import os

from app.config import settings

logger = logging.getLogger(__name__)


class GoogleSheetsService:
    def __init__(self):
        self.scope = [
            'https://spreadsheets.google.com/feeds',
            'https://www.googleapis.com/auth/drive'
        ]
        self.creds = None
        self.client = None
        self.spreadsheet = None
        self.worksheet = None
        
    async def init(self):
        """Инициализация подключения к Google Sheets"""
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
            
            # Получаем или создаем лист "Оплаты"
            try:
                self.worksheet = self.spreadsheet.worksheet("Оплаты")
                logger.info("✅ Found existing 'Оплаты' worksheet")
            except gspread.WorksheetNotFound:
                logger.info("📝 Creating new 'Оплаты' worksheet")
                self.worksheet = self.spreadsheet.add_worksheet(title="Оплаты", rows="1000", cols="10")
                
                # Добавляем заголовки
                headers = [
                    "Telegram ID",
                    "Username", 
                    "Дата оплаты",
                    "Реферальный код пользователя",
                    "Пригласивший (Telegram ID)",
                    "Количество приглашённых"
                ]
                self.worksheet.append_row(headers)
                logger.info("✅ Headers added to new worksheet")
            
            logger.info(f"✅ Google Sheets initialized: {self.spreadsheet.title}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Error initializing Google Sheets: {e}")
            return False
    
    async def add_payment_record(self, payment_data: Dict[str, Any]):
        """Добавление записи об оплате + ОБНОВЛЕНИЕ реферера"""
        try:
            if not self.worksheet:
                logger.error("❌ Google Sheets not initialized")
                return False
            
            # Считаем сколько людей пригласил ЭТОТ пользователь (на момент регистрации будет 0)
            invited_count = await self.get_user_invites_count(payment_data['telegram_id'])
            
            # Подготавливаем данные для записи
            row_data = [
                payment_data['telegram_id'],
                payment_data['username'],
                payment_data['payment_date'],
                payment_data['user_ref_code'],
                payment_data['invited_by_telegram_id'] or "",
                invited_count  # Для нового пользователя будет 0
            ]
            
            logger.info(f"📊 Adding to Google Sheets: {row_data}")
            
            # Добавляем строку в таблицу
            self.worksheet.append_row(row_data)
            
            # 🆕 ЕСЛИ ЕСТЬ РЕФЕРЕР - ОБНОВЛЯЕМ ЕГО СЧЕТЧИК
            if payment_data['invited_by_telegram_id']:
                await self.update_referrer_invite_count(payment_data['invited_by_telegram_id'])
            
            logger.info(f"✅ Payment record added to Google Sheets: {payment_data['telegram_id']}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Error adding payment record: {e}", exc_info=True)
            return False

    async def update_referrer_invite_count(self, referrer_telegram_id: int):
        """🆕 ОБНОВЛЕНИЕ количества приглашенных у реферера"""
        try:
            logger.info(f"🔄 Updating invite count for referrer {referrer_telegram_id}")
            
            # Получаем все записи
            all_records = self.worksheet.get_all_values()
            
            # Находим строку с рефрером
            referrer_row_index = None
            for i, row in enumerate(all_records):
                if i == 0:  # Пропускаем заголовки
                    continue
                if len(row) > 0 and str(row[0]).strip() == str(referrer_telegram_id):
                    referrer_row_index = i + 1  # +1 потому что индексы в Google Sheets начинаются с 1
                    break
            
            if not referrer_row_index:
                logger.warning(f"⚠️ Referrer {referrer_telegram_id} not found in Google Sheets")
                return
            
            # Считаем НОВОЕ количество приглашенных
            new_invite_count = await self.get_user_invites_count(referrer_telegram_id)
            
            # Обновляем ячейку в столбце F (колонка 6)
            cell_address = f"F{referrer_row_index}"
            self.worksheet.update(cell_address, [[new_invite_count]])
            
            logger.info(f"✅ Updated {cell_address} for referrer {referrer_telegram_id}: {new_invite_count} invites")
            
        except Exception as e:
            logger.error(f"❌ Error updating referrer invite count: {e}", exc_info=True)

    async def get_user_invites_count(self, telegram_id: int) -> int:
        """Подсчет количества приглашенных пользователем"""
        try:
            if not self.worksheet:
                return 0
            
            # Получаем все записи
            records = self.worksheet.get_all_records()
            
            # Считаем сколько людей пригласил ЭТОТ пользователь
            count = 0
            for record in records:
                inviter_id = str(record.get('Пригласивший (Telegram ID)', '')).strip()
                if inviter_id == str(telegram_id):
                    count += 1
            
            logger.info(f"📊 User {telegram_id} has invited {count} people")
            return count
            
        except Exception as e:
            logger.error(f"❌ Error counting invites: {e}")
            return 0

# Глобальный экземпляр сервиса
sheets_service = GoogleSheetsService()


async def init_google_sheets():
    """Инициализация Google Sheets при запуске бота"""
    logger.info("📊 Initializing Google Sheets service...")
    success = await sheets_service.init()
    if success:
        logger.info("✅ Google Sheets service initialized successfully")
    else:
        logger.warning("⚠️ Google Sheets service initialization failed")
    return success


async def add_payment_to_sheets(
    telegram_id: int,
    username: str,
    user_ref_code: str,
    invited_by_telegram_id: int = None
):
    """Добавление записи об оплате в Google Sheets (фоновая задача)"""
    try:
        payment_data = {
            'telegram_id': telegram_id,
            'username': username or f"user_{telegram_id}",
            'payment_date': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            'user_ref_code': user_ref_code,
            'invited_by_telegram_id': invited_by_telegram_id or "",
        }
        
        # Запускаем в фоне, чтобы не блокировать бота
        await sheets_service.add_payment_record(payment_data)
        
    except Exception as e:
        logger.error(f"❌ Error in add_payment_to_sheets: {e}")