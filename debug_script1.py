#!/usr/bin/env python3
"""
Анализ временных полей для определения даты активации payment_completed
"""

import os
import sys
import asyncio
from datetime import datetime, timedelta

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database.connection import AsyncSessionLocal, init_db
from app.database.models import User
from sqlalchemy import select, text

async def analyze_time_fields():
    """Анализируем какие временные поля есть в User и как они ведут себя"""
    
    await init_db()
    
    print("=" * 80)
    print("АНАЛИЗ ВРЕМЕННЫХ ПОЛЕЙ ТАБЛИЦЫ USERS")
    print("=" * 80)
    
    async with AsyncSessionLocal() as session:
        
        # 1. Получаем структуру таблицы users
        print("\n1. СТРУКТУРА ТАБЛИЦЫ USERS")
        print("-" * 60)
        
        try:
            columns_query = await session.execute(
                text("""
                SELECT column_name, data_type, is_nullable 
                FROM information_schema.columns 
                WHERE table_name = 'users' AND table_schema = 'public'
                ORDER BY ordinal_position
                """)
            )
            columns = columns_query.fetchall()
            
            time_columns = []
            for col in columns:
                print(f"  {col[0]:25} | {col[1]:20} | nullable: {col[2]}")
                if 'time' in col[1].lower() or col[0].endswith('_at'):
                    time_columns.append(col[0])
            
            print(f"\nВременные поля: {time_columns}")
            
        except Exception as e:
            print(f"Ошибка получения структуры: {e}")
            return
        
        # 2. Анализируем пользователей с payment_completed=True
        print(f"\n2. АНАЛИЗ ПОЛЬЗОВАТЕЛЕЙ С PAYMENT_COMPLETED=TRUE")
        print("-" * 60)
        
        # Получаем всех пользователей с payment_completed=True
        paid_users = await session.execute(
            select(User.id, User.telegram_id, User.created_at, User.payment_completed)
            .where(User.payment_completed == True)
            .order_by(User.created_at.desc())
            .limit(10)
        )
        
        paid_users_list = paid_users.fetchall()
        print(f"Найдено пользователей с payment_completed=True: {len(paid_users_list)}")
        print("\nПоследние 10:")
        
        for user in paid_users_list:
            print(f"  User {user.telegram_id}: created_at = {user.created_at}")
        
        # 3. Проверяем наличие updated_at или других полей
        print(f"\n3. ПРОВЕРКА ДОПОЛНИТЕЛЬНЫХ ВРЕМЕННЫХ ПОЛЕЙ")
        print("-" * 60)
        
        # Пробуем найти поле updated_at
        try:
            updated_at_query = await session.execute(
                text("SELECT column_name FROM information_schema.columns WHERE table_name = 'users' AND column_name LIKE '%updated%'")
            )
            updated_columns = [row[0] for row in updated_at_query.fetchall()]
            print(f"Поля с 'updated': {updated_columns}")
            
            if updated_columns:
                print("Поле updated_at найдено!")
                
                # Анализируем несколько пользователей
                sample_query = await session.execute(
                    text(f"""
                    SELECT telegram_id, created_at, {updated_columns[0]}, payment_completed 
                    FROM users 
                    WHERE payment_completed = true 
                    ORDER BY created_at DESC 
                    LIMIT 5
                    """)
                )
                
                samples = sample_query.fetchall()
                print("\nСравнение created_at и updated_at:")
                for sample in samples:
                    print(f"  User {sample[0]}:")
                    print(f"    created_at:  {sample[1]}")
                    print(f"    updated_at:  {sample[2]}")
                    print(f"    difference:  {sample[2] - sample[1] if sample[2] and sample[1] else 'N/A'}")
                    print()
                    
            else:
                print("Поле updated_at НЕ найдено")
        
        except Exception as e:
            print(f"Ошибка проверки updated_at: {e}")
        
        # 4. Ищем другие поля активации
        print(f"\n4. ПОИСК ПОЛЕЙ АКТИВАЦИИ ПЛАТЕЖЕЙ")
        print("-" * 60)
        
        activation_fields = []
        try:
            activation_query = await session.execute(
                text("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'users' 
                AND (column_name LIKE '%payment%' OR column_name LIKE '%activated%' OR column_name LIKE '%completed%')
                """)
            )
            activation_fields = [row[0] for row in activation_query.fetchall()]
            print(f"Поля связанные с активацией: {activation_fields}")
            
        except Exception as e:
            print(f"Ошибка поиска полей активации: {e}")
        
        # 5. Анализируем конкретные проблемные даты
        print(f"\n5. АНАЛИЗ КОНКРЕТНЫХ ДАТ")
        print("-" * 60)
        
        target_dates = ["2025-09-24", "2025-09-25"]
        
        for date_str in target_dates:
            print(f"\nДата: {date_str}")
            date_obj = datetime.strptime(date_str, '%Y-%m-%d')
            date_start = date_obj.replace(hour=0, minute=0, second=0, microsecond=0)
            date_end = date_start + timedelta(days=1)
            
            # Пользователи зарегистрированные в этот день с payment_completed=True
            same_day = await session.execute(
                select(func.count(User.id))
                .where(
                    and_(
                        User.created_at >= date_start,
                        User.created_at < date_end,
                        User.payment_completed == True
                    )
                )
            )
            same_day_count = same_day.scalar()
            
            print(f"  Зарегистрированные + оплатившие: {same_day_count}")
            
            # Если есть updated_at, проверим активированных в этот день
            if updated_columns:
                try:
                    updated_day = await session.execute(
                        text(f"""
                        SELECT COUNT(*) FROM users 
                        WHERE DATE({updated_columns[0]}) = :target_date 
                        AND payment_completed = true
                        """),
                        {"target_date": date_obj.date()}
                    )
                    updated_count = updated_day.scalar()
                    print(f"  Активированные в этот день (updated_at): {updated_count}")
                    
                except Exception as e:
                    print(f"  Ошибка подсчета по updated_at: {e}")
        
        # 6. Рекомендации
        print(f"\n6. РЕКОМЕНДАЦИИ")
        print("-" * 60)
        
        if updated_columns:
            print("✅ Можно использовать поле updated_at для дневной разбивки")
            print("   Логика: WHERE DATE(updated_at) = target_date AND payment_completed = true")
        else:
            print("❌ Нет подходящего поля для дневной разбивки активаций")
            print("   Варианты решения:")
            print("   1. Добавить поле payment_activated_at")
            print("   2. Использовать только созданные платежи (Robokassa + GetCourse)")
            print("   3. Игнорировать мануальные активации в дневной статистике")

if __name__ == "__main__":
    asyncio.run(analyze_time_fields())