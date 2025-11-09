"""
Сервис отправки уведомлений
"""
import logging
from aiogram import Bot

from app.config import settings
from app.database.connection import AsyncSessionLocal
from app.database.crud import UserCRUD
from app.utils.helpers import format_money

logger = logging.getLogger(__name__)


async def send_sale_notification(ref_code: str, amount: float, commission: float):
    """Отправка уведомления о новой продаже"""
    bot = Bot(token=settings.BOT_TOKEN)
    
    try:
        async with AsyncSessionLocal() as session:
            user = await UserCRUD.get_user_by_ref_code(session, ref_code)
            
            if user:
                text = f"""
🎉 <b>Новая продажа!</b>

💰 Сумма продажи: {format_money(amount, settings.CURRENCY)}
💵 Ваша комиссия: {format_money(commission, settings.CURRENCY)}

Продажа уже подтверждена и добавлена к вашему балансу!

📊 Посмотреть статистику: /stats
💸 Вывести средства: /withdraw
"""
                
                await bot.send_message(
                    user.telegram_id,
                    text,
                    parse_mode="HTML"
                )
                logger.info(f"Sale notification sent to user {user.telegram_id}")
                
    except Exception as e:
        logger.error(f"Error sending sale notification: {e}")
    finally:
        await bot.session.close()


async def send_payment_notification(user_id: int, amount: float, status: str, description: str = ""):
    """Уведомление об изменении статуса платежа"""
    bot = Bot(token=settings.BOT_TOKEN)
    
    try:
        if status == "paid":
            text = f"""
✅ <b>Платеж успешно выполнен!</b>

💰 Сумма: {format_money(amount, settings.CURRENCY)}
📦 Описание: {description}

Спасибо за оплату! 🙏

📊 Если это была покупка по реферальной ссылке, комиссия уже начислена вашему рефереру.
"""
        elif status == "failed":
            text = f"""
❌ <b>Платеж не прошел</b>

💰 Сумма: {format_money(amount, settings.CURRENCY)}
📦 Описание: {description}

Возможные причины:
• Недостаточно средств на карте
• Карта заблокирована банком
• Технические проблемы

💡 Попробуйте еще раз или обратитесь в поддержку: {settings.SUPPORT_CONTACT}
"""
        else:
            return  # Для других статусов не отправляем уведомления
        
        await bot.send_message(user_id, text, parse_mode="HTML")
        logger.info(f"Payment notification sent to user {user_id}, status: {status}")
        
    except Exception as e:
        logger.error(f"Error sending payment notification: {e}")
    finally:
        await bot.session.close()


async def send_withdrawal_notification(user_id: int, amount: float, status: str):
    """Уведомление об изменении статуса выплаты"""
    bot = Bot(token=settings.BOT_TOKEN)
    
    try:
        if status == "completed":
            text = f"""
✅ <b>Выплата завершена!</b>

💰 Сумма: {format_money(amount, settings.CURRENCY)} успешно отправлена на ваши реквизиты.

Спасибо за работу с нами! 🤝

💡 Продолжайте привлекать клиентов и зарабатывать еще больше!
"""
        elif status == "rejected":
            text = f"""
❌ <b>Выплата отклонена</b>

💰 Сумма: {format_money(amount, settings.CURRENCY)}

Пожалуйста, свяжитесь с поддержкой для выяснения причин: {settings.SUPPORT_CONTACT}

Возможные причины:
• Неверные реквизиты
• Технические проблемы
• Нарушение условий программы
"""
        else:
            return
        
        await bot.send_message(user_id, text, parse_mode="HTML")
        logger.info(f"Withdrawal notification sent to user {user_id}, status: {status}")
        
    except Exception as e:
        logger.error(f"Error sending withdrawal notification: {e}")
    finally:
        await bot.session.close()


async def send_admin_notification(message: str):
    """Отправка уведомления администратору"""
    # TODO: Добавить ADMIN_ID в настройки
    ADMIN_ID = 123456789  # Замените на реальный ID администратора
    
    bot = Bot(token=settings.BOT_TOKEN)
    
    try:
        await bot.send_message(ADMIN_ID, f"🔔 <b>Уведомление:</b>\n\n{message}", parse_mode="HTML")
        logger.info("Admin notification sent")
    except Exception as e:
        logger.error(f"Error sending admin notification: {e}")
    finally:
        await bot.session.close()