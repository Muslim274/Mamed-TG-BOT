"""
Основной обработчик системы рассылки с поддержкой множественных админов и медиа
app/handlers/broadcast/broadcast_handler.py

ОБНОВЛЕНО: Добавлена поддержка медиа (фото, видео, аудио, голосовые, круглые видео)
ОБНОВЛЕНО: Добавлены новые типы рассылок (не оплатившим, обучающимся)
"""
import asyncio
import logging
from datetime import datetime
from typing import List, Dict, Any
from aiogram import Router, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext

from app.config import settings, is_admin
from app.database.connection import AsyncSessionLocal
from app.database.crud import UserCRUD
from app.handlers.broadcast.broadcast_states import BroadcastStates
from app.handlers.broadcast.broadcast_utils import (
    parse_telegram_ids,
    get_audience_keyboard,
    get_validation_keyboard,
    get_confirmation_keyboard,
    format_user_list_preview,
    format_broadcast_preview,
    format_progress_message,
    format_final_report,
    validate_message_length
)

logger = logging.getLogger(__name__)

router = Router()

broadcast_stats = {
    'total_broadcasts': 0,
    'total_messages_sent': 0,
    'last_broadcast': None
}


def admin_filter():
    """Создает фильтр для проверки множественных админов"""
    admin_ids = settings.admin_ids_list
    return F.from_user.id.in_(admin_ids)


@router.message(Command("broadcast"), admin_filter())
async def start_broadcast(message: types.Message, state: FSMContext):
    """Начало процесса рассылки - для всех админов"""
    logger.info(f"Admin {message.from_user.id} started broadcast")
    
    if not is_admin(message.from_user.id):
        await message.answer("❌ У вас нет прав для выполнения рассылки")
        return
    
    try:
        async with AsyncSessionLocal() as session:
            stats = await UserCRUD.get_broadcast_statistics(session)
        
        admin_ids = settings.admin_ids_list
        stats_text = f"""
📢 <b>Система рассылки сообщений</b>

👤 <b>Админ:</b> {message.from_user.full_name} (<code>{message.from_user.id}</code>)
👥 <b>Всего админов:</b> {len(admin_ids)}

📊 <b>Статистика пользователей:</b>
• Всего активных: {stats['total_active']}
• Завершили онбординг: {stats['completed_onboarding']}
• Оплатили курс: {stats['paid_users']}
• В процессе онбординга: {stats['incomplete_onboarding']}

👥 <b>Выберите аудиторию для рассылки:</b>
"""
        
        await message.answer(
            stats_text,
            parse_mode="HTML",
            reply_markup=get_audience_keyboard()
        )
        
        await state.set_state(BroadcastStates.choosing_audience)
        await state.update_data(
            user_stats=stats,
            start_time=datetime.now().isoformat(),
            admin_id=message.from_user.id,
            admin_name=message.from_user.full_name
        )
        
    except Exception as e:
        logger.error(f"Error starting broadcast: {e}")
        await message.answer(
            "❌ Ошибка инициализации рассылки. Попробуйте позже.",
            parse_mode="HTML"
        )


@router.callback_query(F.data == "send_all", BroadcastStates.choosing_audience)
async def choose_all_users(callback: types.CallbackQuery, state: FSMContext):
    """Выбор рассылки всем пользователям"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Нет доступа", show_alert=True)
        return
        
    logger.info(f"Admin {callback.from_user.id} chose broadcast to all users")
    
    try:
        async with AsyncSessionLocal() as session:
            recipients_db = await UserCRUD.get_all_active_users(session)
        
        recipients = []
        for user in recipients_db:
            recipients.append({
                'telegram_id': user.telegram_id,
                'username': user.username,
                'full_name': user.full_name,
                'ref_code': user.ref_code
            })
        
        await state.update_data(
            audience_type="all_users",
            recipients=recipients,
            recipient_count=len(recipients)
        )
        
        await callback.message.edit_text(
            f"📝 <b>Введите сообщение для рассылки</b>\n\n"
            f"👥 <b>Получатели:</b> {len(recipients)} пользователей\n\n"
            f"<i>Отправьте текст, фото, видео, аудио или голосовое сообщение:</i>",
            parse_mode="HTML"
        )
        
        await state.set_state(BroadcastStates.entering_message)
        await callback.answer()
        
    except Exception as e:
        logger.error(f"Error getting all users: {e}")
        await callback.answer("❌ Ошибка получения списка пользователей", show_alert=True)


@router.callback_query(F.data == "broadcast_paid_users", BroadcastStates.choosing_audience)
async def choose_paid_users(callback: types.CallbackQuery, state: FSMContext):
    """Выбор рассылки пользователям, оплатившим курс"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Нет доступа", show_alert=True)
        return
        
    logger.info(f"Admin {callback.from_user.id} chose broadcast to paid users")
    
    try:
        async with AsyncSessionLocal() as session:
            recipients_db = await UserCRUD.get_paid_users(session)
        
        recipients = []
        for user in recipients_db:
            recipients.append({
                'telegram_id': user.telegram_id,
                'username': user.username,
                'full_name': user.full_name,
                'ref_code': user.ref_code
            })
        
        await state.update_data(
            audience_type="paid_users",
            recipients=recipients,
            recipient_count=len(recipients)
        )
        
        await callback.message.edit_text(
            f"📝 <b>Введите сообщение для рассылки</b>\n\n"
            f"👥 <b>Получатели:</b> {len(recipients)} пользователей (оплативших курс)\n\n"
            f"<i>Отправьте текст, фото, видео, аудио или голосовое сообщение:</i>",
            parse_mode="HTML"
        )
        
        await state.set_state(BroadcastStates.entering_message)
        await callback.answer()
        
    except Exception as e:
        logger.error(f"Error getting paid users: {e}")
        await callback.answer("❌ Ошибка получения списка пользователей", show_alert=True)


@router.callback_query(F.data == "broadcast_unpaid_users", BroadcastStates.choosing_audience)
async def choose_unpaid_users(callback: types.CallbackQuery, state: FSMContext):
    """Выбор рассылки пользователям, которые НЕ оплатили"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Нет доступа", show_alert=True)
        return
        
    logger.info(f"Admin {callback.from_user.id} chose broadcast to unpaid users")
    
    try:
        async with AsyncSessionLocal() as session:
            recipients_db = await UserCRUD.get_unpaid_users(session)
        
        recipients = []
        for user in recipients_db:
            recipients.append({
                'telegram_id': user.telegram_id,
                'username': user.username,
                'full_name': user.full_name,
                'ref_code': user.ref_code
            })
        
        await state.update_data(
            audience_type="unpaid_users",
            recipients=recipients,
            recipient_count=len(recipients)
        )
        
        await callback.message.edit_text(
            f"📝 <b>Введите сообщение для рассылки</b>\n\n"
            f"👥 <b>Получатели:</b> {len(recipients)} пользователей (не оплативших курс)\n\n"
            f"<i>Отправьте текст, фото, видео, аудио или голосовое сообщение:</i>",
            parse_mode="HTML"
        )
        
        await state.set_state(BroadcastStates.entering_message)
        await callback.answer()
        
    except Exception as e:
        logger.error(f"Error getting unpaid users: {e}")
        await callback.answer("❌ Ошибка получения списка пользователей", show_alert=True)


@router.callback_query(F.data == "broadcast_learning_users", BroadcastStates.choosing_audience)
async def choose_learning_users(callback: types.CallbackQuery, state: FSMContext):
    """Выбор рассылки пользователям, которые проходят обучение"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Нет доступа", show_alert=True)
        return
        
    logger.info(f"Admin {callback.from_user.id} chose broadcast to learning users")
    
    try:
        async with AsyncSessionLocal() as session:
            recipients_db = await UserCRUD.get_learning_users(session)
        
        recipients = []
        for user in recipients_db:
            recipients.append({
                'telegram_id': user.telegram_id,
                'username': user.username,
                'full_name': user.full_name,
                'ref_code': user.ref_code
            })
        
        await state.update_data(
            audience_type="learning_users",
            recipients=recipients,
            recipient_count=len(recipients)
        )
        
        await callback.message.edit_text(
            f"📝 <b>Введите сообщение для рассылки</b>\n\n"
            f"👥 <b>Получатели:</b> {len(recipients)} пользователей (проходят обучение)\n\n"
            f"<i>Отправьте текст, фото, видео, аудио или голосовое сообщение:</i>",
            parse_mode="HTML"
        )
        
        await state.set_state(BroadcastStates.entering_message)
        await callback.answer()
        
    except Exception as e:
        logger.error(f"Error getting learning users: {e}")
        await callback.answer("❌ Ошибка получения списка пользователей", show_alert=True)


@router.callback_query(F.data == "broadcast_payment_page_users", BroadcastStates.choosing_audience)
async def choose_payment_page_users(callback: types.CallbackQuery, state: FSMContext):
    """Выбор рассылки пользователям на странице оплаты"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Нет доступа", show_alert=True)
        return
        
    logger.info(f"Admin {callback.from_user.id} chose broadcast to payment page users")
    
    try:
        async with AsyncSessionLocal() as session:
            recipients_db = await UserCRUD.get_payment_page_users(session)
        
        recipients = []
        for user in recipients_db:
            recipients.append({
                'telegram_id': user.telegram_id,
                'username': user.username,
                'full_name': user.full_name,
                'ref_code': user.ref_code
            })
        
        await state.update_data(
            audience_type="payment_page_users",
            recipients=recipients,
            recipient_count=len(recipients)
        )
        
        await callback.message.edit_text(
            f"📝 <b>Введите сообщение для рассылки</b>\n\n"
            f"👥 <b>Получатели:</b> {len(recipients)} пользователей (на странице оплаты)\n\n"
            f"<i>Отправьте текст, фото, видео, аудио или голосовое сообщение:</i>",
            parse_mode="HTML"
        )
        
        await state.set_state(BroadcastStates.entering_message)
        await callback.answer()
        
    except Exception as e:
        logger.error(f"Error getting payment page users: {e}")
        await callback.answer("❌ Ошибка получения списка пользователей", show_alert=True)

@router.callback_query(F.data == "send_custom", BroadcastStates.choosing_audience)
async def choose_specific_users(callback: types.CallbackQuery, state: FSMContext):
    """Выбор рассылки определенным пользователям"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Нет доступа", show_alert=True)
        return
        
    logger.info(f"Admin {callback.from_user.id} chose broadcast to specific users")
    
    await state.update_data(audience_type="specific_users")
    
    await callback.message.edit_text(
        f"👥 <b>Введите список Telegram ID</b>\n\n"
        f"<b>Поддерживаемые форматы:</b>\n"
        f"• Через запятую: <code>123456789, 987654321</code>\n"
        f"• Через пробел: <code>123456789 987654321</code>\n"
        f"• Каждый с новой строки:\n"
        f"<code>123456789\n987654321</code>\n\n"
        f"<i>Отправьте список ID:</i>",
        parse_mode="HTML"
    )
    
    await state.set_state(BroadcastStates.entering_user_ids)
    await callback.answer()


@router.message(BroadcastStates.entering_user_ids)
async def process_user_ids(message: types.Message, state: FSMContext):
    """Обработка введенного списка Telegram ID"""
    if not is_admin(message.from_user.id):
        await message.answer("❌ У вас нет прав для выполнения этой операции")
        await state.clear()
        return
        
    logger.info(f"Admin {message.from_user.id} processing user IDs input")
    
    try:
        telegram_ids = parse_telegram_ids(message.text)
        
        if not telegram_ids:
            await message.answer(
                "❌ Не удалось найти корректные Telegram ID.\n"
                "Проверьте формат и попробуйте еще раз."
            )
            return
        
        async with AsyncSessionLocal() as session:
            recipients_db = await UserCRUD.get_users_by_telegram_ids(session, telegram_ids)
            
        logger.info(f"Found {len(recipients_db)} users in database")
        
        if not recipients_db:
            await message.answer(
                "❌ Среди указанных ID не найдено активных пользователей в базе данных."
            )
            return
        
        recipients = []
        for user in recipients_db:
            recipients.append({
                'telegram_id': user.telegram_id,
                'username': user.username,
                'full_name': user.full_name,
                'ref_code': user.ref_code
            })
            
        logger.info(f"Converted to {len(recipients)} recipient dictionaries")
        
        preview_text = format_user_list_preview(recipients, telegram_ids)
        
        await state.update_data(
            recipients=recipients,
            recipient_count=len(recipients),
            requested_ids=telegram_ids
        )
        
        await message.answer(
            preview_text,
            parse_mode="HTML",
            reply_markup=get_validation_keyboard()
        )
        
        await state.set_state(BroadcastStates.validating_ids)
        
    except Exception as e:
        logger.error(f"Error processing user IDs: {e}")
        await message.answer(
            "❌ Ошибка обработки списка ID. Попробуйте еще раз."
        )


@router.callback_query(F.data == "broadcast_confirm_users", BroadcastStates.validating_ids)
async def confirm_user_list(callback: types.CallbackQuery, state: FSMContext):
    """Подтверждение списка пользователей"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Нет доступа", show_alert=True)
        return
        
    data = await state.get_data()
    recipients = data.get('recipients', [])
    recipient_count = data.get('recipient_count', 0)
    
    if not recipients or recipient_count == 0:
        await callback.answer("❌ Нет получателей для рассылки", show_alert=True)
        return
    
    await callback.message.edit_text(
        f"📝 <b>Введите сообщение для рассылки</b>\n\n"
        f"👥 <b>Получатели:</b> {recipient_count} пользователей\n\n"
        f"<i>Отправьте текст, фото, видео, аудио или голосовое сообщение:</i>",
        parse_mode="HTML"
    )
    
    await state.set_state(BroadcastStates.entering_message)
    await callback.answer()


@router.callback_query(F.data == "broadcast_edit_users", BroadcastStates.validating_ids)
async def edit_user_list(callback: types.CallbackQuery, state: FSMContext):
    """Изменение списка пользователей"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Нет доступа", show_alert=True)
        return
        
    await callback.message.edit_text(
        f"👥 <b>Введите новый список Telegram ID</b>\n\n"
        f"<b>Поддерживаемые форматы:</b>\n"
        f"• Через запятую: <code>123456789, 987654321</code>\n"
        f"• Через пробел: <code>123456789 987654321</code>\n"
        f"• Каждый с новой строки:\n"
        f"<code>123456789\n987654321</code>\n\n"
        f"<i>Отправьте список ID:</i>",
        parse_mode="HTML"
    )
    
    await state.set_state(BroadcastStates.entering_user_ids)
    await callback.answer()


@router.message(BroadcastStates.entering_message)
async def handle_message_input(message: types.Message, state: FSMContext):
    """Обработка входящего сообщения (текст, фото, видео, аудио и т.д.)"""
    if not is_admin(message.from_user.id):
        await message.answer("❌ Нет доступа")
        return
    
    try:
        data = await state.get_data()
        recipients = data.get('recipients', [])
        recipient_count = data.get('recipient_count', 0)
        admin_name = data.get('admin_name', 'Неизвестно')
        audience_type = data.get('audience_type', '')
        
        # Определяем описание аудитории
        audience_descriptions = {
            "all_users": "всем пользователям",
            "new_leads": "новым лидам (не оплатившим)",
            "partners": "партнерам",
            "partners_completed": "партнерам, завершившим обучение",
            "partners_without_team": "партнерам без команды",
            "partners_in_team": "партнерам в команде",
            "learning_users": "пользователям, которые еще обучаются",
            "specific_users": "выбранным пользователям",
            "paid_users": "пользователям, оплатившим курс",
            "unpaid_users": "пользователям, не оплатившим курс",
            "payment_page_users": "пользователям на странице оплаты"
        }
        audience_description = audience_descriptions.get(audience_type, "пользователям")
        
        # Сохраняем данные в зависимости от типа сообщения
        media_data = {}
        
        if message.text:
            media_data['type'] = 'text'
            media_data['text'] = message.text
            media_data['caption'] = None
            preview_text = message.text
            
        elif message.photo:
            media_data['type'] = 'photo'
            media_data['file_id'] = message.photo[-1].file_id
            media_data['caption'] = message.caption or ""
            preview_text = f"📷 <b>Фото</b>\n{message.caption or '(без текста)'}"
            
        elif message.video:
            media_data['type'] = 'video'
            media_data['file_id'] = message.video.file_id
            media_data['caption'] = message.caption or ""
            preview_text = f"🎥 <b>Видео</b>\n{message.caption or '(без текста)'}"
            
        elif message.video_note:
            media_data['type'] = 'video_note'
            media_data['file_id'] = message.video_note.file_id
            media_data['caption'] = None
            preview_text = f"⭕ <b>Круглое видео</b>"
            
        elif message.audio:
            media_data['type'] = 'audio'
            media_data['file_id'] = message.audio.file_id
            media_data['caption'] = message.caption or ""
            preview_text = f"🎵 <b>Аудио</b>\n{message.caption or '(без текста)'}"
            
        elif message.voice:
            media_data['type'] = 'voice'
            media_data['file_id'] = message.voice.file_id
            media_data['caption'] = message.caption or ""
            preview_text = f"🎤 <b>Голосовое</b>\n{message.caption or '(без текста)'}"
            
        else:
            await message.answer("❌ Неподдерживаемый тип медиа")
            return
        
        # Сохраняем данные
        await state.update_data(
            media_data=media_data,
            message_text=preview_text
        )
        
        # Показываем превью
        confirmation_text = f"""
📢 <b>ПРЕДПРОСМОТР РАССЫЛКИ</b>

👤 <b>Отправитель:</b> {admin_name}
👥 <b>Получатели:</b> {recipient_count} {audience_description}
📝 <b>Сообщение:</b>
━━━━━━━━━━━━━━━━━━━━
{preview_text}
━━━━━━━━━━━━━━━━━━━━

Отправить сейчас?
"""
        
        await message.answer(
            confirmation_text,
            parse_mode="HTML",
            reply_markup=get_confirmation_keyboard()
        )
        
        await state.set_state(BroadcastStates.confirming)
        
    except Exception as e:
        logger.error(f"Error handling message input: {e}")
        await message.answer("❌ Ошибка обработки сообщения")


@router.callback_query(F.data == "broadcast_edit_message", BroadcastStates.confirming)
async def edit_broadcast_message(callback: types.CallbackQuery, state: FSMContext):
    """Изменение сообщения рассылки"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Нет доступа", show_alert=True)
        return
        
    data = await state.get_data()
    recipient_count = data.get('recipient_count', 0)
    
    await callback.message.edit_text(
        f"✏️ <b>Изменение сообщения</b>\n\n"
        f"👥 <b>Получатели:</b> {recipient_count} пользователей\n\n"
        f"<i>Введите новое сообщение:</i>",
        parse_mode="HTML"
    )
    
    await state.set_state(BroadcastStates.entering_message)
    await callback.answer()


@router.callback_query(F.data == "broadcast_confirm_send", BroadcastStates.confirming)
async def confirm_broadcast_send(callback: types.CallbackQuery, state: FSMContext):
    """Подтверждение и запуск рассылки"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Нет доступа", show_alert=True)
        return
    
    try:
        data = await state.get_data()
        recipients = data.get('recipients', [])
        media_data = data.get('media_data', {})
        admin_id = data.get('admin_id')
        admin_name = data.get('admin_name', 'Неизвестно')
        start_time_str = data.get('start_time')
        
        if not recipients:
            await callback.answer("❌ Список получателей пуст", show_alert=True)
            return
        
        start_time = datetime.fromisoformat(start_time_str) if start_time_str else datetime.now()
        
        progress_message = await callback.message.edit_text(
            f"🚀 <b>Запуск рассылки...</b>\n\n"
            f"👤 <b>Инициатор:</b> {admin_name}\n"
            f"👥 <b>Получателей:</b> {len(recipients)}\n\n"
            f"Пожалуйста, подождите...",
            parse_mode="HTML"
        )
        
        await state.set_state(BroadcastStates.broadcasting)
        
        # Запуск в фоне
        asyncio.create_task(
            execute_broadcast(
                bot=callback.bot,
                recipients=recipients,
                media_data=media_data,
                progress_message=progress_message,
                start_time=start_time,
                state=state,
                admin_id=admin_id,
                admin_name=admin_name
            )
        )
        
        await callback.answer("✅ Рассылка запущена")
        
    except Exception as e:
        logger.error(f"Error confirming broadcast: {e}")
        await callback.answer("❌ Ошибка запуска рассылки", show_alert=True)


async def execute_broadcast(
    bot,
    recipients: List[Dict],
    media_data: Dict,
    progress_message: types.Message,
    start_time: datetime,
    state: FSMContext,
    admin_id: int,
    admin_name: str
):
    """
    Выполнение рассылки в фоне с поддержкой медиа
    """
    logger.info(f"Starting broadcast execution for {len(recipients)} recipients by admin {admin_id}")
    
    total = len(recipients)
    successful = 0
    errors = 0
    error_details = {'blocked': 0, 'not_found': 0, 'other': 0}
    
    update_interval = max(1, total // 20)
    
    try:
        for i, recipient in enumerate(recipients, 1):
            telegram_id = recipient['telegram_id']
            
            try:
                # Отправляем в зависимости от типа медиа
                media_type = media_data.get('type', 'text')
                
                if media_type == 'text':
                    await bot.send_message(
                        chat_id=telegram_id,
                        text=media_data.get('text', ''),
                        parse_mode="HTML"
                    )
                    
                elif media_type == 'photo':
                    await bot.send_photo(
                        chat_id=telegram_id,
                        photo=media_data.get('file_id'),
                        caption=media_data.get('caption'),
                        parse_mode="HTML"
                    )
                    
                elif media_type == 'video':
                    await bot.send_video(
                        chat_id=telegram_id,
                        video=media_data.get('file_id'),
                        caption=media_data.get('caption'),
                        parse_mode="HTML"
                    )
                    
                elif media_type == 'video_note':
                    await bot.send_video_note(
                        chat_id=telegram_id,
                        video_note=media_data.get('file_id')
                    )
                    
                elif media_type == 'audio':
                    await bot.send_audio(
                        chat_id=telegram_id,
                        audio=media_data.get('file_id'),
                        caption=media_data.get('caption'),
                        parse_mode="HTML"
                    )
                    
                elif media_type == 'voice':
                    await bot.send_voice(
                        chat_id=telegram_id,
                        voice=media_data.get('file_id'),
                        caption=media_data.get('caption'),
                        parse_mode="HTML"
                    )
                
                successful += 1
                await asyncio.sleep(0.05)
                
            except Exception as e:
                errors += 1
                error_str = str(e).lower()
                
                if "blocked" in error_str or "user is deactivated" in error_str:
                    error_details['blocked'] += 1
                elif "not found" in error_str or "chat not found" in error_str:
                    error_details['not_found'] += 1
                else:
                    error_details['other'] += 1
                
                logger.warning(f"Failed to send to {telegram_id}: {e}")
            
            # Обновляем прогресс
            if i % update_interval == 0 or i == total:
                try:
                    progress_text = format_progress_message(
                        current=i,
                        total=total,
                        successful=successful,
                        errors=errors,
                        admin_name=admin_name
                    )
                    
                    await progress_message.edit_text(
                        progress_text,
                        parse_mode="HTML"
                    )
                except:
                    pass
        
        # Финальный отчет
        end_time = datetime.now()
        duration = end_time - start_time
        
        global broadcast_stats
        broadcast_stats['total_broadcasts'] += 1
        broadcast_stats['total_messages_sent'] += successful
        broadcast_stats['last_broadcast'] = end_time
        
        final_report = format_final_report(
            total=total,
            successful=successful,
            errors=errors,
            error_details=error_details,
            duration=duration,
            admin_name=admin_name,
            admin_id=admin_id
        )
        
        await progress_message.edit_text(
            final_report,
            parse_mode="HTML"
        )
        
        # Уведомляем других админов
        admin_ids = settings.admin_ids_list
        for other_admin_id in admin_ids:
            if other_admin_id != admin_id:
                try:
                    await bot.send_message(
                        chat_id=other_admin_id,
                        text=f"📢 <b>Уведомление о рассылке</b>\n\n{final_report}",
                        parse_mode="HTML"
                    )
                except Exception as e:
                    logger.warning(f"Failed to notify admin {other_admin_id}: {e}")
        
        logger.info(f"Broadcast completed: {successful}/{total} successful by admin {admin_id}")
        
    except Exception as e:
        logger.error(f"Critical error in broadcast execution: {e}")
        try:
            await progress_message.edit_text(
                f"❌ <b>Критическая ошибка рассылки</b>\n\n"
                f"👤 <b>Инициатор:</b> {admin_name}\n"
                f"Обработано: {successful + errors}/{total}\n"
                f"Ошибка: {str(e)}",
                parse_mode="HTML"
            )
        except:
            pass
    
    finally:
        await state.clear()


@router.callback_query(F.data == "cancel_broadcast")
async def cancel_broadcast(callback: types.CallbackQuery, state: FSMContext):
    """Отмена рассылки"""
    logger.info(f"Admin {callback.from_user.id} cancelled broadcast")
    
    await callback.message.edit_text(
        f"❌ <b>Рассылка отменена</b>\n\n"
        f"👤 <b>Отменил:</b> {callback.from_user.full_name}",
        parse_mode="HTML"
    )
    
    await state.clear()
    await callback.answer("Рассылка отменена")


@router.message(Command("broadcast_stats"), admin_filter())
async def show_broadcast_stats(message: types.Message):
    """Показ статистики рассылок"""
    if not is_admin(message.from_user.id):
        await message.answer("❌ У вас нет прав для просмотра статистики")
        return
        
    global broadcast_stats
    
    try:
        async with AsyncSessionLocal() as session:
            user_stats = await UserCRUD.get_broadcast_statistics(session)
        
        last_broadcast_str = "Никогда"
        if broadcast_stats['last_broadcast']:
            last_broadcast_str = broadcast_stats['last_broadcast'].strftime("%d.%m.%Y %H:%M")
        
        admin_ids = settings.admin_ids_list
        stats_text = f"""
📊 <b>Статистика системы рассылки</b>

👤 <b>Запросил:</b> {message.from_user.full_name}
👥 <b>Админов в системе:</b> {len(admin_ids)}

🚀 <b>Рассылки:</b>
• Всего рассылок: {broadcast_stats['total_broadcasts']}
• Сообщений отправлено: {broadcast_stats['total_messages_sent']}
• Последняя рассылка: {last_broadcast_str}

👥 <b>Пользователи:</b>
• Всего активных: {user_stats['total_active']}
• Завершили онбординг: {user_stats['completed_onboarding']}
• Оплатили курс: {user_stats['paid_users']}
• В процессе: {user_stats['incomplete_onboarding']}

💡 Для новой рассылки используйте /broadcast
"""
        
        await message.answer(stats_text, parse_mode="HTML")
        
    except Exception as e:
        logger.error(f"Error showing broadcast stats: {e}")
        await message.answer(
            "❌ Ошибка получения статистики",
            parse_mode="HTML"
        )


def register_broadcast_handlers(dp):
    """Регистрация хендлеров рассылки"""
    dp.include_router(router)