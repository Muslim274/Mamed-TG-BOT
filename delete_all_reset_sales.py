#!/usr/bin/env python3
"""
Удаление ВСЕХ Reset продаж (Reset - это НЕ продажа, а обновление бота)
⚠️ ПЕРЕД ЗАПУСКОМ СДЕЛАЙ БЭКАП БАЗЫ!
"""
import sys
sys.path.insert(0, '/root/telegram-referral-bot')

import asyncio
from sqlalchemy import text
from app.database.connection import AsyncSessionLocal

async def delete_all_reset_sales():
    async with AsyncSessionLocal() as session:
        print("\n" + "="*100)
        print("⚠️  УДАЛЕНИЕ ВСЕХ RESET ПРОДАЖ")
        print("="*100 + "\n")
        
        # Находим ВСЕ Reset продажи
        query = text("""
            SELECT 
                id,
                customer_email,
                ref_code,
                commission_amount,
                created_at,
                product
            FROM sales
            WHERE product LIKE '%Reset Auto-Approved%'
            ORDER BY created_at DESC
        """)
        
        result = await session.execute(query)
        all_reset_sales = result.fetchall()
        
        if len(all_reset_sales) == 0:
            print("✅ Reset продаж не найдено! База чистая.\n")
            return
        
        print(f"🗑️  Найдено Reset продаж: {len(all_reset_sales)}\n")
        
        delete_ids = []
        total = 0
        
        print(f"{'ID':<8} {'Customer':<20} {'Ref Code':<12} {'Commission':<12} {'Date':<25}")
        print("-"*100)
        
        for sale in all_reset_sales:
            print(f"{sale.id:<8} {sale.customer_email:<20} {sale.ref_code:<12} {sale.commission_amount:<12.2f} {sale.created_at}")
            delete_ids.append(sale.id)
            total += sale.commission_amount
        
        print("-"*100)
        print(f"\n💰 Итого к удалению: {total:.2f} руб")
        print(f"📊 Всего записей: {len(delete_ids)}\n")
        
        # Группируем по реферам
        query_refs = text("""
            SELECT 
                u.telegram_id,
                u.username,
                u.full_name,
                s.ref_code,
                COUNT(s.id) as sales_count,
                SUM(s.commission_amount) as total_amount
            FROM sales s
            LEFT JOIN users u ON u.ref_code = s.ref_code
            WHERE s.product LIKE '%Reset Auto-Approved%'
            GROUP BY u.telegram_id, u.username, u.full_name, s.ref_code
            ORDER BY total_amount DESC
        """)
        
        result_refs = await session.execute(query_refs)
        referrers = result_refs.fetchall()
        
        print("\n" + "="*100)
        print("👥 РЕФЕРЫ (у которых будут вычтены эти суммы)")
        print("="*100 + "\n")
        
        print(f"{'Telegram ID':<15} {'Username':<20} {'Ref Code':<12} {'Продаж':<10} {'Сумма':<15}")
        print("-"*100)
        
        for ref in referrers:
            username = f"@{ref.username}" if ref.username else "-"
            print(f"{ref.telegram_id:<15} {username:<20} {ref.ref_code:<12} {ref.sales_count:<10} {ref.total_amount:<15.2f}")
        
        print("-"*100)
        print(f"ИТОГО: {len(referrers)} реферов\n")
        
        print("\n" + "="*100)
        print("⚠️  ВАЖНО!")
        print("="*100)
        print("Reset - это НЕ продажа, а обновление бота пользователем.")
        print("Комиссия НЕ должна начисляться за /reset!")
        print("\nСейчас будут удалены ВСЕ Reset продажи из таблицы sales.")
        print("="*100)
        
        print("\nПродолжить? (введи YES для подтверждения): ", end='')
        
        confirmation = input().strip()
        
        if confirmation != "YES":
            print("\n❌ Отменено. Ничего не удалено.\n")
            return
        
        # Удаляем ВСЕ Reset продажи
        print("\n🔄 Удаление ВСЕХ Reset продаж...")
        
        delete_query = text("DELETE FROM sales WHERE id = ANY(:ids)")
        await session.execute(delete_query, {"ids": delete_ids})
        await session.commit()
        
        print(f"✅ Удалено {len(delete_ids)} Reset продаж!\n")
        
        # Проверяем что осталось
        check_query = text("""
            SELECT COUNT(*) as cnt
            FROM sales
            WHERE product LIKE '%Reset Auto-Approved%'
        """)
        
        check_result = await session.execute(check_query)
        remaining = check_result.fetchone()
        
        print(f"📊 Осталось Reset продаж: {remaining.cnt}")
        
        if remaining.cnt == 0:
            print("✅ Все Reset продажи удалены!")
        
        print("\n" + "="*100)
        print("✅ ГОТОВО!")
        print("="*100)
        print(f"💰 Вычтено из начислений реферам: {total:.2f} руб")
        print(f"📊 Баланс пересчитается автоматически (считается из sales)")
        print("\n🔧 Теперь замени reset_command.py на исправленную версию!")
        print("="*100 + "\n")

if __name__ == "__main__":
    asyncio.run(delete_all_reset_sales())
