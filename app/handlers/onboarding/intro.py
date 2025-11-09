"""
Упрощенный хэндлер вводного видео
"""
import logging
from aiogram import Router, types, F

from app.database.connection import AsyncSessionLocal
from app.database.crud import UserCRUD
from app.database.models import OnboardingStage
from app.middlewares.onboarding_check import OnboardingStageMiddleware
from app.utils.constants import ONBOARDING_TEXTS
from app.helpers.stage_helper import StageUpdateHelper
from app.config import settings
from app.handlers.onboarding.payment import get_integrated_payment_keyboard



logger = logging.getLogger(__name__)

router = Router()
router.message.middleware(
    OnboardingStageMiddleware(
        allowed_stages=[OnboardingStage.NEW_USER, OnboardingStage.INTRO_SHOWN]
    )
)
router.callback_query.middleware(
    OnboardingStageMiddleware(
        allowed_stages=[
            OnboardingStage.NEW_USER,
            OnboardingStage.INTRO_SHOWN,
            OnboardingStage.WAIT_PAYMENT,
        ]
    )
)

def get_intro_keyboard():
    """Упрощенная клавиатура после просмотра вводного видео"""
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="📚 Получить урок",
                    callback_data="intro_continue"
                )
            ]
        ]
    )
    return keyboard

@router.callback_query(F.data == "intro_continue")
async def intro_continue(callback: types.CallbackQuery, onboarding_user):
    logger.info("User %s continuing after intro - showing INTEGRATED payment options", callback.from_user.id)
    
    price = settings.ONBOARDING_COURSE_PRICE
    formatted_amount = f"{price:,.0f}".replace(",", "\u202F") + f" {settings.ONBOARDING_COURSE_CURRENCY}"

    payment_text = f"""
📚 <b>Урок «Инструкция партнерской системы»</b>

💡 <b>Бонус:</b>
• Место в команде Мамеда 🧑‍💻
• Поддержка команды 💪

<b>Стоимость: {formatted_amount}</b>


<i><b>Внимание!</b> Оплата по частям не относится к нашей программе т.к. противоречат нашим религиозным принципам! Мы принимаем оплату только полной стоимости продукта ✅</i>

"""

    try:
        # ВАЖНО: Обновляем стадию пользователя ДО показа клавиатуры!
        async with AsyncSessionLocal() as session:
            await StageUpdateHelper.update_user_stage(session, callback.from_user.id, OnboardingStage.WAIT_PAYMENT, callback.bot)
            await session.commit()
            logger.info(f"✅ Пользователь {callback.from_user.id} переведен в стадию WAIT_PAYMENT")
        
        # Создаем платеж через Robokassa
        payment_url = None
        if not settings.ONBOARDING_MOCK_PAYMENT:
            try:
                from app.services.robokassa_handler import robokassa_handler
                payment_url, invoice_id = await robokassa_handler.create_payment(
                    user_id=callback.from_user.id,
                    amount=settings.ONBOARDING_COURSE_PRICE,
                    description="Онбординг курс партнерской программы"
                )
                logger.info(f"✅ Robokassa payment created: {invoice_id}")
            except Exception as e:
                logger.error(f"❌ Error creating Robokassa payment: {e}")

        keyboard = get_integrated_payment_keyboard(payment_url)

        await callback.message.answer(
            payment_text, 
            parse_mode="HTML", 
            reply_markup=keyboard
        )
        await callback.answer("🚀 Выберите способ оплаты!")
        
    except Exception as e:
        logger.error("Error in intro_continue: %s", e, exc_info=True)
        await callback.answer("❌ Произошла ошибка", show_alert=True)