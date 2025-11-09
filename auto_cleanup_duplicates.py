#!/usr/bin/env python3
"""
Автоматическое удаление дубликатов с подтверждением
⚠️ ПЕРЕД ЗАПУСКОМ СДЕЛАЙ БЭКАП БАЗЫ!
"""
import sys
sys.path.insert(0, '/root/telegram-referral-bot')

import asyncio
from sqlalchemy import text
from app.database.connection import AsyncSessionLocal

async def auto_cleanup_duplicates():
    async with AsyncSessionLocal() as session:
        print("\n" + "="*100)
        print("⚠️  АВТОМАТИЧЕСКОЕ УДАЛЕНИЕ ДУБЛИКАТОВ")
        print("="*100 + "\n")
        
        # Находим дубликаты
        query = text("""
            WITH ranked_sales AS (
                SELECT 
                    id,
                    customer_email,
                    ref_code,
                    commission_amount,
                    created_at,
                    ROW_NUMBER() OVER (PARTITION BY customer_email, ref_code ORDER BY created_at ASC) as rn
                FROM sales
                WHERE product LIKE '%Reset Auto-Approved%'
            )
            SELECT id, customer_email, ref_code, commission_amount, created_at
            FROM ranked_sales
            WHERE rn > 1
            ORDER BY customer_email, created_at
        """)
        
        result = await session.execute(query)
        duplicates = result.fetchall()
        
        if len(duplicates) == 0:
            print("✅ Дубликатов не найдено! База чистая.\n")
            return
        
        print(f"🗑️  Найдено дубликатов: {len(duplicates)}\n")
        
        delete_ids = []
        total = 0
        
        for dup in duplicates:
            print(f"ID: {dup.id} | {dup.customer_email} | {dup.ref_code} | {dup.commission_amount:.2f} руб")
            delete_ids.append(dup.id)
            total += dup.commission_amount
        
        print(f"\n💰 Итого к удалению: {total:.2f} руб\n")
        print("="*100)
        print("⚠️  ЭТИ ЗАПИСИ БУДУТ УДАЛЕНЫ ИЗ ТАБЛИЦЫ sales!")
        print("="*100)
        print("\nПродолжить? (введи YES для подтверждения): ", end='')
        
        confirmation = input().strip()
        
        if confirmation != "YES":
            print("\n❌ Отменено. Ничего не удалено.\n")
            return
        
        # Удаляем дубликаты
        print("\n🔄 Удаление дубликатов...")
        
        delete_query = text("DELETE FROM sales WHERE id = ANY(:ids)")
        await session.execute(delete_query, {"ids": delete_ids})
        await session.commit()
        
        print(f"✅ Удалено {len(delete_ids)} дубликатов!\n")
        
        # Показываем что осталось
        check_query = text("""
            SELECT COUNT(*) as cnt
            FROM sales
            WHERE product LIKE '%Reset Auto-Approved%'
        """)
        
        check_result = await session.execute(check_query)
        remaining = check_result.fetchone()
        
        print(f"📊 Осталось Reset продаж (без дубликатов): {remaining.cnt}")
        print("\n" + "="*100)
        print("⚠️  ВАЖНО: Теперь нужно вычесть суммы из балансов реферов!")
        print("="*100)
        print(f"\nЗапусти: python3 show_balance_corrections.py")
        print("Он покажет сколько вычесть у каждого реферера\n")

if __name__ == "__main__":
    asyncio.run(auto_cleanup_duplicates())
