#!/usr/bin/env python3
"""
Скрипт для поиска дубликатов продаж в таблице sales
"""
import sys
import os

# Добавляем путь к проекту
sys.path.insert(0, '/root/telegram-referral-bot')

import asyncio
from sqlalchemy import text
from app.database.connection import AsyncSessionLocal

async def find_duplicate_sales():
    try:
        async with AsyncSessionLocal() as session:
            print("\n" + "="*80)
            print("🔍 ПОИСК ДУБЛИКАТОВ ПРОДАЖ")
            print("="*80 + "\n")
            
            # 1. Ищем пользователей с несколькими продажами
            query1 = text("""
                SELECT 
                    customer_email,
                    ref_code,
                    COUNT(*) as sale_count,
                    SUM(commission_amount) as total_commission,
                    ARRAY_AGG(product) as products,
                    ARRAY_AGG(created_at ORDER BY created_at) as dates
                FROM sales
                WHERE customer_email LIKE 'user_%'
                GROUP BY customer_email, ref_code
                HAVING COUNT(*) > 1
                ORDER BY COUNT(*) DESC
            """)
            
            result1 = await session.execute(query1)
            duplicates = result1.fetchall()
            
            print(f"📊 Найдено пользователей с дубликатами: {len(duplicates)}\n")
            
            for dup in duplicates:
                print(f"{'─'*80}")
                print(f"📧 Customer: {dup.customer_email}")
                print(f"🔗 Ref Code: {dup.ref_code}")
                print(f"🔢 Количество продаж: {dup.sale_count}")
                print(f"💰 Общая комиссия: {dup.total_commission:.2f} руб.")
                print(f"📦 Продукты:")
                for i, product in enumerate(dup.products, 1):
                    print(f"   {i}. {product}")
                print(f"📅 Даты:")
                for i, date in enumerate(dup.dates, 1):
                    print(f"   {i}. {date}")
            
            print("\n" + "="*80)
            print("🔄 ПРОДАЖИ ОТ КОМАНДЫ /reset")
            print("="*80 + "\n")
            
            # 2. Ищем все продажи с Reset Auto-Approved
            query2 = text("""
                SELECT 
                    id,
                    ref_code,
                    customer_email,
                    amount,
                    commission_amount,
                    product,
                    created_at
                FROM sales
                WHERE product LIKE '%Reset Auto-Approved%'
                ORDER BY created_at DESC
            """)
            
            result2 = await session.execute(query2)
            reset_sales = result2.fetchall()
            
            print(f"📊 Всего продаж от /reset: {len(reset_sales)}\n")
            
            for sale in reset_sales:
                print(f"{'─'*80}")
                print(f"🆔 Sale ID: {sale.id}")
                print(f"📧 Customer: {sale.customer_email}")
                print(f"🔗 Ref Code: {sale.ref_code}")
                print(f"💵 Amount: {sale.amount:.2f} руб.")
                print(f"💰 Commission: {sale.commission_amount:.2f} руб.")
                print(f"📅 Created: {sale.created_at}")
            
            print("\n" + "="*80)
            print("📈 СТАТИСТИКА ПО РЕФЕРЕРАМ")
            print("="*80 + "\n")
            
            # 3. Группируем по ref_code чтобы увидеть кто получил больше всего
            query3 = text("""
                SELECT 
                    ref_code,
                    COUNT(*) as total_sales,
                    COUNT(CASE WHEN product LIKE '%Reset%' THEN 1 END) as reset_sales,
                    SUM(commission_amount) as total_commission
                FROM sales
                GROUP BY ref_code
                HAVING COUNT(CASE WHEN product LIKE '%Reset%' THEN 1 END) > 0
                ORDER BY reset_sales DESC
            """)
            
            result3 = await session.execute(query3)
            referrers = result3.fetchall()
            
            for ref in referrers:
                print(f"{'─'*80}")
                print(f"🔗 Ref Code: {ref.ref_code}")
                print(f"📊 Всего продаж: {ref.total_sales}")
                print(f"🔄 Из них от /reset: {ref.reset_sales}")
                print(f"💰 Общая комиссия: {ref.total_commission:.2f} руб.")
            
            print("\n" + "="*80)
            
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(find_duplicate_sales())
