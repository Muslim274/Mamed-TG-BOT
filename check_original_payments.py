#!/usr/bin/env python3
"""
Проверяем: есть ли у пользователей ОБЫЧНЫЕ продажи GetCourse ДО reset?
"""
import sys
sys.path.insert(0, '/root/telegram-referral-bot')

import asyncio
from sqlalchemy import text
from app.database.connection import AsyncSessionLocal

async def check_original_payments():
    async with AsyncSessionLocal() as session:
        print("\n" + "="*120)
        print("🔍 ПРОВЕРКА: ЕСТЬ ЛИ ОБЫЧНЫЕ ПРОДАЖИ ДО RESET?")
        print("="*120 + "\n")
        
        # Находим всех кто имеет Reset продажи
        query = text("""
            WITH reset_users AS (
                SELECT DISTINCT customer_email, ref_code
                FROM sales
                WHERE product LIKE '%Reset Auto-Approved%'
            ),
            all_sales AS (
                SELECT 
                    s.customer_email,
                    s.ref_code,
                    s.product,
                    s.commission_amount,
                    s.created_at,
                    CASE 
                        WHEN s.product LIKE '%Reset%' THEN 'RESET'
                        ELSE 'ОБЫЧНАЯ'
                    END as sale_type
                FROM sales s
                INNER JOIN reset_users ru ON s.customer_email = ru.customer_email AND s.ref_code = ru.ref_code
                ORDER BY s.customer_email, s.created_at
            )
            SELECT * FROM all_sales
        """)
        
        result = await session.execute(query)
        all_sales = result.fetchall()
        
        # Группируем по пользователям
        users = {}
        for sale in all_sales:
            key = sale.customer_email
            if key not in users:
                users[key] = {
                    'ref_code': sale.ref_code,
                    'sales': []
                }
            users[key]['sales'].append({
                'type': sale.sale_type,
                'product': sale.product,
                'amount': sale.commission_amount,
                'date': sale.created_at
            })
        
        # Анализируем каждого пользователя
        print(f"{'Customer':<20} {'Ref Code':<12} {'Обычных':<10} {'Reset':<10} {'Вердикт':<50}")
        print("="*120)
        
        total_reset_to_delete = 0
        total_reset_to_keep = 0
        
        for customer, data in users.items():
            normal_sales = [s for s in data['sales'] if s['type'] == 'ОБЫЧНАЯ']
            reset_sales = [s for s in data['sales'] if s['type'] == 'RESET']
            
            # Проверяем: есть ли обычная продажа ДО первого reset?
            if normal_sales:
                first_normal = min(s['date'] for s in normal_sales)
                first_reset = min(s['date'] for s in reset_sales)
                
                if first_normal < first_reset:
                    verdict = "❌ УДАЛИТЬ ВСЕ RESET (была обычная оплата)"
                    total_reset_to_delete += len(reset_sales)
                else:
                    verdict = "⚠️  СТРАННО: reset ДО обычной оплаты!"
                    total_reset_to_delete += len(reset_sales)
            else:
                verdict = "⚠️  НЕТ обычной оплаты! Оставить ПЕРВЫЙ reset?"
                total_reset_to_keep += 1
                total_reset_to_delete += len(reset_sales) - 1
            
            print(f"{customer:<20} {data['ref_code']:<12} {len(normal_sales):<10} {len(reset_sales):<10} {verdict}")
            
            # Детали по датам
            for sale in data['sales']:
                type_icon = "💰" if sale['type'] == 'ОБЫЧНАЯ' else "🔄"
                print(f"  {type_icon} {sale['date']} | {sale['product'][:50]:<50} | {sale['amount']:.2f}")
            print()
        
        print("="*120)
        print(f"\n📊 ИТОГОВАЯ РЕКОМЕНДАЦИЯ:")
        print(f"❌ Reset продаж к удалению: {total_reset_to_delete}")
        print(f"✅ Reset продаж оставить: {total_reset_to_keep}")
        print(f"\n💡 Вывод: {'Удалить ВСЕ reset продажи' if total_reset_to_keep == 0 else 'Удалить reset только у тех, кто платил через GetCourse'}\n")

if __name__ == "__main__":
    asyncio.run(check_original_payments())
