#!/usr/bin/env python3
"""
ПРАВИЛЬНАЯ ВЕРСИЯ: Использует БД как источник истины для платежей
"""

import os
import sys
import logging
import asyncio
import re
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from collections import defaultdict
import subprocess
import pytz

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database.connection import AsyncSessionLocal, init_db
from app.database.models import User, OnboardingStage
from app.services.google_sheets import GoogleSheetsService
from sqlalchemy import select, func, and_

logging.basicConfig(level=logging.INFO)
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

class ConversionAnalyticsCorrect:
    """ПРАВИЛЬНАЯ версия с БД как источником истины"""
    
    def __init__(self):
        self.sheets_service = GoogleSheetsService()
        self.worksheet = None
        
    async def init(self):
        await init_db()
        success = await self.sheets_service.init()
        if not success:
            raise Exception("Failed to initialize Google Sheets")
        
        sheet_name = "Конверсии по дням FINAL"
        
        try:
            self.worksheet = self.sheets_service.spreadsheet.worksheet(sheet_name)
        except:
            self.worksheet = self.sheets_service.spreadsheet.add_worksheet(
                title=sheet_name, rows=1000, cols=10
            )
            headers = ["Дата", "Время обновления"] + [STAGE_NAMES[stage] for stage in REQUIRED_STAGES]
            self.worksheet.update('A1:G1', [headers])
            time.sleep(2)
        
        return True
    
    async def get_users_from_logs_by_date(self) -> Dict[str, set]:
        users_by_date = defaultdict(set)
        
        cmd = ["find", BOT_PATH, "-type", "f", "(", "-name", "*.log", "-o", "-name", "*.txt", ")"]
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode != 0:
            return {}
            
        log_files = [f for f in result.stdout.strip().split('\n') if f.strip()]
        
        for log_file in log_files:
            try:
                grep_cmd = ["grep", "/start", log_file]
                grep_result = subprocess.run(grep_cmd, capture_output=True, text=True)
                
                if grep_result.stdout:
                    for line in grep_result.stdout.strip().split('\n'):
                        if not line.strip():
                            continue
                        match = re.search(LOG_PATTERN, line)
                        if match:
                            date_str = match.group(1)
                            user_id = int(match.group(3))
                            users_by_date[date_str].add(user_id)
            except:
                continue
        
        return dict(users_by_date)
    
    async def get_payment_data_from_db(self, date_str: str) -> tuple:
        """Получение данных о платежах из БД - ПРАВИЛЬНЫЙ источник"""
        try:
            date_obj = datetime.strptime(date_str, '%Y-%m-%d')
            date_start = date_obj.replace(hour=0, minute=0, second=0, microsecond=0)
            date_end = date_start + timedelta(days=1)
            
            async with AsyncSessionLocal() as session:
                # 1. Пользователи зарегистрированные и оплатившие в тот же день (payment_completed=True)
                same_day_result = await session.execute(
                    select(func.count(User.id))
                    .where(
                        and_(
                            User.created_at >= date_start,
                            User.created_at < date_end,
                            User.payment_completed == True
                        )
                    )
                )
                same_day_payments = same_day_result.scalar() or 0
                
                # 2. Robokassa платежи за день
                robokassa_count = 0
                try:
                    from app.database.models import Payment
                    robokassa_result = await session.execute(
                        select(func.count(Payment.id))
                        .where(
                            and_(
                                func.date(Payment.updated_at) == date_obj.date(),
                                Payment.status == "paid"
                            )
                        )
                    )
                    robokassa_count = robokassa_result.scalar() or 0
                except:
                    pass
                
                # 3. Sales платежи за день  
                sales_count = 0
                try:
                    from app.database.models import Sale
                    sales_result = await session.execute(
                        select(func.count(Sale.id))
                        .where(func.date(Sale.created_at) == date_obj.date())
                    )
                    sales_count = sales_result.scalar() or 0
                except:
                    pass
                
                # Общее количество платежей за день
                total_daily_payments = robokassa_count + sales_count
                
                return same_day_payments, total_daily_payments, robokassa_count, sales_count
                
        except Exception as e:
            logger.error(f"Ошибка получения данных платежей для {date_str}: {e}")
            return 0, 0, 0, 0
    
    async def get_users_by_stages_for_dates(self, date_list: List[str]) -> Dict[str, Dict]:
        result = {}
        
        async with AsyncSessionLocal() as session:
            for date_str in date_list:
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
                    
                    # INTRO_SHOWN
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
                    
                    # WAIT_PAYMENT
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
                    
                    # ПЛАТЕЖИ - из БД (правильный источник)
                    same_day, total_daily, robokassa, sales = await self.get_payment_data_from_db(date_str)
                    
                    stage_counts[OnboardingStage.PAYMENT_OK] = same_day
                    stage_counts["DAILY_PAYMENTS"] = total_daily
                    
                    result[date_str] = stage_counts
                    
                    # Лог для дат с платежами
                    if total_daily > 0:
                        logger.info(f"💰 {date_str}: Same-day={same_day}, Total={total_daily} (Robokassa={robokassa}, Sales={sales})")
                    
                except Exception as e:
                    logger.error(f"Ошибка обработки {date_str}: {e}")
                    result[date_str] = {s: 0 for s in [OnboardingStage.NEW_USER, OnboardingStage.INTRO_SHOWN, 
                                                      OnboardingStage.WAIT_PAYMENT, OnboardingStage.PAYMENT_OK, "DAILY_PAYMENTS"]}
        
        return result
    
    async def process_all_data(self):
        users_by_date = await self.get_users_from_logs_by_date()
        if not users_by_date:
            return True
        
        all_dates = list(users_by_date.keys())
        stage_data = await self.get_users_by_stages_for_dates(all_dates)
        
        today_formatted = datetime.now(MOSCOW_TZ).strftime('%d.%m.%Y')
        current_time = datetime.now(MOSCOW_TZ).strftime('%H:%M МСК')
        
        all_rows = []
        
        for date_str in sorted(all_dates, reverse=True):
            formatted_date = datetime.strptime(date_str, '%Y-%m-%d').strftime('%d.%m.%Y')
            time_column = current_time if formatted_date == today_formatted else ""
            
            new_users_count = len(users_by_date.get(date_str, set()))
            date_stage_data = stage_data.get(date_str, {})
            
            row_data = [formatted_date, time_column, str(new_users_count)]
            
            for stage in REQUIRED_STAGES[1:]:
                count = date_stage_data.get(stage, 0)
                row_data.append(str(count))
            
            all_rows.append(row_data)
            
            # Показать только строки с платежами
            if int(row_data[-1]) > 0 or int(row_data[-2]) > 0:  # Если есть платежи
                logger.info(f"📋 {formatted_date}: {' | '.join(row_data[2:])}")
        
        if all_rows:
            self.worksheet.clear()
            headers = ["Дата", "Время обновления"] + [STAGE_NAMES[stage] for stage in REQUIRED_STAGES]
            self.worksheet.update('A1:G1', [headers])
            
            # Записываем данные
            batch_size = 100
            for i in range(0, len(all_rows), batch_size):
                batch = all_rows[i:i+batch_size]
                start_row = i + 2
                end_row = start_row + len(batch) - 1
                range_name = f'A{start_row}:G{end_row}'
                self.worksheet.update(range_name, batch)
                if i + batch_size < len(all_rows):
                    time.sleep(1)
            
            logger.info("✅ Данные обновлены")
        
        return True
    
    async def run(self):
        if not await self.init():
            return False
        
        success = await self.process_all_data()
        
        if success:
            logger.info("🎯 ПРАВИЛЬНАЯ АНАЛИТИКА ЗАВЕРШЕНА")
            logger.info("  ✅ Источник данных: БД (не Google Sheets)")
            logger.info("  ✅ Robokassa + Sales = корректные платежи")
        
        return success

async def main():
    analytics = ConversionAnalyticsCorrect()
    success = await analytics.run()
    return 0 if success else 1

if __name__ == "__main__":
    try:
        exit_code = asyncio.run(main())
        sys.exit(exit_code)
    except KeyboardInterrupt:
        sys.exit(0)
