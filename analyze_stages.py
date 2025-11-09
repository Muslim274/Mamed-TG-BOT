#!/usr/bin/env python3
import asyncio
import sys
sys.path.append('/root/telegram-referral-bot')

from app.database.connection import AsyncSessionLocal, init_db
from app.database.models import User, OnboardingStage
from sqlalchemy import select, func, text
from datetime import datetime

async def analyze():
    await init_db()
    
    async with AsyncSessionLocal() as session:
        print("\n📊 СТАТИСТИКА ПО СТАДИЯМ ВОРОНКИ:\n")
        print("-" * 60)
        
        # Общее количество пользователей
        total_result = await session.execute(select(func.count(User.id)))
        total_users = total_result.scalar()
        
        # Статистика по каждой стадии
        stages_info = {
            OnboardingStage.NEW_USER: "Новый пользователь (/start)",
            OnboardingStage.INTRO_SHOWN: "Просмотрел вводное видео",
            OnboardingStage.WAIT_PAYMENT: "Ожидает оплату",
            OnboardingStage.PAYMENT_OK: "Оплата прошла",
            OnboardingStage.WANT_JOIN: "Хочет присоединиться",
            OnboardingStage.READY_START: "Готов начать",
            OnboardingStage.PARTNER_LESSON: "Партнерский урок",
            OnboardingStage.LESSON_DONE: "Завершил урок",
            OnboardingStage.GOT_LINK: "Получил ссылку",
            OnboardingStage.AWAITING_APPROVAL: "Ожидает подтверждения",
            OnboardingStage.COMPLETED: "Завершил онбординг"
        }
        
        for stage, description in stages_info.items():
            result = await session.execute(
                select(func.count(User.id))
                .where(User.onboarding_stage == stage)
            )
            count = result.scalar() or 0
            percentage = (count / total_users * 100) if total_users > 0 else 0
            
            print(f"{stage.value:20s} | {count:6d} | {percentage:6.2f}% | {description}")
        
        print("-" * 60)
        print(f"{'ВСЕГО':20s} | {total_users:6d} | 100.00%")
        
        # Статистика по последним 7 дням
        print("\n📅 НОВЫЕ ПОЛЬЗОВАТЕЛИ ЗА ПОСЛЕДНИЕ 7 ДНЕЙ:")
        print("-" * 40)
        
        result = await session.execute(text("""
            SELECT DATE(created_at) as date, COUNT(*) as count
            FROM users
            WHERE created_at >= CURRENT_DATE - INTERVAL '7 days'
            GROUP BY DATE(created_at)
            ORDER BY date DESC
        """))
        
        for row in result:
            print(f"{row.date}: {row.count} пользователей")
        
        # Конверсия по ключевым этапам
        print("\n🎯 КЛЮЧЕВЫЕ КОНВЕРСИИ:")
        print("-" * 40)
        
        # Из NEW_USER в INTRO_SHOWN
        intro_shown = await session.execute(
            select(func.count(User.id))
            .where(User.onboarding_stage != OnboardingStage.NEW_USER)
        )
        intro_count = intro_shown.scalar() or 0
        intro_conv = (intro_count / total_users * 100) if total_users > 0 else 0
        print(f"Просмотрели видео: {intro_conv:.2f}%")
        
        # До оплаты
        payment_result = await session.execute(
            select(func.count(User.id))
            .where(User.onboarding_stage.in_([
                OnboardingStage.PAYMENT_OK,
                OnboardingStage.WANT_JOIN,
                OnboardingStage.READY_START,
                OnboardingStage.PARTNER_LESSON,
                OnboardingStage.LESSON_DONE,
                OnboardingStage.GOT_LINK,
                OnboardingStage.AWAITING_APPROVAL,
                OnboardingStage.COMPLETED
            ]))
        )
        payment_count = payment_result.scalar() or 0
        payment_conv = (payment_count / total_users * 100) if total_users > 0 else 0
        print(f"Оплатили курс: {payment_conv:.2f}%")
        
        # Завершили онбординг
        completed_result = await session.execute(
            select(func.count(User.id))
            .where(User.onboarding_stage == OnboardingStage.COMPLETED)
        )
        completed_count = completed_result.scalar() or 0
        completed_conv = (completed_count / total_users * 100) if total_users > 0 else 0
        print(f"Завершили онбординг: {completed_conv:.2f}%")

if __name__ == "__main__":
    asyncio.run(analyze())
