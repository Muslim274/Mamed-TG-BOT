"""
Хендлер /start для завершивших онбординг - только inline меню
"""
from aiogram import Router, types, Dispatcher
from aiogram.filters import CommandStart
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardRemove

from app.database.connection import AsyncSessionLocal
from app.database.crud import UserCRUD
from app.middlewares.onboarding_check import OnboardingStageMiddleware
from app.database.models import OnboardingStage
from app.config import settings

# Создаем роутер только для завершивших онбординг
router = Router()
router.message.middleware(OnboardingStageMiddleware(completed_only=True))

@router.message(CommandStart())
async def start_completed_user(message: types.Message):
    """Start для завершивших онбординг - показываем inline меню"""
    telegram_id = message.from_user.id
    
    try:
        async with AsyncSessionLocal() as session:
            user = await UserCRUD.get_user_by_telegram_id(session, telegram_id)
        
        if not user:
            await message.answer("❌ Ошибка получения данных пользователя")
            return
        
        welcome_text = f"""
👋 Добро пожаловать, {message.from_user.full_name}!

💼 <b>Ваш статус:</b> Активный партнер
🔗 <b>Ваш код:</b> <code>{user.ref_code}</code>
💰 <b>Комиссия:</b> {settings.COMMISSION_PERCENT}% с продаж
"""
        
        # Только inline кнопка
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="🎛️ Открыть главное меню",
                        callback_data="show_main_menu"
                    )
                ]
            ]
        )
        
        # Убираем reply кнопки и показываем inline
        await message.answer("🔄 Очищаем интерфейс...", reply_markup=ReplyKeyboardRemove())
        await message.answer(welcome_text, parse_mode="HTML", reply_markup=keyboard)
    
    except Exception as e:
        await message.answer("🔄 Произошла ошибка. Попробуйте еще раз.")

def register_start_handlers(dp: Dispatcher):
    dp.include_router(router)
