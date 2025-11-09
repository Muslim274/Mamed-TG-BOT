#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Скрипт для завершения онбординга пользователя
Переводит пользователя в стадию COMPLETED
"""
import asyncio
import sys
from app.database.connection import AsyncSessionLocal
from app.database.crud import UserCRUD
from app.database.models import OnboardingStage


async def complete_user(telegram_id: int):
    """Завершает онбординг пользователя"""
    async with AsyncSessionLocal() as session:
        # Получаем пользователя
        user = await UserCRUD.get_user_by_telegram_id(session, telegram_id)

        if not user:
            print(f"❌ Пользователь {telegram_id} не найден!")
            return False

        print(f"Текущая стадия: {user.onboarding_stage}")

        # Обновляем стадию на COMPLETED
        user.onboarding_stage = OnboardingStage.COMPLETED
        user.payment_completed = True

        session.add(user)
        await session.commit()

        print(f"✅ Пользователь {telegram_id} переведен в стадию COMPLETED!")
        print(f"Теперь при /start он увидит главное меню")
        return True


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Использование: python complete_user_onboarding.py <telegram_id>")
        print("Пример: python complete_user_onboarding.py 5403400682")
        sys.exit(1)

    telegram_id = int(sys.argv[1])
    asyncio.run(complete_user(telegram_id))
