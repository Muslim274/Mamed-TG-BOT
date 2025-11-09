"""
ОТЛАДОЧНАЯ версия support.py для быстрого исправления Reply
app/handlers/support.py
"""
import logging
from aiogram import Router, types, F
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from datetime import datetime
import re

from app.database.connection import AsyncSessionLocal
from app.database.crud import UserCRUD
from app.database.models import OnboardingStage
from app.config import settings

logger = logging.getLogger(__name__)
router = Router()

# ID админа
ADMIN_ID = settings.ADMIN_ID

# Хранилище связей
admin_message_to_user = {}
user_last_message_time = {}

@router.message(F.text == "/admin_fix")
async def fix_admin_status(message: types.Message):
    """Исправить статус админа"""
    if message.from_user.id != ADMIN_ID:
        return
        
    try:
        async with AsyncSessionLocal() as session:
            await UserCRUD.update_onboarding_stage(session, ADMIN_ID, OnboardingStage.COMPLETED)
        
        await message.answer("🔧 Статус админа исправлен!")
        logger.info(f"🔧 Fixed admin status for {ADMIN_ID}")
        
    except Exception as e:
        await message.answer("❌ Ошибка исправления статуса")
        logger.error(f"❌ Error fixing admin status: {e}")

@router.callback_query(F.data == "main_support")
async def support_menu(callback: types.CallbackQuery):
    """Открытие меню поддержки"""
    logger.info(f"User {callback.from_user.id} opened support menu")
    
    support_text = """
👨‍💼 <b>Техническая поддержка</b>

💬 Напиши прямо сюда в чат свой вопрос как тебе удобно: можешь текстом, можешь голосовым, можешь прикрепить скриншот. 

🔔 <b>Все твои сообщения будут переданы в поддержку</b>

Мы тебе скоро ответим 🙌
"""
    
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🔙 Назад в главное меню",
                    callback_data="show_main_menu"
                )
            ]
        ]
    )
    
    try:
        await callback.message.edit_text(support_text, parse_mode="HTML", reply_markup=keyboard)
    except:
        await callback.message.answer(support_text, parse_mode="HTML", reply_markup=keyboard)
    
    await callback.answer()

@router.message(~F.text.startswith('/'))
async def handle_user_messages(message: types.Message):
    """
    Обработка сообщений пользователей
    """
    user_id = message.from_user.id
    
    # 🔍 ОТЛАДКА: Логируем ВСЕ входящие сообщения
    logger.info(f"🔥 INCOMING MESSAGE: user_id={user_id}, is_admin={user_id == ADMIN_ID}, text='{message.text[:50] if message.text else '[media]'}'")
    
    # Пропускаем админа ТОЛЬКО если это НЕ Reply
    if user_id == ADMIN_ID and not message.reply_to_message:
        logger.debug(f"🚫 Ignoring non-reply message from admin {user_id}")
        return
    
    logger.info(f"📨 Processing message from user {user_id}: {message.text[:50] if message.text else '[media]'}")
    
    try:
        # Получаем информацию о пользователе
        async with AsyncSessionLocal() as session:
            user = await UserCRUD.get_user_by_telegram_id(session, user_id)
        
        user_info = f"@{message.from_user.username}" if message.from_user.username else "Без username"
        current_time = datetime.now().strftime("%d.%m.%Y %H:%M")
        
        if user:
            user_stage = user.onboarding_stage
            stage_text = "Завершенный онбординг" if user_stage == OnboardingStage.COMPLETED else f"Онбординг: {user_stage}"
            ref_code = user.ref_code
        else:
            stage_text = "Новый пользователь"
            ref_code = "Не найден"
        
        # Отправляем админу В ТОГО ЖЕ БОТА
        await send_to_admin_in_bot(
            message=message,
            user_id=user_id,
            user_name=message.from_user.full_name,
            user_info=user_info,
            ref_code=ref_code,
            stage_text=stage_text,
            current_time=current_time
        )
        
        # Уведомляем пользователя
        current_time_obj = datetime.now()
        should_notify = False
        
        if user_id not in user_last_message_time:
            should_notify = True
        else:
            time_diff = (current_time_obj - user_last_message_time[user_id]).total_seconds()
            if time_diff >= 1800:  # 30 минут
                should_notify = True
        
        if should_notify:
            await message.answer("✅ Сейчас ответим тебе..")
            user_last_message_time[user_id] = current_time_obj
            logger.info(f"✅ Sent notification to user {user_id}")
        
        logger.info(f"✅ Message from user {user_id} sent to admin in bot")
        
    except Exception as e:
        logger.error(f"❌ Error processing user message: {e}", exc_info=True)
        await message.answer("❌ Ошибка отправки сообщения. Попробуйте позже.")

async def send_to_admin_in_bot(message: types.Message, user_id: int, user_name: str, 
                               user_info: str, ref_code: str, stage_text: str, current_time: str):
    """
    Отправка сообщения админу В ТОМ ЖЕ БОТЕ
    """
    try:
        # Формируем сообщение для админа
        admin_text = f"""
💬 <b>СООБЩЕНИЕ ОТ ПОЛЬЗОВАТЕЛЯ</b>

👤 <b>Имя:</b> {user_name}
🆔 <b>ID:</b> <code>{user_id}</code>
🅰 <b>Username:</b> {user_info}
🔗 <b>Реф. код:</b> {ref_code}
⏰ <b>Время:</b> {current_time}
🎯 <b>Стадия:</b> {stage_text}

💬 <b>Сообщение:</b>
{message.text or '[медиа-файл]'}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📝 <b>ДЛЯ ОТВЕТА:</b> Нажмите Reply на это сообщение ⬆️
🔄 User ID: <code>{user_id}</code>
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""
        
        # Отправляем админу в бот
        admin_msg = await message.bot.send_message(
            chat_id=ADMIN_ID,
            text=admin_text,
            parse_mode="HTML"
        )
        
        # Сохраняем связь
        admin_message_to_user[admin_msg.message_id] = user_id
        
        # 🔍 ОТЛАДКА: Логируем сохранение связи
        logger.info(f"🔗 SAVED LINK: admin_msg_id={admin_msg.message_id} -> user_id={user_id}")
        logger.info(f"🔗 CURRENT LINKS: {list(admin_message_to_user.keys())}")
        
        # Если есть медиа - отправляем отдельно
        if message.photo:
            media_msg = await message.bot.send_photo(
                chat_id=ADMIN_ID,
                photo=message.photo[-1].file_id,
                caption=f"📸 Фото от пользователя {user_id}"
            )
            admin_message_to_user[media_msg.message_id] = user_id
            
        elif message.voice:
            media_msg = await message.bot.send_voice(
                chat_id=ADMIN_ID,
                voice=message.voice.file_id,
                caption=f"🎤 Голосовое от пользователя {user_id}"
            )
            admin_message_to_user[media_msg.message_id] = user_id
            
        logger.info(f"✅ Admin notification sent, message_id: {admin_msg.message_id}")
        
    except Exception as e:
        logger.error(f"❌ Error sending to admin: {e}", exc_info=True)

# 🔍 ОТЛАДОЧНЫЙ HANDLER: Логируем ВСЕ сообщения от админа
@router.message(F.from_user.id == ADMIN_ID)
async def debug_admin_messages(message: types.Message):
    """
    ОТЛАДКА: Логируем все сообщения от админа + УНИВЕРСАЛЬНЫЙ ОТВЕТ
    """
    logger.info(f"🔥 ADMIN MESSAGE RECEIVED!")
    logger.info(f"   user_id: {message.from_user.id}")
    logger.info(f"   chat_id: {message.chat.id}")
    logger.info(f"   text: '{message.text}'")
    logger.info(f"   reply_to_message: {message.reply_to_message is not None}")
    
    if message.reply_to_message:
        logger.info(f"   reply_to_message_id: {message.reply_to_message.message_id}")
        logger.info(f"   reply_to_text: '{message.reply_to_message.text[:100] if message.reply_to_message.text else '[no text]'}'")
        
        # Переходим к обработке Reply
        await handle_admin_reply(message)
    else:
        logger.info(f"   ℹ️ Not a reply message - trying universal handler")
        
        # 🆕 УНИВЕРСАЛЬНЫЙ HANDLER: Ищем последнего пользователя
        if admin_message_to_user:
            # Берем последнего пользователя (самое недавнее сообщение)
            last_message_id = max(admin_message_to_user.keys())
            last_user_id = admin_message_to_user[last_message_id]
            
            logger.info(f"🎯 Using universal handler: last_user_id={last_user_id}")
            
            # Отправляем как универсальный ответ
            await send_universal_reply(message, last_user_id)
        else:
            logger.warning("⚠️ No recent users found for universal reply")
            await message.reply(
                "⚠️ <b>Нет активных диалогов</b>\n\n"
                "Для ответа пользователю:\n"
                "1. Дождитесь сообщения от пользователя\n"
                "2. Нажмите Reply на сообщение от бота\n"
                "3. Напишите ответ",
                parse_mode="HTML"
            )

async def handle_admin_reply(message: types.Message):
    """
    Обработка Reply от админа
    """
    replied_message_id = message.reply_to_message.message_id
    
    logger.info(f"🔥 ADMIN REPLY HANDLER TRIGGERED!")
    logger.info(f"   replied_to_message_id: {replied_message_id}")
    logger.info(f"   available_links: {list(admin_message_to_user.keys())}")
    
    # Ищем пользователя
    user_id = admin_message_to_user.get(replied_message_id)
    
    if not user_id:
        logger.warning(f"⚠️ No user_id found for message_id {replied_message_id}")
        
        # Пытаемся найти в тексте
        replied_text = message.reply_to_message.text or ""
        logger.info(f"🔍 Searching in replied text: '{replied_text[:200]}'")
        
        id_match = re.search(r'🆔 <b>ID:</b> <code>(\d+)</code>', replied_text)
        if id_match:
            user_id = int(id_match.group(1))
            logger.info(f"✅ Found user_id via regex: {user_id}")
        else:
            # Альтернативный поиск
            id_match = re.search(r'User ID: <code>(\d+)</code>', replied_text)
            if id_match:
                user_id = int(id_match.group(1))
                logger.info(f"✅ Found user_id via regex (alt): {user_id}")
    else:
        logger.info(f"✅ Found user_id via direct link: {user_id}")
    
    if not user_id:
        logger.error(f"❌ Could not determine user_id!")
        await message.reply(
            "❌ Не удалось определить пользователя.\n\n"
            f"🔍 Отладка:\n"
            f"• replied_to_message_id: {replied_message_id}\n"
            f"• available_links: {list(admin_message_to_user.keys())}\n"
            f"• text_preview: {(message.reply_to_message.text or '')[:100]}"
        )
        return
    
    try:
        logger.info(f"💬 Sending reply to user {user_id}")
        
        # Проверяем пользователя в БД
        async with AsyncSessionLocal() as session:
            user = await UserCRUD.get_user_by_telegram_id(session, user_id)
            if not user:
                await message.reply(f"❌ Пользователь {user_id} не найден в базе данных")
                return
            
            user_stage = user.onboarding_stage
        
        # Формируем ответ
        response_text = f"""💬 <b>Ответ от поддержки:</b>

{message.text or '[медиа-файл]'}"""
        
        # Определяем кнопки
        keyboard = None
        if user_stage == OnboardingStage.COMPLETED:
            keyboard = InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        InlineKeyboardButton(
                            text="🔙 Главное меню",
                            callback_data="show_main_menu"
                        )
                    ]
                ]
            )
        
        # Отправляем ответ пользователю
        await message.bot.send_message(
            chat_id=user_id,
            text=response_text,
            parse_mode="HTML",
            reply_markup=keyboard
        )
        
        # Сбрасываем таймер уведомлений
        if user_id in user_last_message_time:
            del user_last_message_time[user_id]
        
        # Подтверждение админу
        await message.reply(
            f"✅ <b>Ответ отправлен!</b>\n\n"
            f"👤 Пользователь: {user.full_name}\n"
            f"🆔 ID: <code>{user_id}</code>\n"
            f"🎯 Стадия: {user_stage}",
            parse_mode="HTML"
        )
        
        logger.info(f"✅ Reply sent to user {user_id}")
        
    except Exception as e:
        await message.reply(f"❌ Ошибка отправки ответа: {str(e)}")
        logger.error(f"❌ Error sending admin reply: {e}", exc_info=True)

async def send_universal_reply(message: types.Message, user_id: int):
    """
    Универсальная отправка ответа последнему пользователю
    """
    try:
        logger.info(f"💬 Sending universal reply to user {user_id}")
        
        # Проверяем пользователя в БД
        async with AsyncSessionLocal() as session:
            user = await UserCRUD.get_user_by_telegram_id(session, user_id)
            if not user:
                await message.reply(f"❌ Пользователь {user_id} не найден в базе данных")
                return
            
            user_stage = user.onboarding_stage
        
        # Формируем ответ
        response_text = f"""💬 <b>Ответ от поддержки:</b>

{message.text or '[медиа-файл]'}"""
        
        # Определяем кнопки
        keyboard = None
        if user_stage == OnboardingStage.COMPLETED:
            keyboard = InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        InlineKeyboardButton(
                            text="🔙 Главное меню",
                            callback_data="show_main_menu"
                        )
                    ]
                ]
            )
        
        # Отправляем ответ пользователю
        await message.bot.send_message(
            chat_id=user_id,
            text=response_text,
            parse_mode="HTML",
            reply_markup=keyboard
        )
        
        # Сбрасываем таймер уведомлений
        if user_id in user_last_message_time:
            del user_last_message_time[user_id]
        
        # Подтверждение админу
        await message.reply(
            f"✅ <b>Универсальный ответ отправлен!</b>\n\n"
            f"👤 Пользователь: {user.full_name}\n"
            f"🆔 ID: <code>{user_id}</code>\n"
            f"🎯 Стадия: {user_stage}\n\n"
            f"💡 <b>Совет:</b> Для точного ответа используйте Reply на сообщение от пользователя",
            parse_mode="HTML"
        )
        
        logger.info(f"✅ Universal reply sent to user {user_id}")
        
    except Exception as e:
        await message.reply(f"❌ Ошибка отправки ответа: {str(e)}")
        logger.error(f"❌ Error sending universal reply: {e}", exc_info=True)

def register_support_handlers(dp):
    """Регистрация хендлеров поддержки"""
    dp.include_router(router)