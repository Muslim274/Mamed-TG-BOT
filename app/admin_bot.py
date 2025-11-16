"""
Специальный бот для обработки ответов админа в его личном аккаунте
Запускается отдельно для обработки сообщений админа
"""
import asyncio
import logging
from aiogram import Bot, Dispatcher, types, F
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from app.config import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Создаем отдельного бота для админа
admin_bot = Bot(token=settings.BOT_TOKEN)
admin_dp = Dispatcher()

@admin_dp.message(F.from_user.id == settings.ADMIN_ID)
async def admin_reply_handler(message: types.Message):
    """Обработка ответов админа в его личном аккаунте"""
    # Проверяем что это ответ на сообщение
    if not message.reply_to_message:
        return
    
    replied_text = message.reply_to_message.text
    if not replied_text or "🆘 <b>НОВОЕ ОБРАЩЕНИЕ В ПОДДЕРЖКУ</b>" not in replied_text:
        return
    
    try:
        # Извлекаем ID пользователя
        start_marker = "🆔 <b>ID:</b> <code>"
        end_marker = "</code>"
        start_pos = replied_text.find(start_marker)
        
        if start_pos == -1:
            await message.reply("❌ Не найден ID пользователя")
            return
        
        start_pos += len(start_marker)
        end_pos = replied_text.find(end_marker, start_pos)
        user_id = int(replied_text[start_pos:end_pos])
        
        # Ответ пользователю
        user_reply = f"""
💬 <b>Ответ от технической поддержки:</b>

{message.text}

<i>Если у вас остались вопросы, нажмите кнопку ниже</i>
"""
        
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="💬 Задать еще вопрос",
                        callback_data="main_support"
                    )
                ],
                [
                    InlineKeyboardButton(
                        text="🔙 Главное меню",
                        callback_data="show_main_menu"
                    )
                ]
            ]
        )
        
        # Отправляем через основного бота
        await admin_bot.send_message(
            chat_id=user_id,
            text=user_reply,
            parse_mode="HTML",
            reply_markup=keyboard
        )
        
        await message.reply("✅ Ответ отправлен пользователю!")
        logger.info(f"Admin reply sent to user {user_id}")
        
    except Exception as e:
        logger.error(f"Error: {e}")
        await message.reply("❌ Ошибка отправки ответа")

async def run_admin_bot():
    """Запуск админского бота"""
    logger.info("🤖 Admin bot started for handling support replies")
    await admin_dp.start_polling(admin_bot, skip_updates=True)

if __name__ == "__main__":
    asyncio.run(run_admin_bot())
