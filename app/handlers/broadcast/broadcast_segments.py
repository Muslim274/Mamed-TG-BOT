"""
Handlers для сегментированной рассылки
Новые функции для рассылки по сегментам пользователей
"""
import logging
from aiogram import Router, types, F
from aiogram.fsm.context import FSMContext

from app.config import is_admin
from app.database.connection import AsyncSessionLocal
from app.database.statistics_crud import UserSegmentCRUD
from app.handlers.broadcast.broadcast_states import BroadcastStates

logger = logging.getLogger(__name__)

router = Router()


@router.callback_query(F.data == "send_leads", BroadcastStates.choosing_audience)
async def choose_new_leads(callback: types.CallbackQuery, state: FSMContext):
    """Выбор рассылки новым лидам (не оплатившим)"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Нет доступа", show_alert=True)
        return

    logger.info(f"Admin {callback.from_user.id} chose broadcast to new leads")

    try:
        async with AsyncSessionLocal() as session:
            recipients_db = await UserSegmentCRUD.get_segment_new_leads(session)

        recipients = []
        for user in recipients_db:
            recipients.append({
                'telegram_id': user.telegram_id,
                'username': user.username,
                'full_name': user.full_name,
                'ref_code': user.ref_code
            })

        await state.update_data(
            audience_type="new_leads",
            recipients=recipients,
            recipient_count=len(recipients)
        )

        await callback.message.edit_text(
            f"📝 <b>Введите сообщение для рассылки</b>\n\n"
            f"👥 <b>Получатели:</b> {len(recipients)} новых лидов (не оплативших)\n"
            f"🆕 <b>Сегмент:</b> Пользователи, которые еще не совершили покупку\n\n"
            f"<i>Отправьте текст, фото, видео, аудио или голосовое сообщение:</i>",
            parse_mode="HTML"
        )

        await state.set_state(BroadcastStates.entering_message)
        await callback.answer()

    except Exception as e:
        logger.error(f"Error getting new leads: {e}")
        await callback.answer("❌ Ошибка получения списка новых лидов", show_alert=True)


@router.callback_query(F.data == "send_partners", BroadcastStates.choosing_audience)
async def choose_partners(callback: types.CallbackQuery, state: FSMContext):
    """Выбор рассылки партнерам (завершившим онбординг)"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Нет доступа", show_alert=True)
        return

    logger.info(f"Admin {callback.from_user.id} chose broadcast to partners")

    try:
        async with AsyncSessionLocal() as session:
            recipients_db = await UserSegmentCRUD.get_segment_partners(session)

        recipients = []
        for user in recipients_db:
            recipients.append({
                'telegram_id': user.telegram_id,
                'username': user.username,
                'full_name': user.full_name,
                'ref_code': user.ref_code
            })

        await state.update_data(
            audience_type="partners",
            recipients=recipients,
            recipient_count=len(recipients)
        )

        await callback.message.edit_text(
            f"📝 <b>Введите сообщение для рассылки</b>\n\n"
            f"👥 <b>Получатели:</b> {len(recipients)} партнеров\n"
            f"🤝 <b>Сегмент:</b> Пользователи, которые полностью завершили онбординг\n\n"
            f"<i>Отправьте текст, фото, видео, аудио или голосовое сообщение:</i>",
            parse_mode="HTML"
        )

        await state.set_state(BroadcastStates.entering_message)
        await callback.answer()

    except Exception as e:
        logger.error(f"Error getting partners: {e}")
        await callback.answer("❌ Ошибка получения списка партнеров", show_alert=True)


@router.callback_query(F.data == "send_no_team", BroadcastStates.choosing_audience)
async def choose_partners_without_team(callback: types.CallbackQuery, state: FSMContext):
    """Выбор рассылки партнерам без команды (купили, но не нажали кнопку 'Команда')"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Нет доступа", show_alert=True)
        return

    logger.info(f"Admin {callback.from_user.id} chose broadcast to partners without team")

    try:
        async with AsyncSessionLocal() as session:
            recipients_db = await UserSegmentCRUD.get_segment_partners_without_team(session)

        recipients = []
        for user in recipients_db:
            recipients.append({
                'telegram_id': user.telegram_id,
                'username': user.username,
                'full_name': user.full_name,
                'ref_code': user.ref_code
            })

        await state.update_data(
            audience_type="partners_without_team",
            recipients=recipients,
            recipient_count=len(recipients)
        )

        await callback.message.edit_text(
            f"📝 <b>Введите сообщение для рассылки</b>\n\n"
            f"👥 <b>Получатели:</b> {len(recipients)} партнеров без команды\n"
            f"⚠️ <b>Сегмент:</b> Пользователи, которые купили партнерку, но не нажали кнопку 'Команда'\n\n"
            f"<i>Отправьте текст, фото, видео, аудио или голосовое сообщение:</i>",
            parse_mode="HTML"
        )

        await state.set_state(BroadcastStates.entering_message)
        await callback.answer()

    except Exception as e:
        logger.error(f"Error getting partners without team: {e}")
        await callback.answer("❌ Ошибка получения списка партнеров без команды", show_alert=True)


@router.callback_query(F.data == "send_done", BroadcastStates.choosing_audience)
async def choose_partners_completed(callback: types.CallbackQuery, state: FSMContext):
    """Выбор рассылки партнерам, завершившим обучение"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Нет доступа", show_alert=True)
        return

    logger.info(f"Admin {callback.from_user.id} chose broadcast to partners who completed training")

    try:
        async with AsyncSessionLocal() as session:
            recipients_db = await UserSegmentCRUD.get_segment_partners_completed(session)

        recipients = []
        for user in recipients_db:
            recipients.append({
                'telegram_id': user.telegram_id,
                'username': user.username,
                'full_name': user.full_name,
                'ref_code': user.ref_code
            })

        await state.update_data(
            audience_type="partners_completed",
            recipients=recipients,
            recipient_count=len(recipients)
        )

        await callback.message.edit_text(
            f"📝 <b>Введите сообщение для рассылки</b>\n\n"
            f"👥 <b>Получатели:</b> {len(recipients)} партнеров\n"
            f"🎓 <b>Сегмент:</b> Партнёры, завершившие обучение\n\n"
            f"<i>Отправьте текст, фото, видео, аудио или голосовое сообщение:</i>",
            parse_mode="HTML"
        )

        await state.set_state(BroadcastStates.entering_message)
        await callback.answer()

    except Exception as e:
        logger.error(f"Error getting completed partners: {e}")
        await callback.answer("❌ Ошибка получения списка партнеров", show_alert=True)


@router.callback_query(F.data == "send_in_team", BroadcastStates.choosing_audience)
async def choose_partners_in_team(callback: types.CallbackQuery, state: FSMContext):
    """Выбор рассылки партнерам, вступившим в команду"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Нет доступа", show_alert=True)
        return

    logger.info(f"Admin {callback.from_user.id} chose broadcast to partners in team")

    try:
        async with AsyncSessionLocal() as session:
            recipients_db = await UserSegmentCRUD.get_segment_partners_in_team(session)

        recipients = []
        for user in recipients_db:
            recipients.append({
                'telegram_id': user.telegram_id,
                'username': user.username,
                'full_name': user.full_name,
                'ref_code': user.ref_code
            })

        await state.update_data(
            audience_type="partners_in_team",
            recipients=recipients,
            recipient_count=len(recipients)
        )

        await callback.message.edit_text(
            f"📝 <b>Введите сообщение для рассылки</b>\n\n"
            f"👥 <b>Получатели:</b> {len(recipients)} партнеров\n"
            f"💪 <b>Сегмент:</b> Партнёры, вступившие в команду\n\n"
            f"<i>Отправьте текст, фото, видео, аудио или голосовое сообщение:</i>",
            parse_mode="HTML"
        )

        await state.set_state(BroadcastStates.entering_message)
        await callback.answer()

    except Exception as e:
        logger.error(f"Error getting partners in team: {e}")
        await callback.answer("❌ Ошибка получения списка партнеров в команде", show_alert=True)


@router.callback_query(F.data == "send_learning", BroadcastStates.choosing_audience)
async def choose_learning_users(callback: types.CallbackQuery, state: FSMContext):
    """Выбор рассылки пользователям, которые еще обучаются"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Нет доступа", show_alert=True)
        return

    logger.info(f"Admin {callback.from_user.id} chose broadcast to learning users")

    try:
        async with AsyncSessionLocal() as session:
            recipients_db = await UserSegmentCRUD.get_segment_learning_users(session)

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
            f"👥 <b>Получатели:</b> {len(recipients)} пользователей\n"
            f"📚 <b>Сегмент:</b> Пользователи, которые еще обучаются\n\n"
            f"<i>Отправьте текст, фото, видео, аудио или голосовое сообщение:</i>",
            parse_mode="HTML"
        )

        await state.set_state(BroadcastStates.entering_message)
        await callback.answer()

    except Exception as e:
        logger.error(f"Error getting learning users: {e}")
        await callback.answer("❌ Ошибка получения списка обучающихся", show_alert=True)
