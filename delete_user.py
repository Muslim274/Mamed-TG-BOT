#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Скрипт для удаления пользователя из базы данных
"""
import asyncio
import sys
from app.database.connection import AsyncSessionLocal
from app.database.crud import UserCRUD
from sqlalchemy import delete
from app.database.models import User, Sale, Click, Withdrawal, Payment


async def delete_user(telegram_id: int):
    """Удаляет пользователя и все связанные данные"""
    async with AsyncSessionLocal() as session:
        # Получаем пользователя
        user = await UserCRUD.get_user_by_telegram_id(session, telegram_id)

        if not user:
            print(f"Пользователь {telegram_id} не найден в базе данных")
            return False

        print(f"Найден пользователь:")
        print(f"  ID: {user.id}")
        print(f"  Telegram ID: {user.telegram_id}")
        print(f"  Username: {user.username}")
        print(f"  Full name: {user.full_name}")
        print(f"  Ref code: {user.ref_code}")
        print(f"  Stage: {user.onboarding_stage}")

        # Удаляем связанные данные
        print("\nУдаление связанных данных...")

        # Удаляем клики (связаны по ref_code)
        await session.execute(delete(Click).where(Click.ref_code == user.ref_code))
        print("  - Клики удалены")

        # Удаляем продажи (связаны по ref_code)
        await session.execute(delete(Sale).where(Sale.ref_code == user.ref_code))
        print("  - Продажи удалены")

        # Удаляем выводы (связаны по user_id)
        await session.execute(delete(Withdrawal).where(Withdrawal.user_id == user.id))
        print("  - Выводы удалены")

        # Удаляем платежи (связаны по user_id)
        await session.execute(delete(Payment).where(Payment.user_id == user.id))
        print("  - Платежи удалены")

        # Удаляем самого пользователя
        await session.delete(user)
        await session.commit()

        print(f"\nПользователь {telegram_id} полностью удален из базы данных!")
        print("Теперь при /start он будет считаться новым пользователем")
        return True


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Использование: python delete_user.py <telegram_id>")
        print("Пример: python delete_user.py 5403400682")
        sys.exit(1)

    telegram_id = int(sys.argv[1])
    asyncio.run(delete_user(telegram_id))
