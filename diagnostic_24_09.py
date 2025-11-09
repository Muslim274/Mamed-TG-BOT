#!/usr/bin/env python3
"""
Диагностический скрипт для анализа пользователей за 24.09.2025
Выясняем разницу между "регистрация+оплата в 1 день" и "всего оплат за день"
"""

import os
import sys
import asyncio
from datetime import datetime, timedelta
from typing import List, Dict, Any

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database.connection import AsyncSessionLocal, init_db
from app.database.models import User, Payment, Sale
from sqlalchemy import select, func, and_

async def analyze_date(target_date: str = "2025-09-24"):
    """Подробный анализ пользователей за указанную дату"""
    
    await init_db()
    
    date_obj = datetime.strptime(target_date, '%Y-%m-%d')
    date_start = date_obj.replace(hour=0, minute=0, second=0, microsecond=0)
    date_end = date_start + timedelta(days=1)
    
    print(f"=" * 60)
    print(f"ДИАГНОСТИКА ЗА {target_date}")
    print(f"=" * 60)
    
    async with AsyncSessionLocal() as session:
        
        # 1. Пользователи с payment_completed=True И регистрацией в этот день
        print("\n🔍 1. ОПЛАТИЛИ (РЕГИСТРАЦИЯ+ОПЛАТА В 1 ДЕНЬ)")
        print("-" * 50)
        
        same_day_users = await session.execute(
            select(User.id, User.telegram_id, User.created_at, User.payment_completed)
            .where(
                and_(
                    User.created_at >= date_start,
                    User.created_at < date_end,
                    User.payment_completed == True
                )
            )
            .order_by(User.created_at)
        )
        
        same_day_list = same_day_users.fetchall()
        print(f"Найдено: {len(same_day_list)} пользователей")
        
        for user in same_day_list:
            print(f"  - User ID: {user.id}, Telegram ID: {user.telegram_id}")
            print(f"    Регистрация: {user.created_at}")
            print(f"    Payment completed: {user.payment_completed}")
            print()
        
        # 2. Все платежи Robokassa за этот день
        print("\n🔍 2. ПЛАТЕЖИ ROBOKASSA ЗА ЭТОТ ДЕНЬ")
        print("-" * 50)
        
        try:
            robokassa_payments = await session.execute(
                select(Payment.id, Payment.user_id, Payment.amount, Payment.status, Payment.created_at)
                .where(
                    and_(
                        func.date(Payment.created_at) == date_obj.date(),
                        Payment.status == "paid"
                    )
                )
                .order_by(Payment.created_at)
            )
            
            robokassa_list = robokassa_payments.fetchall()
            print(f"Найдено: {len(robokassa_list)} платежей")
            
            robokassa_user_ids = set()
            for payment in robokassa_list:
                robokassa_user_ids.add(payment.user_id)
                print(f"  - Payment ID: {payment.id}, User ID: {payment.user_id}")
                print(f"    Сумма: {payment.amount}, Статус: {payment.status}")
                print(f"    Дата платежа: {payment.created_at}")
                
                # Получаем информацию о пользователе
                user_info = await session.execute(
                    select(User.telegram_id, User.created_at)
                    .where(User.id == payment.user_id)
                )
                user_data = user_info.fetchone()
                if user_data:
                    print(f"    Telegram ID: {user_data.telegram_id}")
                    print(f"    Дата регистрации: {user_data.created_at}")
                print()
                
        except Exception as e:
            print(f"Ошибка получения Robokassa платежей: {e}")
            robokassa_user_ids = set()
        
        # 3. Все продажи GetCourse за этот день (исправлено)
        print("\n🔍 3. ПРОДАЖИ GETCOURSE ЗА ЭТОТ ДЕНЬ")
        print("-" * 50)
        
        try:
            # Получаем все Sales записи за день
            sales = await session.execute(
                select(Sale)
                .where(func.date(Sale.created_at) == date_obj.date())
                .order_by(Sale.created_at)
            )
            
            sales_list = sales.fetchall()
            print(f"Найдено: {len(sales_list)} продаж")
            
            sales_user_ids = set()
            for sale_row in sales_list:
                sale = sale_row[0] if isinstance(sale_row, tuple) else sale_row
                
                print(f"  - Sale запись:")
                print(f"    ID: {getattr(sale, 'id', 'N/A')}")
                print(f"    Сумма: {getattr(sale, 'amount', 'N/A')}")
                print(f"    Email: {getattr(sale, 'customer_email', 'N/A')}")
                print(f"    Продукт: {getattr(sale, 'product', 'N/A')}")
                print(f"    Дата: {getattr(sale, 'created_at', 'N/A')}")
                
                # Ищем связь с пользователем через email
                customer_email = getattr(sale, 'customer_email', None)
                if customer_email:
                    # Ищем пользователя с таким email в Telegram (если есть поле)
                    # Или другой способ связи
                    print(f"    Попытка найти пользователя по email: {customer_email}")
                    
                    # Пока что не можем точно связать с user_id
                    # Но считаем как дополнительный платеж
                    sales_user_ids.add(f"email_{customer_email}")
                
                print()
                
        except Exception as e:
            print(f"Ошибка получения GetCourse продаж: {e}")
            sales_user_ids = set()
        
        # 4. Анализ различий
        print("\n🔍 4. АНАЛИЗ РАЗЛИЧИЙ")
        print("-" * 50)
        
        same_day_user_ids = set(user.id for user in same_day_list)
        all_payment_user_ids = robokassa_user_ids | sales_user_ids
        
        print(f"Пользователи с регистрацией+оплатой в 1 день: {len(same_day_user_ids)}")
        print(f"User IDs: {same_day_user_ids}")
        print()
        
        print(f"Пользователи, платившие через системы в этот день: {len(all_payment_user_ids)}")
        print(f"User IDs: {all_payment_user_ids}")
        print()
        
        # Кто платил, но не регистрировался в этот день?
        paid_but_not_registered_today = all_payment_user_ids - same_day_user_ids
        if paid_but_not_registered_today:
            print(f"Платили в этот день, но регистрировались раньше: {len(paid_but_not_registered_today)}")
            for user_id in paid_but_not_registered_today:
                user_info = await session.execute(
                    select(User.telegram_id, User.created_at, User.payment_completed)
                    .where(User.id == user_id)
                )
                user_data = user_info.fetchone()
                if user_data:
                    print(f"  - User ID: {user_id}, Telegram ID: {user_data.telegram_id}")
                    print(f"    Дата регистрации: {user_data.created_at}")
                    print(f"    Payment completed: {user_data.payment_completed}")
        else:
            print("Все кто платил в этот день - регистрировались в этот же день")
        
        print()
        
        # Кто регистрировался и имеет payment_completed, но не платил через системы в этот день?
        registered_but_not_paid_today = same_day_user_ids - all_payment_user_ids
        if registered_but_not_paid_today:
            print(f"Регистрировались в этот день с payment_completed=True, но не платили через системы: {len(registered_but_not_paid_today)}")
            for user_id in registered_but_not_paid_today:
                print(f"  - User ID: {user_id} (возможно, мануальная активация)")
        else:
            print("Все кто регистрировался с payment_completed=True - платили через системы")
        
        # 6. Дополнительная проверка: все пользователи с payment_completed=True
        print("\n🔍 6. ВСЕ ПОЛЬЗОВАТЕЛИ С PAYMENT_COMPLETED=TRUE")
        print("-" * 50)
        
        all_paid_users = await session.execute(
            select(User.id, User.telegram_id, User.created_at, User.payment_completed)
            .where(User.payment_completed == True)
            .order_by(User.created_at.desc())
            .limit(20)  # Показываем последних 20
        )
        
        print("Последние 20 пользователей с payment_completed=True:")
        for user in all_paid_users.fetchall():
            print(f"  - User ID: {user.id}, Telegram ID: {user.telegram_id}")
            print(f"    Дата регистрации: {user.created_at}")
            print(f"    Зарегистрирован в {target_date}?: {'ДА' if user.created_at.date() == date_obj.date() else 'НЕТ'}")
            print()
        
        # 7. ТОЧНОЕ ВОСПРОИЗВЕДЕНИЕ ЛОГИКИ ОСНОВНОГО СКРИПТА
        print(f"\n🔍 7. ВОСПРОИЗВОДИМ ЛОГИКУ ОСНОВНОГО СКРИПТА ДЛЯ {target_date}")
        print("-" * 60)
        
        # Точно повторяем логику из основного скрипта
        try:
            # Robokassa платежи (как в основном скрипте)
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
            print(f"Robokassa count (основной скрипт): {robokassa_count}")
            
            # GetCourse продажи (как в основном скрипте)
            sales_payments = await session.execute(
                select(func.count(Sale.id))
                .where(func.date(Sale.created_at) == date_obj.date())
            )
            sales_count = sales_payments.scalar() or 0
            print(f"Sales count (основной скрипт): {sales_count}")
            
            # Итого как в основном скрипте
            total_from_systems = robokassa_count + sales_count
            print(f"Total from systems: {total_from_systems}")
            
            # Проверяем специальную логику для 25.09.2025
            if target_date == "2025-09-25":
                print(f"Специальная логика для 25.09.2025: принудительно 4")
                daily_payments_count = 4
            elif target_date == "2025-09-24":
                print(f"Логика для 24.09.2025: используем total_from_systems = {total_from_systems}")
                daily_payments_count = total_from_systems
            else:
                daily_payments_count = total_from_systems
            
            print(f"ФИНАЛЬНЫЙ РЕЗУЛЬТАТ (как в основном скрипте): {daily_payments_count}")
            
            # Если все еще не сходится, значит проблема в GetCourse
            if daily_payments_count != total_from_systems and target_date != "2025-09-25":
                print("⚠️ Проблема не в специальной логике!")
                
        except Exception as e:
            print(f"Ошибка воспроизведения логики основного скрипта: {e}")
        
        # 8. ДЕТАЛЬНАЯ ПРОВЕРКА SALES
        print(f"\n🔍 8. ДЕТАЛЬНАЯ ПРОВЕРКА ТАБЛИЦЫ SALES ЗА {target_date}")
        print("-" * 60)
        
        try:
            from sqlalchemy import text
            
            # Сырой SQL запрос для точного подсчета
            raw_sales_count = await session.execute(
                text("SELECT COUNT(*) FROM sales WHERE DATE(created_at) = :target_date"),
                {"target_date": date_obj.date()}
            )
            raw_count = raw_sales_count.scalar()
            print(f"Сырой SQL подсчет Sales: {raw_count}")
            
            # Получаем все записи Sales за этот день сырым запросом
            raw_sales_data = await session.execute(
                text("SELECT * FROM sales WHERE DATE(created_at) = :target_date ORDER BY created_at"),
                {"target_date": date_obj.date()}
            )
            raw_sales = raw_sales_data.fetchall()
            
            print(f"Найдено Sales записей сырым запросом: {len(raw_sales)}")
            for i, sale in enumerate(raw_sales):
                print(f"  Sale {i+1}: {dict(sale._mapping)}")
            
            if raw_count > 0:
                print(f"НАЙДЕНА ПРИЧИНА РАСХОЖДЕНИЯ: GetCourse Sales = {raw_count}")
            
        except Exception as e:
            print(f"Ошибка сырого SQL запроса: {e}")
        
        # 9. ИТОГОВАЯ ДИАГНОСТИКА
        print(f"\n🔍 9. ИТОГОВАЯ ДИАГНОСТИКА")
        print("-" * 60)
        
        expected_robokassa = len(robokassa_user_ids)
        expected_sales = len(raw_sales) if 'raw_sales' in locals() else 0
        expected_total = expected_robokassa + expected_sales
        
        print(f"Диагностические результаты:")
        print(f"  - Robokassa платежи: {expected_robokassa}")
        print(f"  - GetCourse продажи: {expected_sales}")  
        print(f"  - Ожидаемый итог: {expected_total}")
        print()
        print(f"Основной скрипт показывает: 4")
        print(f"Расхождение: {4 - expected_total}")
        
        if expected_total == 4:
            print("✅ ПРОБЛЕМА РЕШЕНА: Найден источник 4-го платежа")
        else:
            print("❌ ПРОБЛЕМА ОСТАЕТСЯ: Источник расхождения не найден")

if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else "2025-09-24"
    asyncio.run(analyze_date(target))