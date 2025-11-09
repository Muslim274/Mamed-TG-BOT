#!/usr/bin/env python3
"""
Диагностический скрипт для анализа конкретных дат и выявления причин расхождений в данных
"""

import os
import sys
import asyncio
import logging
from datetime import datetime, timedelta
import pytz

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database.connection import AsyncSessionLocal, init_db
from app.database.crud import UserCRUD
from app.database.models import User, OnboardingStage
from app.services.google_sheets import GoogleSheetsService
from app.config import settings
from sqlalchemy import select, func, and_, text, desc

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

MOSCOW_TZ = pytz.timezone('Europe/Moscow')

class PaymentDiagnostic:
    """Диагностика расхождений в данных по платежам"""
    
    def __init__(self):
        self.sheets_service = GoogleSheetsService()
        
    async def init(self):
        """Инициализация"""
        await init_db()
        success = await self.sheets_service.init()
        return success
    
    async def analyze_specific_date(self, target_date: str):
        """
        Детальный анализ конкретной даты
        target_date в формате 'YYYY-MM-DD' (например, '2025-09-25')
        """
        print(f"\n{'='*60}")
        print(f"ДЕТАЛЬНЫЙ АНАЛИЗ ДАТЫ: {target_date}")
        print(f"{'='*60}")
        
        date_obj = datetime.strptime(target_date, '%Y-%m-%d')
        date_start = date_obj.replace(hour=0, minute=0, second=0, microsecond=0)
        date_end = date_start + timedelta(days=1)
        
        async with AsyncSessionLocal() as session:
            # 1. АНАЛИЗ РЕГИСТРАЦИЙ
            print(f"\n1️⃣ РЕГИСТРАЦИИ {target_date}:")
            
            # Всего регистраций
            total_registrations = await session.execute(
                select(func.count(User.id))
                .where(
                    and_(
                        User.created_at >= date_start,
                        User.created_at < date_end
                    )
                )
            )
            total_reg = total_registrations.scalar() or 0
            print(f"   📊 Всего регистраций: {total_reg}")
            
            # Регистрации по стадиям онбординга
            for stage in [OnboardingStage.NEW_USER, OnboardingStage.INTRO_SHOWN, 
                         OnboardingStage.WAIT_PAYMENT, OnboardingStage.PAYMENT_OK]:
                stage_count = await session.execute(
                    select(func.count(User.id))
                    .where(
                        and_(
                            User.created_at >= date_start,
                            User.created_at < date_end,
                            User.onboarding_stage == stage
                        )
                    )
                )
                count = stage_count.scalar() or 0
                print(f"   📋 {stage.value}: {count}")
            
            # 2. АНАЛИЗ ПОЛЬЗОВАТЕЛЕЙ С ЗАВЕРШЕННОЙ ОПЛАТОЙ
            print(f"\n2️⃣ ПОЛЬЗОВАТЕЛИ С ЗАВЕРШЕННОЙ ОПЛАТОЙ:")
            
            # Зарегистрировались в этот день И имеют payment_completed=True
            same_day_paid = await session.execute(
                select(func.count(User.id))
                .where(
                    and_(
                        User.created_at >= date_start,
                        User.created_at < date_end,
                        User.payment_completed == True
                    )
                )
            )
            same_day_paid_count = same_day_paid.scalar() or 0
            print(f"   💰 Зарегистрированы + payment_completed: {same_day_paid_count}")
            
            # Детальная информация о пользователях с оплатой
            paid_users_details = await session.execute(
                select(User.telegram_id, User.created_at, User.onboarding_stage, User.payment_completed)
                .where(
                    and_(
                        User.created_at >= date_start,
                        User.created_at < date_end,
                        User.payment_completed == True
                    )
                )
                .limit(10)
            )
            paid_users = paid_users_details.fetchall()
            
            if paid_users:
                print(f"   📋 Первые 10 пользователей с оплатой:")
                for user in paid_users:
                    print(f"      ID: {user.telegram_id}, Создан: {user.created_at}, Стадия: {user.onboarding_stage}")
            
            # 3. АНАЛИЗ ТАБЛИЦЫ PAYMENTS
            print(f"\n3️⃣ ТАБЛИЦА PAYMENTS (Robokassa):")
            
            try:
                from app.database.models import Payment
                
                # Платежи созданные в этот день
                payments_created = await session.execute(
                    select(func.count(Payment.id))
                    .where(
                        and_(
                            Payment.created_at >= date_start,
                            Payment.created_at < date_end
                        )
                    )
                )
                created_count = payments_created.scalar() or 0
                print(f"   📅 Создано платежей: {created_count}")
                
                # Платежи обновленные в этот день (статус "paid")
                payments_paid = await session.execute(
                    select(func.count(Payment.id))
                    .where(
                        and_(
                            func.date(Payment.updated_at) == date_obj.date(),
                            Payment.status == "paid"
                        )
                    )
                )
                paid_count = payments_paid.scalar() or 0
                print(f"   💳 Оплачено в этот день: {paid_count}")
                
                # Детали платежей
                payment_details = await session.execute(
                    select(Payment.invoice_id, Payment.amount, Payment.status, 
                           Payment.created_at, Payment.updated_at)
                    .where(func.date(Payment.updated_at) == date_obj.date())
                    .limit(10)
                )
                payments = payment_details.fetchall()
                
                if payments:
                    print(f"   📋 Детали платежей:")
                    for payment in payments:
                        print(f"      Invoice: {payment.invoice_id}, Сумма: {payment.amount}, "
                             f"Статус: {payment.status}")
                        print(f"           Создан: {payment.created_at}, Обновлен: {payment.updated_at}")
                        
            except Exception as e:
                print(f"   ❌ Ошибка анализа Payments: {e}")
            
            # 4. АНАЛИЗ ТАБЛИЦЫ SALES
            print(f"\n4️⃣ ТАБЛИЦА SALES (GetCourse комиссии):")
            
            try:
                from app.database.models import Sale
                
                sales_count_result = await session.execute(
                    select(func.count(Sale.id))
                    .where(func.date(Sale.created_at) == date_obj.date())
                )
                sales_count = sales_count_result.scalar() or 0
                print(f"   💰 Продаж: {sales_count}")
                
                if sales_count > 0:
                    sales_details = await session.execute(
                        select(Sale.ref_code, Sale.amount, Sale.commission_amount, 
                               Sale.product, Sale.created_at)
                        .where(func.date(Sale.created_at) == date_obj.date())
                        .limit(10)
                    )
                    sales = sales_details.fetchall()
                    
                    print(f"   📋 Детали продаж:")
                    for sale in sales:
                        print(f"      Ref: {sale.ref_code}, Сумма: {sale.amount}, "
                             f"Комиссия: {sale.commission_amount}")
                        print(f"           Продукт: {sale.product}, Создано: {sale.created_at}")
                        
            except Exception as e:
                print(f"   ❌ Ошибка анализа Sales: {e}")
    
    async def analyze_google_sheets(self, target_date: str):
        """Анализ данных из Google Sheets для конкретной даты"""
        print(f"\n5️⃣ GOOGLE SHEETS 'ОПЛАТЫ':")
        
        try:
            # Получаем лист "Оплаты"
            payments_worksheet = self.sheets_service.spreadsheet.worksheet('Оплаты')
            all_records = payments_worksheet.get_all_records()
            
            # Фильтруем по дате
            target_payments = []
            for record in all_records:
                payment_date = record.get('Дата оплаты', '')
                if payment_date:
                    # Извлекаем дату (первая часть до пробела)
                    payment_date_only = payment_date.split()[0] if ' ' in payment_date else payment_date
                    if payment_date_only == target_date:
                        target_payments.append(record)
            
            print(f"   📊 Записей в Google Sheets: {len(target_payments)}")
            
            if target_payments:
                print(f"   📋 Первые 5 записей:")
                for i, payment in enumerate(target_payments[:5]):
                    telegram_id = payment.get('Telegram ID', 'N/A')
                    username = payment.get('Username', 'N/A')
                    payment_date = payment.get('Дата оплаты', 'N/A')
                    ref_code = payment.get('Реферальный код пользователя', 'N/A')
                    invited_by = payment.get('Пригласивший (Telegram ID)', 'N/A')
                    
                    print(f"      {i+1}. ID: {telegram_id}, User: {username}")
                    print(f"         Дата: {payment_date}, Ref: {ref_code}, Пригласил: {invited_by}")
            
            return len(target_payments)
            
        except Exception as e:
            print(f"   ❌ Ошибка анализа Google Sheets: {e}")
            return 0
    
    async def cross_reference_analysis(self, target_date: str):
        """Перекрестный анализ: сопоставляем данные из БД и Google Sheets"""
        print(f"\n6️⃣ ПЕРЕКРЕСТНЫЙ АНАЛИЗ:")
        
        try:
            # Получаем список пользователей с оплатой из БД
            date_obj = datetime.strptime(target_date, '%Y-%m-%d')
            date_start = date_obj.replace(hour=0, minute=0, second=0, microsecond=0)
            date_end = date_start + timedelta(days=1)
            
            async with AsyncSessionLocal() as session:
                db_paid_users = await session.execute(
                    select(User.telegram_id)
                    .where(
                        and_(
                            User.created_at >= date_start,
                            User.created_at < date_end,
                            User.payment_completed == True
                        )
                    )
                )
                db_paid_ids = {row.telegram_id for row in db_paid_users.fetchall()}
            
            # Получаем список из Google Sheets
            payments_worksheet = self.sheets_service.spreadsheet.worksheet('Оплаты')
            all_records = payments_worksheet.get_all_records()
            
            sheets_paid_ids = set()
            for record in all_records:
                payment_date = record.get('Дата оплаты', '')
                if payment_date:
                    payment_date_only = payment_date.split()[0] if ' ' in payment_date else payment_date
                    if payment_date_only == target_date:
                        telegram_id = record.get('Telegram ID')
                        if telegram_id:
                            sheets_paid_ids.add(int(telegram_id))
            
            # Сравнение
            print(f"   📊 БД (payment_completed=True): {len(db_paid_ids)} пользователей")
            print(f"   📊 Google Sheets: {len(sheets_paid_ids)} пользователей")
            
            # Пересечения и различия
            intersection = db_paid_ids & sheets_paid_ids
            only_in_db = db_paid_ids - sheets_paid_ids
            only_in_sheets = sheets_paid_ids - db_paid_ids
            
            print(f"   ✅ Совпадают: {len(intersection)}")
            print(f"   🔴 Только в БД: {len(only_in_db)}")
            print(f"   🔵 Только в Sheets: {len(only_in_sheets)}")
            
            if only_in_db:
                print(f"   📋 Только в БД (первые 5): {list(only_in_db)[:5]}")
            
            if only_in_sheets:
                print(f"   📋 Только в Sheets (первые 5): {list(only_in_sheets)[:5]}")
                
        except Exception as e:
            print(f"   ❌ Ошибка перекрестного анализа: {e}")
    
    async def run_full_diagnostic(self, dates_to_analyze: list):
        """Полная диагностика для списка дат"""
        if not await self.init():
            print("❌ Ошибка инициализации")
            return
        
        for target_date in dates_to_analyze:
            await self.analyze_specific_date(target_date)
            await self.analyze_google_sheets(target_date)
            await self.cross_reference_analysis(target_date)
            print(f"\n{'='*60}\n")

async def main():
    """Запуск диагностики для проблемных дат"""
    diagnostic = PaymentDiagnostic()
    
    # Анализируем проблемные даты
    problem_dates = [
        "2025-09-25",  # Сегодня: 0 same-day paid, 1 total payments, 3 в Sheets
        "2025-08-14"   # Парадокс: 55 same-day paid, 39 total payments
    ]
    
    await diagnostic.run_full_diagnostic(problem_dates)

if __name__ == "__main__":
    asyncio.run(main())