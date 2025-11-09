"""
Система поддержки с AI автоответами и логированием в Google Sheets
app/handlers/simple_support.py
"""
import logging
from datetime import datetime
from typing import Optional
from aiogram import Router, types, F
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from app.config import settings
from app.services.support_chat_logger import support_chat_logger
from app.services.deepseek_client import deepseek_client
from app.services.auto_answers import auto_answers_service
from app.database.crud import UserCRUD

logger = logging.getLogger(__name__)
router = Router()


class SimpleSupportHandler:
    def __init__(self):
        self.message_to_user = {}  # message_id -> user_id
        self.last_auto_response = {}  # user_id -> datetime
        self.user_gender = {}  # user_id -> 'male' or 'female' (временное хранилище)
        self.user_names = {}  # user_id -> full_name (для логирования)
        self.admin_id = settings.ADMIN_ID
        
        self.last_user_message = {}  # user_id -> datetime (для отслеживания сессий)
        self.admin_notified = {}  # user_id -> bool (отправлена ли история админу)
        
        # ID админов для разных полов - берем из config
        self.male_admin_id = settings.MALE_ADMIN_ID      # для мужчин
        self.female_admin_id = settings.FEMALE_ADMIN_ID  # для женщин
    
    async def get_user_gender(self, user_id: int) -> Optional[str]:
        """Получить пол пользователя (сначала из БД, потом из памяти)"""
        from app.database.connection import AsyncSessionLocal
        
        # Проверяем сначала БД
        try:
            async with AsyncSessionLocal() as db:
                user_data = await UserCRUD.get_user_by_telegram_id(db, user_id)
                if user_data and user_data.gender:
                    # Сохраняем в кеш памяти для быстрого доступа
                    self.user_gender[user_id] = user_data.gender
                    return user_data.gender
        except Exception as e:
            logger.error(f"❌ Error getting gender from DB for user {user_id}: {e}")
        
        # Если нет в БД - проверяем память
        return self.user_gender.get(user_id)
    
    async def set_user_gender(self, user_id: int, gender: str):
        """Установить пол пользователя (сохраняем в БД и в памяти)"""
        from app.database.connection import AsyncSessionLocal
        
        # Сохраняем в память
        self.user_gender[user_id] = gender
        logger.info(f"👤 User {user_id} selected gender: {gender}")
        
        # Сохраняем в БД
        try:
            async with AsyncSessionLocal() as db:
                await UserCRUD.update_user_gender(db, user_id, gender)
                logger.info(f"✅ Gender saved to DB for user {user_id}")
        except Exception as e:
            logger.error(f"❌ Error saving gender to DB for user {user_id}: {e}")
    
    def get_admin_id_by_gender(self, gender: str) -> int:
        """Получить ID админа в зависимости от пола"""
        if gender == 'male':
            return self.male_admin_id
        elif gender == 'female':
            return self.female_admin_id
        return self.admin_id  # fallback
        
    def is_new_session(self, user_id: int) -> bool:
        """Проверка является ли это новой сессией (прошло >12 часов)"""
        from datetime import datetime, timedelta
        
        now = datetime.now()
        
        # Если пользователь пишет первый раз - это новая сессия
        if user_id not in self.last_user_message:
            self.last_user_message[user_id] = now
            return True
        
        last_message_time = self.last_user_message[user_id]
        time_passed = now - last_message_time
        
        # Обновляем время последнего сообщения
        self.last_user_message[user_id] = now
        
        # Если прошло больше 12 часов - новая сессия
        if time_passed > timedelta(hours=12):
            logger.info(f"⏰ New session for user {user_id} (last message {time_passed.total_seconds() / 3600:.1f}h ago)")
            # Сбрасываем флаг уведомления админа при новой сессии
            self.admin_notified[user_id] = False
            return True
        else:
            logger.info(f"⏰ Continuing session for user {user_id} (last message {time_passed.total_seconds() / 60:.1f}m ago)")
            return False
        
    
    def should_send_auto_response(self, user_id: int) -> bool:
        """Проверка нужно ли отправлять автоответ (раз в 30 минут)"""
        now = datetime.now()
        if user_id not in self.last_auto_response:
            self.last_auto_response[user_id] = now
            return True
            
        last_response = self.last_auto_response[user_id]
        if (now - last_response).total_seconds() >= 1800:  # 30 минут
            self.last_auto_response[user_id] = now
            return True
            
        return False
    
    async def handle_user_message(self, message):
        """Обработка сообщения от пользователя с AI автоответами"""
        from app.database.connection import AsyncSessionLocal
        
        user_id = message.from_user.id
        gender = await self.get_user_gender(user_id)
        
        # Сохраняем имя пользователя
        self.user_names[user_id] = message.from_user.full_name
        
        # Если пол не выбран - предлагаем выбрать
        if not gender:
            await self.ask_gender_selection(message)
            return
        
        # Логируем сообщение пользователя в буфер
        support_chat_logger.add_message_to_buffer(
            user_id=user_id,
            sender="Пользователь",
            text=message.text,
            gender=gender
        )
        
        # === AI ОБРАБОТКА ===
        
        # 1. 🆕 Используем DeepSeek для определения типа сообщения
        logger.info(f"🤖 Classifying message type for user {user_id}...")
        message_type = await deepseek_client.classify_message_type(message.text)
        
        if message_type == "greeting":
            # Это приветствие - проверяем тип сессии
            logger.info(f"👋 Detected greeting from user {user_id}")
            
            # Определяем новая ли это сессия
            is_new_session = self.is_new_session(user_id)
            
            # Генерируем ответ с учетом контекста
            greeting_response = await deepseek_client.generate_greeting_response(
                message.text, 
                is_new_session=is_new_session
            )
            
            # Логируем ответ
            support_chat_logger.add_message_to_buffer(
                user_id=user_id,
                sender="AI Support",
                text=greeting_response,
                gender=gender
            )
            
            await message.answer(greeting_response)
            return
        
        # 2. Это вопрос - получаем стадию пользователя из БД
        logger.info(f"❓ User {user_id} sent a QUESTION: '{message.text[:50]}...'")
        
        async with AsyncSessionLocal() as db:
            user_data = await UserCRUD.get_user_by_telegram_id(db, user_id)
            
            if not user_data:
                logger.warning(f"⚠️ User {user_id} not found in DB, forwarding to admin")
                await self.send_to_admin(message, gender)
                return
            
            user_stage = user_data.onboarding_stage
        
        logger.info(f"📊 User {user_id} stage: {user_stage}")
        
        # 3. Получаем автоответы для данной стадии
        qa_pairs = await auto_answers_service.get_qa_pairs_for_stage(user_stage)
        
        if not qa_pairs:
            logger.warning(f"⚠️ No Q&A pairs for stage {user_stage}, forwarding to admin")
            await self.send_to_admin(message, gender)
            
            if self.should_send_auto_response(user_id):
                await message.answer("✅ Сейчас ответим тебе..")
            return
        
        logger.info(f"📋 Loaded {len(qa_pairs)} Q&A pairs for stage {user_stage}")
        
        # 4. Используем AI для поиска похожего вопроса (минимум 80% совпадение)
        logger.info(f"🤖 Searching for matching answer (≥80% similarity) using AI...")
        ai_answer = await deepseek_client.find_matching_answer(
            user_question=message.text,
            qa_pairs=qa_pairs
        )
        
        if ai_answer:
            # Найден подходящий ответ - отправляем его
            logger.info(f"✅ Found matching answer for user {user_id} (≥80% match)")
            
            # Логируем автоответ
            support_chat_logger.add_message_to_buffer(
                user_id=user_id,
                sender="AI Support",
                text=ai_answer,
                gender=gender
            )
            
            await message.answer(ai_answer)
        else:
            # Ответ не найден (<80% совпадение) - направляем админу
            logger.info(f"❌ No matching answer found (<80% similarity), forwarding to admin")
            await self.send_to_admin(message, gender)
            
            # Автоответ пользователю (раз в 30 минут)
            if self.should_send_auto_response(user_id):
                await message.answer("✅ Сейчас ответим тебе..")
    
    async def ask_gender_selection(self, message):
        """Предложить выбрать пол"""
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="🧔🏻 Мужчина", callback_data="gender_male"),
                InlineKeyboardButton(text="🧕 Женщина", callback_data="gender_female")
            ]
        ])
        
        text = """👤 <b>Выбор пола</b>

Пожалуйста, выберите пол для корректной работы технической поддержки.

<i>Этот выбор сохранится, и вам не придется выбирать каждый раз.</i>"""
        
        await message.answer(text, reply_markup=keyboard, parse_mode="HTML")
        
    def get_unread_chat_history(self, user_id: int) -> str:
        """
        Получить только те сообщения, которые админ НЕ видел 
        (т.е. сообщения где отвечал AI Support)
        """
        # Проверяем отправлялась ли уже история этому админу
        if self.admin_notified.get(user_id, False):
            logger.info(f"ℹ️ History already sent to admin for user {user_id}, skipping")
            return ""
        
        # Получаем буфер сообщений из support_chat_logger
        if user_id not in support_chat_logger.chat_buffer:
            logger.info(f"ℹ️ No chat buffer found for user {user_id}")
            return ""
        
        messages = support_chat_logger.chat_buffer[user_id]['messages']
        
        if not messages:
            logger.info(f"ℹ️ Chat buffer is empty for user {user_id}")
            return ""
        
        # Ищем сообщения с AI Support (это означает что админ их не видел)
        ai_messages = [msg for msg in messages if "AI Support:" in msg]
        
        if not ai_messages:
            # Нет сообщений от AI - админ видел всё
            logger.info(f"ℹ️ No AI Support messages found for user {user_id}")
            return ""
        
        # ВАЖНО: Берем все сообщения КРОМЕ последнего
        # Последнее сообщение - это текущий вопрос пользователя, который отправляется отдельно
        # Поэтому берем messages[:-1] (все кроме последнего)
        history_messages = messages[:-1] if len(messages) > 1 else []
        
        if not history_messages:
            logger.info(f"ℹ️ No history to send (only current message)")
            return ""
        
        # Помечаем что история отправлена
        self.admin_notified[user_id] = True
        logger.info(f"📋 Sending {len(history_messages)} unread messages to admin for user {user_id}")
        
        return "\n\n".join(history_messages)  
    
    async def send_to_admin(self, user_message, gender: str):
        """Отправка сообщения админу в зависимости от пола с историей непрочитанных сообщений"""
        user = user_message.from_user
        username = f"@{user.username}" if user.username else "Без username"
        
        # Выбираем нужного админа
        target_admin_id = self.get_admin_id_by_gender(gender)
        gender_emoji = "🧔🏻" if gender == 'male' else "🧕"
        gender_text = "МУЖЧИНА" if gender == 'male' else "ЖЕНЩИНА"
        
        # Получаем историю НЕПРОЧИТАННЫХ сообщений (где отвечал AI Support)
        unread_history = self.get_unread_chat_history(user.id)
        
        # Формируем сообщение
        admin_text = f"""💬 <b>СООБЩЕНИЕ ОТ ПОЛЬЗОВАТЕЛЯ</b>

{gender_emoji} <b>Пол:</b> {gender_text}
👤 <b>Имя:</b> {user.full_name}
🆔 <b>ID:</b> {user.id}
🅰️ <b>Username:</b> {username}"""

        # Если есть непрочитанная история - добавляем её
        if unread_history:
            admin_text += f"\n\n{unread_history}"
        
        # Добавляем текущее сообщение
        admin_text += f"\n\n💬 <b>Сообщение:</b>\n{user_message.text or '[медиа-файл]'}"
        
        try:
            # Отправляем одно сообщение со всей информацией
            admin_msg = await user_message.bot.send_message(
                chat_id=target_admin_id,
                text=admin_text,
                parse_mode="HTML"
            )
            
            # Сохраняем связь message_id -> user_id для ответа
            self.message_to_user[admin_msg.message_id] = user.id
            
            if unread_history:
                logger.info(f"📨 Message with history from user {user.id} ({gender}) sent to admin {target_admin_id}")
            else:
                logger.info(f"📨 Message from user {user.id} ({gender}) sent to admin {target_admin_id}")
                
        except Exception as e:
            logger.error(f"❌ Failed to send message to admin {target_admin_id}: {e}")
    
    async def handle_admin_reply(self, message):
        """Обработка ответа админа на сообщение пользователя"""
        if not message.reply_to_message:
            return
            
        replied_msg_id = message.reply_to_message.message_id
        user_id = self.message_to_user.get(replied_msg_id)
        
        if not user_id:
            return  # Игнорируем если это не ответ на сообщение пользователя
        
        # Получаем пол пользователя и имя (теперь async!)
        gender = await self.get_user_gender(user_id)
        user_name = self.user_names.get(user_id, f"User_{user_id}")
        
        # Логируем ответ админа в буфер
        if message.text:
            support_chat_logger.add_message_to_buffer(
                user_id=user_id,
                sender="Админ",
                text=message.text,
                gender=gender
            )
            
        try:
            # Отправляем ответ пользователю
            if message.text:
                await message.bot.send_message(
                    chat_id=user_id,
                    text=message.text
                )
            elif message.photo:
                await message.bot.send_photo(
                    chat_id=user_id,
                    photo=message.photo[-1].file_id,
                    caption=message.caption
                )
                # Логируем фото
                support_chat_logger.add_message_to_buffer(
                    user_id=user_id,
                    sender="Админ",
                    text="[отправил фото]",
                    gender=gender
                )
            elif message.voice:
                await message.bot.send_voice(
                    chat_id=user_id,
                    voice=message.voice.file_id,
                    caption=message.caption
                )
                # Логируем голосовое
                support_chat_logger.add_message_to_buffer(
                    user_id=user_id,
                    sender="Админ",
                    text="[отправил голосовое сообщение]",
                    gender=gender
                )
            
            logger.info(f"✅ Admin reply sent to user {user_id}")
            
            # ✅ СОХРАНЯЕМ ПОСЛЕ ОТВЕТА АДМИНА
            await support_chat_logger.save_chat_to_sheets(
                user_id=user_id,
                user_name=user_name,
                gender=gender
            )
                
        except Exception as e:
            logger.error(f"❌ Failed to send reply to user {user_id}: {e}")

# Глобальный экземпляр
support_handler = SimpleSupportHandler()


# ============================================================================
# HANDLERS
# ============================================================================

@router.callback_query(F.data.in_(["gender_male", "gender_female"]))
async def handle_gender_selection(callback: types.CallbackQuery):
    """Обработка выбора пола пользователя"""
    user_id = callback.from_user.id
    gender = "male" if callback.data == "gender_male" else "female"
    
    # Сохраняем выбор (теперь async!)
    await support_handler.set_user_gender(user_id, gender)
    
    gender_emoji = "🧔🏻" if gender == 'male' else "🧕"
    gender_text = "мужской" if gender == 'male' else "женский"
    
    # Кнопка для смены пола
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔄 Изменить пол", callback_data="change_gender")]
    ])
    
    text = f"""{gender_emoji} <b>Пол выбран: {gender_text}</b>

✅ Теперь вы можете написать свой вопрос в чат, и вам ответит администратор.

<i>Ваш выбор сохранён. При следующем обращении выбирать пол не потребуется.</i>"""
    
    try:
        await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    except:
        await callback.message.answer(text, reply_markup=keyboard, parse_mode="HTML")
    
    await callback.answer("✅ Пол успешно выбран!")


@router.callback_query(F.data == "change_gender")
async def handle_change_gender(callback: types.CallbackQuery):
    """Обработка изменения пола"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🧔🏻 Мужчина", callback_data="gender_male"),
            InlineKeyboardButton(text="🧕 Женщина", callback_data="gender_female")
        ]
    ])
    
    text = """🔄 <b>Изменение пола</b>

Выберите новый пол:"""
    
    try:
        await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    except:
        await callback.message.answer(text, reply_markup=keyboard, parse_mode="HTML")
    
    await callback.answer()


# Обработка текстовых сообщений от пользователей
@router.message(
    ~F.text.startswith('/'),
    ~F.from_user.id.in_([settings.ADMIN_ID, settings.MALE_ADMIN_ID, settings.FEMALE_ADMIN_ID]),
    ~F.content_type.in_(['voice', 'photo', 'video', 'document', 'audio', 'sticker'])
)
async def handle_user_messages(message: types.Message):
    """Обработка текстовых сообщений от пользователей"""
    await support_handler.handle_user_message(message)


# Отклонение медиа-сообщений от пользователей
@router.message(
    ~F.from_user.id.in_([settings.ADMIN_ID, settings.MALE_ADMIN_ID, settings.FEMALE_ADMIN_ID]),
    F.content_type.in_(['voice', 'photo', 'video', 'document', 'audio', 'sticker']),
    ~F.content_type.in_(['m_video_unikal'])
)
async def reject_media_messages(message: types.Message):
    """Отклонение медиа-сообщений от пользователей"""
    await message.answer(
        "💬  <b>Напишите ваш вопрос текстом, и мы обязательно поможем!</b>\n\n",
        parse_mode="HTML"
    )


# Ответы админов через reply
@router.message(
    F.from_user.id.in_([settings.ADMIN_ID, settings.MALE_ADMIN_ID, settings.FEMALE_ADMIN_ID]),
    F.reply_to_message
)
async def handle_admin_replies(message: types.Message):
    """Обработка ответов админов через reply"""
    await support_handler.handle_admin_reply(message)


# Кнопки поддержки
SUPPORT_CALLBACKS = [
    "main_support", "ask_question_help", "payment_help", "contact_support"
]

@router.callback_query(F.data.in_(SUPPORT_CALLBACKS))
async def show_support_message(callback: types.CallbackQuery):
    """Показ сообщения тех.поддержки с выбором пола"""
    user_id = callback.from_user.id
    gender = await support_handler.get_user_gender(user_id)  # ← Теперь async!
    
    # Если пол уже выбран - показываем стандартное сообщение
    if gender:
        gender_emoji = "🧔🏻" if gender == 'male' else "🧕"
        gender_text = "мужской" if gender == 'male' else "женский"
        
        # Кнопка для смены пола
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔄 Изменить пол", callback_data="change_gender")]
        ])
        
        support_text = f"""👨‍💼 <b>Техническая поддержка</b>

{gender_emoji} <b>Выбранный пол:</b> {gender_text}

💬 Напишите прямо сюда в чат свой вопрос текстом, а также можете прикрепить скриншот.

Мы тебе скоро ответим 🙌"""
        
        await callback.message.answer(support_text, reply_markup=keyboard, parse_mode="HTML")
    
    else:
        # Если пол не выбран - предлагаем выбрать
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="🧔🏻 Мужчина", callback_data="gender_male"),
                InlineKeyboardButton(text="🧕 Женщина", callback_data="gender_female")
            ]
        ])
        
        support_text = """👨‍💼 <b>Техническая поддержка</b>

👤 <b>Выберите пол для корректной работы поддержки:</b>

💬 После выбора вы сможете написать свой вопрос прямо в чат.

<i>Ваш выбор сохранится для будущих обращений.</i>"""
        
        await callback.message.answer(support_text, reply_markup=keyboard, parse_mode="HTML")
    
    await callback.answer()


def register_simple_support_handlers(dp):
    """Регистрация handlers для поддержки"""
    dp.include_router(router)