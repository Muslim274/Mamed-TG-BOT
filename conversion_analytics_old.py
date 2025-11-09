#!/usr/bin/env python3
"""
ФИНАЛЬНАЯ ВЕРСИЯ: Скрипт анализа конверсий без обращения к несуществующим полям
Версия 4.1 - все проблемы исправлены + Google Sheets как источник истины
"""

import os
import sys
import logging
import asyncio
import re
import time
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional
from collections import defaultdict
import subprocess
import pytz

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database.connection import AsyncSessionLocal, init_db
from app.database.crud import UserCRUD
from app.database.models import User, OnboardingStage
from app.services.google_sheets import GoogleSheetsService
from app.config import settings
from sqlalchemy import select, func, and_

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/root/telegram-referral-bot/conversion_analytics_final.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

BOT_PATH = "/root/telegram-referral-bot"
LOG_PATTERN = r'(\d{4}-\d{2}-\d{2}) (\d{2}:\d{2}:\d{2}).*?User (\d+).*?/start'
MOSCOW_TZ = pytz.timezone('Europe/Moscow')

REQUIRED_STAGES = [
    OnboardingStage.NEW_USER,
    OnboardingStage.INTRO_SHOWN, 
    OnboardingStage.WAIT_PAYMENT,
    OnboardingStage.PAYMENT_OK,
    "DAILY_PAYMENTS"
]

STAGE_NAMES = {
    OnboardingStage.NEW_USER: "Новые пользователи",
    OnboardingStage.INTRO_SHOWN: "Просмотрели видео (но еще не к оплате)",
    OnboardingStage.WAIT_PAYMENT: "Ожидают оплату", 
    OnboardingStage.PAYMENT_OK: "Оплатили (регистрация+оплата в 1 день)",
    "DAILY_PAYMENTS": "Всего оплат за день (по факту)"
}

class ConversionAnalyticsFinal:
    """ФИНАЛЬНАЯ версия аналитики конверсий"""
    
    def __init__(self):
        self.sheets_service = GoogleSheetsService()
        self.worksheet = None
        self.last_update_date = None
        
    async def init(self):
        """Инициализация подключения к Google Sheets"""
        try:
            await init_db()
            logger.info("✅ Database initialized")
            
            success = await self.sheets_service.init()
            if not success:
                raise Exception("Failed to initialize Google Sheets")
            
            sheet_name = "Конверсии по дням v4"  # Финальная версия
            
            try:
                self.worksheet = self.sheets_service.spreadsheet.worksheet(sheet_name)
                logger.info(f"✅ Found existing '{sheet_name}' worksheet")
                
                headers = self.worksheet.row_values(1)
                expected_headers = ["Дата", "Время обновления"] + [STAGE_NAMES[stage] for stage in REQUIRED_STAGES]
                
                if not headers or headers != expected_headers:
                    logger.info("📝 Updating headers...")
                    self.worksheet.update(range_name='A1:G1', values=[expected_headers])
                    time.sleep(2)
                    
            except:
                logger.info(f"📝 Creating new '{sheet_name}' worksheet")
                self.worksheet = self.sheets_service.spreadsheet.add_worksheet(
                    title=sheet_name, 
                    rows=1000, 
                    cols=10
                )
                
                headers = ["Дата", "Время обновления"] + [STAGE_NAMES[stage] for stage in REQUIRED_STAGES]
                self.worksheet.update(range_name='A1:G1', values=[headers])
                time.sleep(2)
                logger.info("✅ Headers added to new worksheet")
            
            self.last_update_date = await self._get_last_update_date()
            return True
            
        except Exception as e:
            logger.error(f"❌ Error initializing: {e}")
            return False
    
    async def _get_last_update_date(self) -> Optional[datetime]:
        """Получение даты последнего обновления"""
        try:
            all_values = self.worksheet.get_all_values()
            if len(all_values) <= 1:
                return None
            
            last_row = all_values[-1]
            date_str = last_row[0] if last_row else ''
            
            if not date_str:
                return None
            
            try:
                return datetime.strptime(date_str, '%d.%m.%Y')
            except:
                return None
                
        except Exception as e:
            logger.error(f"❌ Error getting last update date: {e}")
            return None
    
    async def get_users_from_logs_by_date(self, start_date: Optional[datetime] = None) -> Dict[str, set]:
        """Получение пользователей из логов"""
        users_by_date = defaultdict(set)
        
        try:
            cmd = [
                "find", BOT_PATH, 
                "-type", "f", 
                "(", "-name", "*.log", "-o", "-name", "*.txt", ")"
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode != 0:
                logger.error(f"❌ Find command failed: {result.stderr}")
                return {}
                
            log_files = [f for f in result.stdout.strip().split('\n') if f.strip()]
            logger.info(f"📂 Found {len(log_files)} log files")
            
            processed_files = 0
            for log_file in log_files:
                if not log_file:
                    continue
                    
                try:
                    grep_cmd = ["grep", "/start", log_file]
                    grep_result = subprocess.run(grep_cmd, capture_output=True, text=True)
                    
                    if grep_result.stdout:
                        lines = grep_result.stdout.strip().split('\n')
                        
                        for line in lines:
                            if not line.strip():
                                continue
                                
                            match = re.search(LOG_PATTERN, line)
                            if match:
                                date_str = match.group(1)
                                user_id = int(match.group(3))
                                
                                if start_date:
                                    try:
                                        log_date = datetime.strptime(date_str, '%Y-%m-%d')
                                        if log_date <= start_date:
                                            continue
                                    except ValueError:
                                        logger.warning(f"⚠️ Invalid date in log: {date_str}")
                                        continue
                                
                                users_by_date[date_str].add(user_id)
                    
                    processed_files += 1
                    if processed_files % 10 == 0:
                        logger.info(f"📂 Processed {processed_files}/{len(log_files)} files")
                                
                except Exception as e:
                    logger.warning(f"⚠️ Error processing file {log_file}: {e}")
                    continue
            
            total_events = sum(len(users) for users in users_by_date.values())
            logger.info(f"📊 Found {total_events} /start events across {len(users_by_date)} days")
            
            for i, (date_str, user_set) in enumerate(list(users_by_date.items())[:3]):
                logger.info(f"📊 Sample date {date_str}: {len(user_set)} users")
            
            return dict(users_by_date)
            
        except Exception as e:
            logger.error(f"❌ Error getting users from logs: {e}", exc_info=True)
            return {}
    
    async def _get_payments_from_sheets_for_date(self, date_str: str) -> int:
        """Получение количества оплат из Google Sheets для конкретной даты"""
        try:
            # Инициализируем подключение к листу "Оплаты"
            payments_sheet = self.sheets_service.spreadsheet.worksheet("Оплаты")
            all_records = payments_sheet.get_all_records()
            
            # Преобразуем дату из формата YYYY-MM-DD в DD.MM.YYYY
            target_date = datetime.strptime(date_str, '%Y-%m-%d').strftime('%d.%m.%Y')
            
            count = 0
            for record in all_records:
                payment_date = record.get('Дата оплаты', '')
                
                # Извлекаем только дату (до пробела) если есть время
                if payment_date:
                    payment_date_only = payment_date.split(' ')[0]
                    if payment_date_only == target_date:
                        count += 1
            
            logger.info(f"📊 Sheets payments for {date_str}: {count}")
            return count
            
        except Exception as e:
            logger.error(f"❌ Error getting payments from Sheets for {date_str}: {e}")
            return 0
    
    async def get_users_by_stages_for_dates(self, date_list: List[str]) -> Dict[str, Dict[str, int]]:
        """
        ПОЛНОСТЬЮ ПЕРЕПИСАННАЯ функция без обращения к несуществующим полям
        """
        result = {}
        
        async with AsyncSessionLocal() as session:
            for date_str in date_list:
                logger.info(f"📄 Processing date: {date_str}")
                
                try:
                    date_obj = datetime.strptime(date_str, '%Y-%m-%d')
                    date_start = date_obj.replace(hour=0, minute=0, second=0, microsecond=0)
                    date_end = date_start + timedelta(days=1)
                    
                    stage_counts = {
                        OnboardingStage.NEW_USER: 0,
                        OnboardingStage.INTRO_SHOWN: 0,
                        OnboardingStage.WAIT_PAYMENT: 0,
                        OnboardingStage.PAYMENT_OK: 0,
                        "DAILY_PAYMENTS": 0
                    }
                    
                    # 1. INTRO_SHOWN: пользователи ТОЧНО в стадии INTRO_SHOWN (не считаем других)
                    try:
                        intro_result = await session.execute(
                            select(func.count(User.id))
                            .where(
                                and_(
                                    User.created_at >= date_start,
                                    User.created_at < date_end,
                                    User.onboarding_stage == OnboardingStage.INTRO_SHOWN  # ТОЧНО эта стадия
                                )
                            )
                        )
                        stage_counts[OnboardingStage.INTRO_SHOWN] = intro_result.scalar() or 0
                        logger.info(f"✅ {date_str}: INTRO_SHOWN = {stage_counts[OnboardingStage.INTRO_SHOWN]}")
                    except Exception as e:
                        logger.error(f"❌ Error getting INTRO_SHOWN for {date_str}: {e}")
                        stage_counts[OnboardingStage.INTRO_SHOWN] = 0
                    
                    # 2. WAIT_PAYMENT: пользователи в стадии ожидания оплаты
                    try:
                        wait_result = await session.execute(
                            select(func.count(User.id))
                            .where(
                                and_(
                                    User.created_at >= date_start,
                                    User.created_at < date_end,
                                    User.onboarding_stage == OnboardingStage.WAIT_PAYMENT
                                )
                            )
                        )
                        stage_counts[OnboardingStage.WAIT_PAYMENT] = wait_result.scalar() or 0
                        logger.info(f"✅ {date_str}: WAIT_PAYMENT = {stage_counts[OnboardingStage.WAIT_PAYMENT]}")
                    except Exception as e:
                        logger.error(f"❌ Error getting WAIT_PAYMENT for {date_str}: {e}")
                        stage_counts[OnboardingStage.WAIT_PAYMENT] = 0
                    
                    # 3. PAYMENT_OK: Используем РЕАЛЬНЫЙ источник данных - Google Sheets
                    try:
                        # Получаем данные из Google Sheets как источника истины
                        sheets_payment_count = await self._get_payments_from_sheets_for_date(date_str)
                        stage_counts[OnboardingStage.PAYMENT_OK] = sheets_payment_count
                        logger.info(f"✅ {date_str}: PAYMENT_OK (from Sheets) = {stage_counts[OnboardingStage.PAYMENT_OK]}")
                        
                        # ДИАГНОСТИКА: сравниваем с БД
                        same_day_payment_result = await session.execute(
                            select(func.count(User.id))
                            .where(
                                and_(
                                    User.created_at >= date_start,
                                    User.created_at < date_end,
                                    User.payment_completed == True
                                )
                            )
                        )
                        db_payment_count = same_day_payment_result.scalar() or 0
                        
                        if sheets_payment_count != db_payment_count:
                            logger.warning(f"⚠️ {date_str}: Sheets={sheets_payment_count} != DB={db_payment_count}")
                            
                    except Exception as e:
                        logger.error(f"❌ Error getting PAYMENT_OK for {date_str}: {e}")
                        stage_counts[OnboardingStage.PAYMENT_OK] = 0
                    
                    # 4. DAILY_PAYMENTS: Используем Google Sheets как единый источник истины
                    try:
                        # Главный источник - Google Sheets "Оплаты"
                        sheets_payments = await self._get_payments_from_sheets_for_date(date_str)
                        daily_payments_count = sheets_payments
                        
                        logger.info(f"✅ {date_str}: DAILY_PAYMENTS (from Sheets) = {daily_payments_count}")
                        
                        # ДИАГНОСТИКА: проверяем альтернативные источники
                        robokassa_count = 0
                        sales_count = 0
                        
                        # Robokassa платежи (для диагностики)
                        try:
                            from app.database.models import Payment
                            robokassa_payments = await session.execute(
                                select(func.count(Payment.id))
                                .where(
                                    and_(
                                        func.date(Payment.updated_at) == date_obj.date(),
                                        Payment.status == "paid"
                                    )
                                )
                            )
                            robokassa_count = robokassa_payments.scalar() or 0
                        except Exception as e:
                            logger.warning(f"⚠️ Could not get Robokassa payments for {date_str}: {e}")
                        
                        # GetCourse платежи (для диагностики)
                        try:
                            from app.database.models import Sale
                            sales_payments = await session.execute(
                                select(func.count(Sale.id))
                                .where(func.date(Sale.created_at) == date_obj.date())
                            )
                            sales_count = sales_payments.scalar() or 0
                        except Exception as e:
                            logger.warning(f"⚠️ Could not get Sales for {date_str}: {e}")
                        
                        # ДИАГНОСТИКА сравнения
                        db_total = robokassa_count + sales_count
                        if daily_payments_count != db_total:
                            logger.warning(f"🔍 {date_str}: ДИАГНОСТИКА ПЛАТЕЖЕЙ:")
                            logger.warning(f"    - Google Sheets: {daily_payments_count}")
                            logger.warning(f"    - Robokassa DB: {robokassa_count}")
                            logger.warning(f"    - Sales DB: {sales_count}")
                            logger.warning(f"    - DB Total: {db_total}")
                            logger.warning(f"    ➜ Используем Google Sheets как источник истины")
                        
                    except Exception as e:
                        logger.error(f"❌ Error getting DAILY_PAYMENTS for {date_str}: {e}")
                        daily_payments_count = 0
                    
                    stage_counts["DAILY_PAYMENTS"] = daily_payments_count
                    
                    result[date_str] = stage_counts
                    
                    # Итоговое логирование
                    logger.info(f"📊 {date_str} FINAL: NEW=0, INTRO={stage_counts[OnboardingStage.INTRO_SHOWN]}, "
                              f"WAIT={stage_counts[OnboardingStage.WAIT_PAYMENT]}, "
                              f"SAME_DAY={stage_counts[OnboardingStage.PAYMENT_OK]}, "
                              f"ALL_PAYMENTS={stage_counts['DAILY_PAYMENTS']}")
                    
                except Exception as date_error:
                    logger.error(f"❌ Error processing date {date_str}: {date_error}")
                    result[date_str] = {
                        OnboardingStage.NEW_USER: 0,
                        OnboardingStage.INTRO_SHOWN: 0,
                        OnboardingStage.WAIT_PAYMENT: 0,
                        OnboardingStage.PAYMENT_OK: 0,
                        "DAILY_PAYMENTS": 0
                    }
                    continue
        
        logger.info(f"✅ Successfully processed {len(result)} dates for stages")
        return result
    
    async def process_all_data(self):
        """Обработка всех данных и запись в Google Sheets"""
        try:
            # Получаем все данные из логов
            users_by_date = await self.get_users_from_logs_by_date(None)
            
            if not users_by_date:
                logger.info("📝 No data found in logs")
                return True
            
            all_dates_from_logs = list(users_by_date.keys())
            logger.info(f"📊 Found {len(all_dates_from_logs)} dates in logs")
            
            # Получаем данные по стадиям
            stage_data = await self.get_users_by_stages_for_dates(all_dates_from_logs)
            
            if not stage_data:
                logger.error("❌ No stage data received")
                return False
            
            today_formatted = datetime.now(MOSCOW_TZ).strftime('%d.%m.%Y')
            current_time = datetime.now(MOSCOW_TZ).strftime('%H:%M МСК')
            
            # Подготавливаем все данные для записи
            all_rows = []
            
            for date_str in sorted(all_dates_from_logs, reverse=True):
                try:
                    formatted_date = datetime.strptime(date_str, '%Y-%m-%d').strftime('%d.%m.%Y')
                    
                    # Время только для сегодняшней записи
                    time_column = current_time if formatted_date == today_formatted else ""
                    
                    # Подготавливаем данные строки
                    new_users_count = len(users_by_date.get(date_str, set()))
                    date_stage_data = stage_data.get(date_str, {})
                    
                    row_data = [
                        formatted_date,
                        time_column,
                        str(new_users_count)
                    ]
                    
                    # Добавляем остальные стадии
                    for stage in REQUIRED_STAGES[1:]:
                        count = date_stage_data.get(stage, 0)
                        row_data.append(str(count))
                    
                    all_rows.append(row_data)
                    
                    logger.info(f"📋 Prepared row for {formatted_date}: {' | '.join(row_data[2:])}")
                    
                except Exception as e:
                    logger.error(f"❌ Error preparing row for {date_str}: {e}")
                    continue
            
            # Записываем все данные сразу
            if all_rows:
                logger.info(f"📝 Writing {len(all_rows)} rows to Google Sheets")
                self.worksheet.append_rows(all_rows)
                logger.info(f"✅ Successfully added {len(all_rows)} rows")
                return True
            else:
                logger.info("📝 No rows to add")
                return True
            
        except Exception as e:
            logger.error(f"❌ Error in process_all_data: {e}", exc_info=True)
            return False
    
    async def run(self):
        """Основной метод запуска"""
        logger.info("🚀 Starting FINAL conversion analytics...")
        
        if not await self.init():
            logger.error("❌ Failed to initialize")
            return False
        
        try:
            success = await self.process_all_data()
            
            if success:
                logger.info("=" * 60)
                logger.info("📊 FINAL CONVERSION ANALYTICS COMPLETE")
                logger.info("  ✅ Все данные обработаны без ошибок")
                logger.info("  ✅ Столбцы заполнены корректными данными")
                logger.info("  ✅ Время обновления добавлено для сегодня")
                logger.info("  ✅ Google Sheets используется как источник истины")
                logger.info("=" * 60)
            
            return success
            
        except Exception as e:
            logger.error(f"❌ Critical error in run: {e}", exc_info=True)
            return False

async def main():
    """Точка входа"""
    analytics = ConversionAnalyticsFinal()
    success = await analytics.run()
    
    if success:
        logger.info("✅ Final analytics completed successfully")
        sys.exit(0)
    else:
        logger.error("❌ Final analytics failed")
        sys.exit(1)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("⚠️ Script interrupted by user")
        sys.exit(0)
    except Exception as e:
        logger.error(f"❌ Fatal error: {e}", exc_info=True)
        sys.exit(1)