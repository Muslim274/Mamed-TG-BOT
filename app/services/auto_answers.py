"""
Сервис для работы с автоответами из Google Sheets
app/services/auto_answers.py
"""
import logging
import os
from typing import List, Dict, Optional
import gspread
from google.oauth2.service_account import Credentials

from app.config import settings
from app.database.models import OnboardingStage

logger = logging.getLogger(__name__)


class AutoAnswersService:
    """Сервис для получения автоответов из Google Sheets"""
    
    # Стадии для неоплативших пользователей (ТОЛЬКО эти две!)
    NON_PAID_STAGES = [
        OnboardingStage.NEW_USER,
        OnboardingStage.INTRO_SHOWN
    ]
    
    def __init__(self):
        self.scope = [
            'https://spreadsheets.google.com/feeds',
            'https://www.googleapis.com/auth/drive'
        ]
        self.creds = None
        self.client = None
        self.spreadsheet = None
        self.non_paid_worksheet = None
        self.partners_worksheet = None
        
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
            
            # Получаем листы с автоответами
            try:
                self.non_paid_worksheet = self.spreadsheet.worksheet("Автоответы_Не_оплатил")
                logger.info("✅ Found 'Автоответы_Не_оплатил' worksheet")
            except gspread.WorksheetNotFound:
                logger.error("❌ 'Автоответы_Не_оплатил' worksheet not found")
                return False
            
            try:
                self.partners_worksheet = self.spreadsheet.worksheet("Автоответы_Партнеры")
                logger.info("✅ Found 'Автоответы_Партнеры' worksheet")
            except gspread.WorksheetNotFound:
                logger.error("❌ 'Автоответы_Партнеры' worksheet not found")
                return False
            
            logger.info("✅ Auto Answers Service initialized")
            return True
            
        except Exception as e:
            logger.error(f"❌ Error initializing Auto Answers Service: {e}")
            return False
    
    def _get_qa_pairs_from_sheet(self, worksheet) -> List[Dict[str, str]]:
        """
        Получает пары вопрос-ответ из листа
        
        Args:
            worksheet: Лист Google Sheets
            
        Returns:
            Список словарей с ключами 'question' и 'answer'
        """
        try:
            # Получаем все значения листа
            all_values = worksheet.get_all_values()
            
            if not all_values or len(all_values) < 2:
                logger.warning("⚠️ Worksheet is empty or has no data rows")
                return []
            
            qa_pairs = []
            
            # Пропускаем заголовок (первую строку) и читаем данные
            for row in all_values[1:]:
                if len(row) >= 2:
                    question = row[0].strip()  # Столбец A
                    answer = row[1].strip()    # Столбец B
                    
                    # Пропускаем пустые строки
                    if question and answer:
                        qa_pairs.append({
                            'question': question,
                            'answer': answer
                        })
            
            logger.info(f"📋 Loaded {len(qa_pairs)} Q&A pairs from worksheet")
            return qa_pairs
            
        except Exception as e:
            logger.error(f"❌ Error reading Q&A pairs: {e}", exc_info=True)
            return []
    
    async def get_qa_pairs_for_stage(self, stage: str) -> List[Dict[str, str]]:
        """
        Получает пары вопрос-ответ в зависимости от стадии пользователя
        
        Args:
            stage: Стадия пользователя (из OnboardingStage)
            
        Returns:
            Список пар вопрос-ответ
        """
        try:
            # Определяем какой лист использовать
            if stage in self.NON_PAID_STAGES:
                worksheet = self.non_paid_worksheet
                logger.info(f"📄 Using 'Автоответы_Не_оплатил' for stage {stage}")
            else:
                worksheet = self.partners_worksheet
                logger.info(f"📄 Using 'Автоответы_Партнеры' for stage {stage}")
            
            return self._get_qa_pairs_from_sheet(worksheet)
            
        except Exception as e:
            logger.error(f"❌ Error getting Q&A pairs for stage {stage}: {e}")
            return []
    
    async def reload_answers(self):
        """Перезагрузка данных из Google Sheets (для обновления)"""
        logger.info("🔄 Reloading auto answers from Google Sheets...")
        return await self.init()


# Глобальный экземпляр
auto_answers_service = AutoAnswersService()


async def init_auto_answers_service():
    """Инициализация сервиса автоответов при запуске бота"""
    logger.info("💬 Initializing Auto Answers Service...")
    success = await auto_answers_service.init()
    if success:
        logger.info("✅ Auto Answers Service initialized successfully")
    else:
        logger.warning("⚠️ Auto Answers Service initialization failed")
    return success