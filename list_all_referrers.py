#!/usr/bin/env python3
import sys
sys.path.insert(0, '/root/telegram-referral-bot')

import asyncio
from sqlalchemy import text
from app.database.connection import AsyncSessionLocal

async def list_referrers():
    async with AsyncSessionLocal() as session:
        query = text("""
            SELECT 
                u.telegram_id,
                u.username,
                u.full_name,
                u.ref_code,
                COUNT(s.id) as reset_sales,
                SUM(s.commission_amount) as illegal_amount
            FROM sales s
            LEFT JOIN users u ON u.ref_code = s.ref_code
            WHERE s.product LIKE '%Reset Auto-Approved%'
            GROUP BY u.telegram_id, u.username, u.full_name, u.ref_code
            ORDER BY SUM(s.commission_amount) DESC
        """)
        
        result = await session.execute(query)
        referrers = result.fetchall()
        
        print("\nСПИСОК РЕФЕРОВ С НЕЗАКОННЫМИ ЗАРАБОТКАМИ:\n")
        print(f"{'Telegram ID':<15} {'Username':<20} {'Имя':<25} {'Реф код':<12} {'Reset продаж':<15} {'Незаконно начислено':<20}")
        print("="*110)
        
        total = 0
        for r in referrers:
            username = f"@{r.username}" if r.username else "-"
            print(f"{r.telegram_id:<15} {username:<20} {r.full_name:<25} {r.ref_code:<12} {r.reset_sales:<15} {r.illegal_amount:<20.2f}")
            total += r.illegal_amount
        
        print("="*110)
        print(f"\nИТОГО: {len(referrers)} реферов, {total:.2f} руб незаконно начислено\n")

asyncio.run(list_referrers())
