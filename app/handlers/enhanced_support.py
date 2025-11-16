"""
Упрощенная система поддержки
app/handlers/enhanced_support.py
"""
import logging
from aiogram import Router, types, F
from app.config import settings

logger = logging.getLogger(__name__)
router = Router()

# Простой класс-заглушка для совместимости с импортом в bot.py
class SimpleSupportHandler:
    def __init__(self):
        self.admin_id = None

# Глобальный экземпляр для совместимости
enhanced_support = SimpleSupportHandler()

# Текст сообщения поддержки
SUPPORT_MESSAGE = """👨‍💼 <b>Техническая поддержка</b>

💬 Напиши прямо сюда в чат нашему администратору нажав прямо на его ник

🧔🏻 Мужчинам ➡️ @azizmuhammad18 ⬅️
🧕 Женщинам ➡️ @adm_zarina53 ⬅️

Мы тебе скоро ответим 🙌"""

# Список callback'ов для поддержки
SUPPORT_CALLBACKS = [
    "main_support", "ask_question_help", "payment_help", "contact_support"
]

@router.callback_query(F.data.in_(SUPPORT_CALLBACKS))
async def show_support_message_callback(callback: types.CallbackQuery):
    """Показ сообщения поддержки при нажатии на кнопки"""
    await callback.message.answer(SUPPORT_MESSAGE, parse_mode="HTML")
    await callback.answer()

@router.message(
    ~F.text.startswith('/'),                    # Исключаем команды
    ~F.from_user.id.in_([settings.ADMIN_ID]),   # Исключаем админа
    ~F.text.in_(['m_video_unikal'])             # Исключаем спец.фразы
)
async def handle_any_user_message(message: types.Message):
    """Обработка любого сообщения пользователя - показываем контакты поддержки"""
    await message.answer(SUPPORT_MESSAGE, parse_mode="HTML")

def register_enhanced_support_handlers(dp):
    """Регистрация handlers для поддержки"""
    dp.include_router(router)