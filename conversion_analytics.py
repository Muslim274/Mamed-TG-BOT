#!/usr/bin/env python3
"""
ФИНАЛЬНАЯ ВЕРСИЯ: Скрипт анализа конверсий с правильной логикой GetCourse платежей
Версия 4.7 - Время обновления только для текущего дня
GetCourse платежи учитываются по дате подтверждения админом (Sale.created_at)
"""

import os
import sys
import logging
import asyncio
import re
import time
import json
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional
from collections import defaultdict
import subprocess
import pytz
import argparse

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
BACKUP_FILE = '/root/telegram-referral-bot/data_backup.json'

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
    """ФИНАЛЬНАЯ версия аналитики конверсий с правильным подсчетом оплат"""
    
    def __init__(self):
        self.sheets_service = GoogleSheetsService()
        self.worksheet = None
        self.last_update_date = None
        self.backup_data = {}
        
    async def init(self):
        """Инициализация подключения к Google Sheets"""
        try:
            await init_db()
            logger.info("✅ Database initialized")
            
            success = await self.sheets_service.init()
            if not success:
                raise Exception("Failed to initialize Google Sheets")
            
            sheet_name = "Конверсии по дням"
            
            try:
                self.worksheet = self.sheets_service.spreadsheet.worksheet(sheet_name)
                logger.info(f"✅ Found existing '{sheet_name}' worksheet")
                
                headers = self.worksheet.row_values(1)
                expected_headers = ["Дата", "Время обновления"] + [STAGE_NAMES[stage] for stage in REQUIRED_STAGES]
                
                if not headers or headers != expected_headers:
                    logger.info("🔄 Updating headers...")
                    self.worksheet.update(range_name='A1:G1', values=[expected_headers])
                    time.sleep(2)
                    
            except:
                logger.info(f"🔄 Creating new '{sheet_name}' worksheet")
                self.worksheet = self.sheets_service.spreadsheet.add_worksheet(
                    title=sheet_name, 
                    rows=1000, 
                    cols=10
                )
                
                headers = ["Дата", "Время обновления"] + [STAGE_NAMES[stage] for stage in REQUIRED_STAGES]
                self.worksheet.update(range_name='A1:G1', values=[headers])
                time.sleep(2)
                logger.info("✅ Headers added to new worksheet")
            
            # Создаем резервную копию существующих данных
            await self.create_backup()
            
            self.last_update_date = await self._get_last_update_date()
            return True
            
        except Exception as e:
            logger.error(f"❌ Error initializing: {e}")
            return False
    
    async def create_backup(self):
        """Создание резервной копии существующих данных"""
        try:
            all_values = self.worksheet.get_all_values()
            
            backup_data = {
                'timestamp': datetime.now(MOSCOW_TZ).isoformat(),
                'data': all_values,
                'total_rows': len(all_values)
            }
            
            # Сохраняем в файл
            with open(BACKUP_FILE, 'w', encoding='utf-8') as f:
                json.dump(backup_data, f, ensure_ascii=False, indent=2)
            
            # Сохраняем в памяти
            self.backup_data = backup_data
            
            logger.info(f"💾 Backup created: {len(all_values)} rows saved to {BACKUP_FILE}")
            
        except Exception as e:
            logger.error(f"❌ Error creating backup: {e}")
            # Продолжаем работу даже если бэкап не удался
    
    async def restore_from_backup(self):
        """Восстановление данных из резервной копии"""
        try:
            if os.path.exists(BACKUP_FILE):
                with open(BACKUP_FILE, 'r', encoding='utf-8') as f:
                    backup_data = json.load(f)
                
                if backup_data.get('data'):
                    # Очищаем лист
                    self.worksheet.clear()
                    time.sleep(1)
                    
                    # Восстанавливаем данные
                    if backup_data['data']:
                        self.worksheet.update('A1', backup_data['data'])
                        logger.info(f"🔄 Restored {len(backup_data['data'])} rows from backup")
                        return True
            
            logger.error("❌ No valid backup found")
            return False
            
        except Exception as e:
            logger.error(f"❌ Error restoring backup: {e}")
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
            
            return dict(users_by_date)
            
        except Exception as e:
            logger.error(f"❌ Error getting users from logs: {e}", exc_info=True)
            return {}
    
    async def get_users_by_stages_for_dates(self, date_list: List[str]) -> Dict[str, Dict[str, int]]:
        """
        ПОЛНОСТЬЮ ПЕРЕПИСАННАЯ функция с правильным подсчетом payment_completed
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
                    
                    # 1. INTRO_SHOWN: пользователи ТОЧНО в стадии INTRO_SHOWN
                    try:
                        intro_result = await session.execute(
                            select(func.count(User.id))
                            .where(
                                and_(
                                    User.created_at >= date_start,
                                    User.created_at < date_end,
                                    User.onboarding_stage == OnboardingStage.INTRO_SHOWN
                                )
                            )
                        )
                        stage_counts[OnboardingStage.INTRO_SHOWN] = intro_result.scalar() or 0
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
                    except Exception as e:
                        logger.error(f"❌ Error getting WAIT_PAYMENT for {date_str}: {e}")
                        stage_counts[OnboardingStage.WAIT_PAYMENT] = 0
                    
                    # 3. PAYMENT_OK: пользователи с payment_completed=True И регистрацией в этот день
                    try:
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
                        same_day_payments = same_day_payment_result.scalar() or 0
                        stage_counts[OnboardingStage.PAYMENT_OK] = same_day_payments
                        
                    except Exception as e:
                        logger.error(f"❌ Error getting PAYMENT_OK for {date_str}: {e}")
                        stage_counts[OnboardingStage.PAYMENT_OK] = 0
                    
                    # 4. DAILY_PAYMENTS: ВСЕ платежи за день
                    try:
                        # Robokassa платежи за этот день
                        robokassa_count = 0
                        try:
                            from app.database.models import Payment
                            robokassa_payments = await session.execute(
                                select(func.count(Payment.id))
                                .where(
                                    and_(
                                        func.date(Payment.created_at) == date_obj.date(),
                                        Payment.status == "paid"
                                    )
                                )
                            )
                            robokassa_count = robokassa_payments.scalar() or 0
                        except Exception as e:
                            logger.warning(f"⚠️ Could not get Robokassa payments for {date_str}: {e}")
                        
                        # GetCourse платежи за этот день
                        sales_count = 0
                        try:
                            from app.database.models import Sale
                            sales_payments = await session.execute(
                                select(func.count(Sale.id))
                                .where(func.date(Sale.created_at) == date_obj.date())
                            )
                            sales_count = sales_payments.scalar() or 0
                        except Exception as e:
                            logger.warning(f"⚠️ Could not get GetCourse sales for {date_str}: {e}")
                        
                        # Итоговый подсчет
                        daily_payments_count = robokassa_count + sales_count
                        stage_counts["DAILY_PAYMENTS"] = daily_payments_count
                        
                    except Exception as e:
                        logger.error(f"❌ Error getting DAILY_PAYMENTS for {date_str}: {e}")
                        stage_counts["DAILY_PAYMENTS"] = 0
                    
                    result[date_str] = stage_counts
                    
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
    
    async def get_existing_data(self) -> Dict[str, Dict]:
        """Получение существующих данных из таблицы"""
        existing_data = {}
        try:
            all_values = self.worksheet.get_all_values()
            if len(all_values) > 1:
                for row in all_values[1:]:
                    if len(row) >= 3 and row[0]:
                        existing_data[row[0]] = {
                            'time': row[1] if len(row) > 1 else '',
                            'data': row[2:] if len(row) > 2 else [],
                            'row_data': row
                        }
                logger.info(f"📋 Found {len(existing_data)} existing rows in sheet")
        except Exception as e:
            logger.warning(f"⚠️ Could not read existing data: {e}")
            existing_data = {}
        
        return existing_data
    
    async def safe_update_sheet(self, all_rows: List[List[str]]) -> bool:
        """Безопасное обновление таблицы с проверкой"""
        try:
            logger.info(f"📄 Starting safe update of {len(all_rows)} rows")
            
            # Создаем финальную резервную копию перед записью
            await self.create_backup()
            
            # Очищаем старые данные
            self.worksheet.clear()
            time.sleep(1)
            
            # Восстанавливаем заголовки
            headers = ["Дата", "Время обновления"] + [STAGE_NAMES[stage] for stage in REQUIRED_STAGES]
            self.worksheet.update(range_name='A1:G1', values=[headers])
            time.sleep(1)
            
            # Записываем новые данные порциями для надежности
            batch_size = 50
            total_batches = (len(all_rows) + batch_size - 1) // batch_size
            
            for i in range(0, len(all_rows), batch_size):
                batch = all_rows[i:i + batch_size]
                batch_num = i // batch_size + 1
                
                try:
                    self.worksheet.append_rows(batch)
                    logger.info(f"📄 Batch {batch_num}/{total_batches}: {len(batch)} rows added")
                    time.sleep(1)
                    
                except Exception as batch_error:
                    logger.error(f"❌ Error in batch {batch_num}: {batch_error}")
                    # Пытаемся восстановить из бэкапа
                    logger.info("🔄 Attempting to restore from backup...")
                    if await self.restore_from_backup():
                        logger.info("✅ Data restored from backup")
                        return False
                    else:
                        logger.error("❌ Failed to restore from backup!")
                        return False
            
            # Проверяем, что данные записались корректно
            verification_data = self.worksheet.get_all_values()
            if len(verification_data) != len(all_rows) + 1:
                logger.error(f"❌ Data verification failed! Expected {len(all_rows) + 1}, got {len(verification_data)}")
                if await self.restore_from_backup():
                    logger.info("✅ Data restored from backup after verification failure")
                return False
            
            logger.info(f"✅ Safe update completed successfully: {len(all_rows)} rows written")
            return True
            
        except Exception as e:
            logger.error(f"❌ Critical error in safe_update_sheet: {e}")
            logger.info("🔄 Attempting emergency restore...")
            if await self.restore_from_backup():
                logger.info("✅ Emergency restore successful")
            else:
                logger.error("❌ Emergency restore failed!")
            return False
    
    async def update_today_time_only(self):
        """Обновление времени только для сегодняшней записи, если она существует"""
        try:
            current_time = datetime.now(MOSCOW_TZ).strftime('%H:%M МСК')
            today_formatted = datetime.now(MOSCOW_TZ).strftime('%d.%m.%Y')
            
            # Получаем существующие данные
            existing_data = await self.get_existing_data()
            
            if not existing_data:
                logger.info("📄 No existing data found")
                return False
            
            # Проверяем, есть ли сегодняшняя запись
            if today_formatted not in existing_data:
                logger.info(f"📄 Today's date ({today_formatted}) not found in existing data")
                return False
            
            # Подготавливаем данные для записи
            all_rows = []
            for date_str in sorted(existing_data.keys(), key=lambda x: datetime.strptime(x, '%d.%m.%Y'), reverse=True):
                # ИСПРАВЛЕНИЕ: Время только для сегодняшнего дня, для остальных - пустое
                if date_str == today_formatted:
                    time_to_use = current_time
                    logger.info(f"🕐 Updated time for today ({date_str}): {current_time}")
                else:
                    time_to_use = ""  # Пустое время для всех остальных дат
                
                row_data = [date_str, time_to_use] + existing_data[date_str]['data']
                all_rows.append(row_data)
            
            return await self.safe_update_sheet(all_rows)
            
        except Exception as e:
            logger.error(f"❌ Error in update_today_time_only: {e}")
            return False
    
    async def incremental_update(self):
        """Инкрементальное обновление - только недостающие данные"""
        try:
            current_time = datetime.now(MOSCOW_TZ).strftime('%H:%M МСК')
            today_formatted = datetime.now(MOSCOW_TZ).strftime('%d.%m.%Y')
            
            # Получаем существующие данные
            existing_data = await self.get_existing_data()
            
            # Получаем все данные из логов
            users_by_date = await self.get_users_from_logs_by_date(None)
            
            if not users_by_date:
                logger.info("📄 No data found in logs")
                # Если данных в логах нет, но есть сегодняшняя запись - обновляем только время
                return await self.update_today_time_only()
            
            # Определяем какие даты нужно обновить
            all_dates_from_logs = set(users_by_date.keys())
            existing_dates = set(existing_data.keys())
            
            # Даты, которые нужно добавить или обновить
            dates_to_process = []
            
            for date_str in all_dates_from_logs:
                formatted_date = datetime.strptime(date_str, '%Y-%m-%d').strftime('%d.%m.%Y')
                
                if formatted_date not in existing_dates:
                    dates_to_process.append(date_str)
                    logger.info(f"➕ Will add new date: {formatted_date}")
                elif formatted_date == today_formatted:
                    dates_to_process.append(date_str)
                    logger.info(f"🔄 Will update today's data: {formatted_date}")
            
            # Если нет дат для обработки, но есть сегодняшняя запись - обновляем только время
            if not dates_to_process:
                logger.info("📄 No new data to process")
                return await self.update_today_time_only()
            
            logger.info(f"📊 Processing {len(dates_to_process)} dates")
            
            # Получаем данные по стадиям только для нужных дат
            stage_data = await self.get_users_by_stages_for_dates(dates_to_process)
            
            # Обновляем данные
            for date_str in dates_to_process:
                formatted_date = datetime.strptime(date_str, '%Y-%m-%d').strftime('%d.%m.%Y')
                
                # Подготавливаем данные строки
                new_users_count = len(users_by_date.get(date_str, set()))
                date_stage_data = stage_data.get(date_str, {})
                
                row_data = [str(new_users_count)]
                
                for stage in REQUIRED_STAGES[1:]:
                    count = date_stage_data.get(stage, 0)
                    row_data.append(str(count))
                
                # Время записываем только для текущего дня
                time_for_this_date = current_time if formatted_date == today_formatted else existing_data.get(formatted_date, {}).get('time', '')
                
                existing_data[formatted_date] = {
                    'time': time_for_this_date,
                    'data': row_data
                }
                
                if formatted_date == today_formatted:
                    logger.info(f"🕐 Updated time for today ({formatted_date}): {current_time}")
                else:
                    logger.info(f"📋 Updated data for {formatted_date} (time unchanged)")
            
            # Подготавливаем финальные данные для записи

            all_rows = []
            for date_str in sorted(existing_data.keys(), key=lambda x: datetime.strptime(x, '%d.%m.%Y'), reverse=True):
                # ИСПРАВЛЕНИЕ: Время только для сегодняшнего дня
                if date_str == today_formatted:
                    time_to_use = existing_data[date_str]['time']
                else:
                    time_to_use = ""  # Пустое время для всех исторических дат
                
                row_data = [date_str, time_to_use] + existing_data[date_str]['data']
                all_rows.append(row_data)
            
            return await self.safe_update_sheet(all_rows)
            
        except Exception as e:
            logger.error(f"❌ Error in incremental_update: {e}", exc_info=True)
            return False
    
    async def full_update(self):
        """Полное обновление всех данных"""
        try:
            # Получаем все данные из логов
            users_by_date = await self.get_users_from_logs_by_date(None)
            
            if not users_by_date:
                logger.info("📄 No data found in logs")
                return True
            
            all_dates_from_logs = list(users_by_date.keys())
            logger.info(f"📊 Found {len(all_dates_from_logs)} dates in logs")
            
            # Получаем данные по стадиям
            stage_data = await self.get_users_by_stages_for_dates(all_dates_from_logs)
            
            if not stage_data:
                logger.error("❌ No stage data received")
                return False
            
            current_time = datetime.now(MOSCOW_TZ).strftime('%H:%M МСК')
            today_formatted = datetime.now(MOSCOW_TZ).strftime('%d.%m.%Y')
            
            # Подготавливаем все данные для записи
            all_rows = []
            
            for date_str in sorted(all_dates_from_logs, reverse=True):
                try:
                    formatted_date = datetime.strptime(date_str, '%Y-%m-%d').strftime('%d.%m.%Y')
                    
                    # Время записываем только для сегодняшнего дня
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
                    
                    if formatted_date == today_formatted:
                        logger.info(f"🕐 Today's row ({formatted_date}): time={time_column}")
                    
                except Exception as e:
                    logger.error(f"❌ Error preparing row for {date_str}: {e}")
                    continue
            
            return await self.safe_update_sheet(all_rows)
            
        except Exception as e:
            logger.error(f"❌ Error in full_update: {e}", exc_info=True)
            return False
        
    async def run(self, mode='incremental'):
        """
        Основной метод запуска
        
        Args:
            mode (str): Режим работы:
                - 'full': Полное обновление всех данных
                - 'incremental': Инкрементальное обновление (только недостающее)
                - 'today_time': Обновить только время для сегодняшней записи
        """
        logger.info(f"🚀 Starting FINAL conversion analytics v4.7 in '{mode}' mode...")
        
        if not await self.init():
            logger.error("❌ Failed to initialize")
            return False
        
        try:
            success = False
            
            if mode == 'full':
                success = await self.full_update()
                
            elif mode == 'incremental':
                success = await self.incremental_update()
                
            elif mode == 'today_time':
                success = await self.update_today_time_only()
                
            else:
                logger.error(f"❌ Unknown mode: {mode}")
                return False
            
            if success:
                current_time = datetime.now(MOSCOW_TZ).strftime('%H:%M МСК')
                logger.info("=" * 60)
                logger.info(f"📊 FINAL CONVERSION ANALYTICS v4.7 COMPLETE ({mode.upper()} mode)")
                logger.info(f"  ⏰ Last update time: {current_time}")
                logger.info("  ✅ PAYMENT_OK: пользователи с payment_completed=True И регистрацией в тот же день") 
                logger.info("  ✅ DAILY_PAYMENTS: ВСЕ платежи за день (независимо от даты регистрации)")
                logger.info("  ✅ Время обновления записывается ТОЛЬКО для текущего дня")
                logger.info("  ✅ Безопасное обновление с резервным копированием")
                logger.info("=" * 60)
            
            return success
            
        except Exception as e:
            logger.error(f"❌ Critical error in run: {e}", exc_info=True)
            
            # Попытка экстренного восстановления
            logger.info("🚨 Attempting emergency data recovery...")
            if await self.restore_from_backup():
                logger.info("✅ Emergency recovery successful")
            else:
                logger.error("❌ Emergency recovery failed!")
            
            return False


async def main():
    """Точка входа с поддержкой режимов работы"""
    parser = argparse.ArgumentParser(description='Conversion Analytics Script v4.7 - Time Update Only for Today')
    parser.add_argument('--mode', 
                       choices=['full', 'incremental', 'today_time'], 
                       default='incremental',
                       help='Update mode (default: incremental)')
    parser.add_argument('--backup-only', 
                       action='store_true',
                       help='Only create backup without updating')
    parser.add_argument('--restore', 
                       action='store_true',
                       help='Restore data from backup')
    
    args = parser.parse_args()
    
    analytics = ConversionAnalyticsFinal()
    
    # Специальные режимы
    if args.backup_only:
        logger.info("💾 Backup-only mode")
        if await analytics.init():
            await analytics.create_backup()
            logger.info("✅ Backup completed")
        return
    
    if args.restore:
        logger.info("🔄 Restore mode")
        if await analytics.init():
            success = await analytics.restore_from_backup()
            if success:
                logger.info("✅ Restore completed successfully")
                sys.exit(0)
            else:
                logger.error("❌ Restore failed")
                sys.exit(1)
        return
    
    # Обычная работа
    success = await analytics.run(mode=args.mode)
    
    if success:
        logger.info(f"✅ Final analytics v4.7 completed successfully in {args.mode} mode")
        sys.exit(0)
    else:
        logger.error(f"❌ Final analytics failed in {args.mode} mode")
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