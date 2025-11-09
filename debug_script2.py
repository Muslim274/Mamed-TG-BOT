#!/usr/bin/env python3
"""
Анализ конкретных пользователей и их покупок
"""

import asyncio
import logging
from datetime import datetime
from app.database.connection import AsyncSessionLocal, init_db
from app.database.models import User, Payment, Sale
from sqlalchemy import select, and_, or_

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)

async def analyze_specific_users():
    """Анализ конкретных пользователей"""
    
    # Telegram ID пользователей, которые якобы сделали покупки 25.09.2025
    target_users = [7951381914, 5770664096, 5371246308, 6030319393]
    
    logger.info("=" * 70)
    logger.info("АНАЛИЗ КОНКРЕТНЫХ ПОЛЬЗОВАТЕЛЕЙ ЗА 25.09.2025")
    logger.info("=" * 70)
    
    async with AsyncSessionLocal() as session:
        for telegram_id in target_users:
            logger.info(f"\n🔍 АНАЛИЗ ПОЛЬЗОВАТЕЛЯ {telegram_id}")
            logger.info("-" * 50)
            
            # 1. Найти пользователя
            user_result = await session.execute(
                select(User).where(User.telegram_id == telegram_id)
            )
            user = user_result.scalar_one_or_none()
            
            if not user:
                logger.error(f"❌ Пользователь {telegram_id} не найден в БД")
                continue
            
            logger.info(f"👤 Данные пользователя:")
            logger.info(f"   ID в БД: {user.id}")
            logger.info(f"   Username: {user.username}")
            logger.info(f"   Создан: {user.created_at}")
            logger.info(f"   payment_completed: {user.payment_completed}")
            logger.info(f"   onboarding_stage: {user.onboarding_stage}")
            
            # 2. Найти все платежи Robokassa
            payments_result = await session.execute(
                select(Payment).where(Payment.user_id == user.id)
            )
            payments = payments_result.fetchall()
            
            logger.info(f"\n💳 ROBOKASSA ПЛАТЕЖИ ({len(payments)}):")
            if payments:
                for payment in payments:
                    logger.info(f"   Invoice: {payment.invoice_id}")
                    logger.info(f"   Статус: {payment.status}")
                    logger.info(f"   Сумма: {payment.amount}")
                    logger.info(f"   Создан: {payment.created_at}")
                    logger.info(f"   Обновлен: {payment.updated_at}")
                    
                    # Проверяем, оплачен ли в 25.09.2025
                    if payment.updated_at and payment.updated_at.date() == datetime(2025, 9, 25).date():
                        if payment.status == 'paid':
                            logger.info(f"   ✅ ОПЛАЧЕН 25.09.2025!")
                        else:
                            logger.info(f"   ⚠️ Обновлен 25.09.2025 но статус: {payment.status}")
                    logger.info("")
            else:
                logger.info("   Нет платежей Robokassa")
            
            # 3. Найти Sales (GetCourse)
            sales_result = await session.execute(
                select(Sale).where(Sale.ref_code == user.ref_code)
            )
            sales = sales_result.fetchall()
            
            logger.info(f"\n🛒 SALES (GetCourse) ({len(sales)}):")
            if sales:
                for sale in sales:
                    logger.info(f"   Ref: {sale.ref_code}")
                    logger.info(f"   Сумма: {sale.amount}")
                    logger.info(f"   Комиссия: {sale.commission_amount}")
                    logger.info(f"   Создан: {sale.created_at}")
                    
                    # Проверяем, создан ли в 25.09.2025
                    if sale.created_at.date() == datetime(2025, 9, 25).date():
                        logger.info(f"   ✅ ПРОДАЖА 25.09.2025!")
                    logger.info("")
            else:
                logger.info("   Нет продаж GetCourse")
            
            # 4. Проверяем регистрацию в тот же день
            user_reg_date = user.created_at.date()
            target_date = datetime(2025, 9, 25).date()
            
            same_day_reg = user_reg_date == target_date
            logger.info(f"\n📅 ВРЕМЕННОЙ АНАЛИЗ:")
            logger.info(f"   Регистрация: {user_reg_date}")
            logger.info(f"   Целевая дата: {target_date}")
            logger.info(f"   Регистрация в тот же день: {same_day_reg}")
            
            # 5. Итоговый вывод для этого пользователя
            has_robokassa_payment_today = any(
                p.updated_at and p.updated_at.date() == target_date and p.status == 'paid' 
                for p in payments
            )
            
            has_sales_today = any(
                s.created_at.date() == target_date 
                for s in sales
            )
            
            logger.info(f"\n📊 ИТОГ ДЛЯ {telegram_id}:")
            logger.info(f"   Robokassa оплата 25.09: {has_robokassa_payment_today}")
            logger.info(f"   GetCourse продажа 25.09: {has_sales_today}")
            logger.info(f"   Регистрация 25.09: {same_day_reg}")
            logger.info(f"   payment_completed: {user.payment_completed}")
            
            # Должен ли считаться в "Оплатили (рег+оплата в 1 день)"?
            should_count_same_day = same_day_reg and (has_robokassa_payment_today or has_sales_today)
            logger.info(f"   Должен считаться в 'рег+оплата в 1 день': {should_count_same_day}")
            
            logger.info("=" * 50)

async def main():
    """Главная функция"""
    await init_db()
    await analyze_specific_users()
    
    logger.info("\n" + "=" * 70)
    logger.info("ВЫВОДЫ:")
    logger.info("=" * 70)
    logger.info("Проанализируем результаты и определим:")
    logger.info("1. Кто из этих пользователей реально совершил покупку 25.09.2025")
    logger.info("2. Каким способом (Robokassa или GetCourse)")
    logger.info("3. Кто зарегистрировался и оплатил в один день")
    logger.info("4. Почему данные не попадают в аналитику")

if __name__ == "__main__":
    asyncio.run(main())