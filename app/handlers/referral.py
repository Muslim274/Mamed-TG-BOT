"""
Хендлер для работы с реферальными ссылками
"""
from aiogram import Router, types, F
from aiogram.fsm.context import FSMContext

from app.database.connection import AsyncSessionLocal
from app.database.crud import UserCRUD
from app.keyboards.inline import get_referral_menu
from app.config import settings

router = Router()


@router.message(F.text == "💰 Моя ссылка")
async def get_referral_link(message: types.Message):
    """Получение реферальной ссылки"""
    user_id = message.from_user.id
    
    async with AsyncSessionLocal() as session:
        user = await UserCRUD.get_user_by_telegram_id(session, user_id)
        
        if not user:
            await message.answer("❌ Ошибка: пользователь не найден")
            return
        
        # Генерируем ссылки
        telegram_link = f"https://t.me/{settings.BOT_USERNAME}?start={user.ref_code}"
        tracking_link = f"{settings.DOMAIN}/track/{user.ref_code}"
        
        text = f"""
🔗 <b>Ваши реферальные ссылки:</b>

<b>Прямая ссылка на бот:</b>
<code>{telegram_link}</code>

<b>Трекинговая ссылка (с переходом на лендинг):</b>
<code>{tracking_link}</code>

📋 Нажмите на ссылку, чтобы скопировать её.

💡 <b>Совет:</b> Используйте трекинговую ссылку для размещения в соцсетях и на сайтах - она позволит отследить все переходы и покупки!
"""
        
        await message.answer(
            text,
            parse_mode="HTML",
            reply_markup=get_referral_menu(user.ref_code)
        )


@router.callback_query(F.data.startswith("copy_link:"))
async def copy_link_handler(callback: types.CallbackQuery):
    """Обработка копирования ссылки"""
    ref_code = callback.data.split(":")[1]
    link = f"{settings.DOMAIN}/track/{ref_code}"
    
    await callback.answer(
        "✅ Ссылка скопирована в буфер обмена!",
        show_alert=True
    )


@router.callback_query(F.data.startswith("link_stats:"))
async def link_stats_handler(callback: types.CallbackQuery):
    """Показ статистики по ссылке"""
    ref_code = callback.data.split(":")[1]
    
    async with AsyncSessionLocal() as session:
        from app.database.crud import ClickCRUD, SaleCRUD
        
        clicks_count = await ClickCRUD.count_clicks_by_ref_code(session, ref_code)
        sales = await SaleCRUD.get_user_sales(session, ref_code)
        
        total_sales = len(sales)
        confirmed_sales = len([s for s in sales if s.status == "confirmed"])
        total_earned = sum(s.commission_amount for s in sales if s.status == "confirmed")
        
        text = f"""
📊 <b>Статистика вашей реферальной ссылки:</b>

👆 Переходов: {clicks_count}
🛒 Всего продаж: {total_sales}
✅ Подтвержденных продаж: {confirmed_sales}
💰 Заработано: {total_earned:.2f} {settings.CURRENCY}

🔄 Обновлено: только что
"""
        
        await callback.message.edit_text(
            text,
            parse_mode="HTML",
            reply_markup=get_referral_menu(ref_code)
        )
    
    await callback.answer()


def register_referral_handlers(dp: Router):
    """Регистрация хендлеров модуля referral"""
    dp.include_router(router)
