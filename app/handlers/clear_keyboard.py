"""
Команда для очистки reply клавиатур
"""
from aiogram import Router, types
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardRemove, InlineKeyboardMarkup, InlineKeyboardButton

router = Router()

@router.message(Command("clear"))
async def clear_keyboard(message: types.Message):
    """Команда для очистки reply клавиатуры"""
    
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🎛️ Главное меню",
                    callback_data="show_main_menu"
                )
            ]
        ]
    )
    
    await message.answer(
        "🧹 Reply клавиатура очищена! Теперь используются только inline кнопки.",
        reply_markup=ReplyKeyboardRemove()
    )
    
    await message.answer(
        "✅ Интерфейс настроен. Выберите действие:",
        reply_markup=keyboard
    )

def register_clear_handlers(dp):
    """Регистрация хендлеров очистки"""
    dp.include_router(router)
