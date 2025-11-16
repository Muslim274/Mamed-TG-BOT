"""
Хендлер статистики пользователя
"""
from aiogram import Router, types, F
from datetime import datetime, timedelta

from app.database.connection import AsyncSessionLocal
from app.database.crud import UserCRUD, ClickCRUD, SaleCRUD
from app.config import settings
from app.utils.helpers import format_money

router = Router()


@router.message(F.text == "📊 Статистика")
async def show_statistics(message: types.Message):
    """Показ подробной статистики пользователя"""
    user_id = message.from_user.id
    
    async with AsyncSessionLocal() as session:
        user = await UserCRUD.get_user_by_telegram_id(session, user_id)
        
        if not user:
            await message.answer("❌ Ошибка: пользователь не найден")
            return
        
        # Получаем все данные
        clicks_count = await ClickCRUD.count_clicks_by_ref_code(session, user.ref_code)
        sales = await SaleCRUD.get_user_sales(session, user.ref_code)
        
        # Расчеты
        total_sales = len(sales)
        pending_sales = len([s for s in sales if s.status == "pending"])
        confirmed_sales = len([s for s in sales if s.status == "confirmed"])
        cancelled_sales = len([s for s in sales if s.status == "cancelled"])
        
        total_earned = sum(s.commission_amount for s in sales if s.status == "confirmed")
        pending_amount = sum(s.commission_amount for s in sales if s.status == "pending")
        
        # Конверсия
        conversion = (confirmed_sales / clicks_count * 100) if clicks_count > 0 else 0
        
        # Статистика за последние 30 дней
        month_ago = datetime.now() - timedelta(days=30)
        recent_sales = [s for s in sales if s.created_at >= month_ago]
        month_earned = sum(s.commission_amount for s in recent_sales if s.status == "confirmed")
        
        text = f"""
📊 <b>Ваша статистика</b>

👤 <b>Информация о партнере:</b>
├ ID: <code>{user.telegram_id}</code>
├ Реф. код: <code>{user.ref_code}</code>
└ Дата регистрации: {user.created_at.strftime('%d.%m.%Y')}

📈 <b>Общие показатели:</b>
├ 👆 Переходов: {clicks_count}
├ 🛒 Всего продаж: {total_sales}
├ ✅ Подтверждено: {confirmed_sales}
├ ⏳ Ожидает: {pending_sales}
├ ❌ Отменено: {cancelled_sales}
└ 📊 Конверсия: {conversion:.2f}%

💰 <b>Финансы:</b>
├ 💵 Заработано: {format_money(total_earned, settings.CURRENCY)}
├ ⏳ Ожидает подтверждения: {format_money(pending_amount, settings.CURRENCY)}
└ 📅 За последние 30 дней: {format_money(month_earned, settings.CURRENCY)}

🏆 <b>Ваш статус:</b>
{get_partner_status(total_earned)}

📱 Используйте кнопку "Моя ссылка" для получения реферальной ссылки
"""
        
        await message.answer(text, parse_mode="HTML")


def get_partner_status(total_earned: float) -> str:
    """Определение статуса партнера по заработку"""
    if total_earned < 1000:
        return "🥉 Бронзовый партнер (до 1000 {})".format(settings.CURRENCY)
    elif total_earned < 5000:
        return "🥈 Серебряный партнер (1000-5000 {})".format(settings.CURRENCY)
    elif total_earned < 10000:
        return "🥇 Золотой партнер (5000-10000 {})".format(settings.CURRENCY)
    else:
        return "💎 Платиновый партнер (10000+ {})".format(settings.CURRENCY)


def register_stats_handlers(dp: Router):
    """Регистрация хендлеров модуля stats"""
    dp.include_router(router)
