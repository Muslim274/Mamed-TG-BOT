
"""
Хэндлер для обработки уникальных видео в боте (только текстовые команды)
app/handlers/video_uniquifier_handler.py
"""
import os
import asyncio
import tempfile
import logging
from pathlib import Path
from aiogram import Router, types, F
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from datetime import datetime

from app.config import settings
from app.services.video_uniquifier_service import video_uniquifier_service

logger = logging.getLogger(__name__)

# Создаем роутер
router = Router()

# FSM состояния
class VideoProcessingStates(StatesGroup):
    waiting_for_video = State()
    processing_video = State()

@router.message(F.text == "m_video_unikal")
async def start_video_uniquifier_text(message: types.Message, state: FSMContext):
    """Запуск процесса создания уникальных видео через текстовое сообщение"""
    # Проверяем завершен ли онбординг
    from app.database.connection import AsyncSessionLocal
    from app.database.crud import UserCRUD
    from app.database.models import OnboardingStage
    
    async with AsyncSessionLocal() as session:
        user = await UserCRUD.get_user_by_telegram_id(session, message.from_user.id)
        if not user or user.onboarding_stage != OnboardingStage.COMPLETED:
            await message.answer("❌ Сначала завершите онбординг")
            return
    
    logger.info(f"User {message.from_user.id} started video uniquifier via text")
    
    intro_text = """
🎥 <b>Создание уникальных видео</b>

**Пожалуйста, отправьте видео 🎥 в чат.**

После получения бот начнёт его обработку, создаст уникальную версию видео для каждого участника программы и сохранит её на Google Диске в папке с именем участника.

⚠️ <b>Важно:</b>
• Видео должно быть в формате MP4
• Рекомендуемый размер: до 100 МБ
• Процесс может занять несколько минут

🔧 <b>Что будет сделано:</b>
• Для каждого пользователя создается уникальная версия
• Применяются небольшие изменения (масштаб, цвет, водяные знаки)
• Видео сохраняются в персональные папки на Google Drive
"""
    
    await message.answer(intro_text, parse_mode="HTML")
    await state.set_state(VideoProcessingStates.waiting_for_video)

@router.message(VideoProcessingStates.waiting_for_video, F.video)
async def handle_video_upload(message: types.Message, state: FSMContext):
    """Обработка загруженного видео"""
    logger.info(f"Video uploaded by user {message.from_user.id}")
    
    try:
        video = message.video
        
        # Проверяем размер файла (лимит 100 МБ)
        max_size = 100 * 1024 * 1024  # 100 МБ в байтах
        if video.file_size > max_size:
            await message.answer(
                f"❌ <b>Файл слишком большой!</b>\n\n"
                f"Размер: {video.file_size / 1024 / 1024:.1f} МБ\n"
                f"Максимум: 100 МБ\n\n"
                f"Пожалуйста, сожмите видео и попробуйте снова.",
                parse_mode="HTML"
            )
            return
        
        # Проверяем длительность (лимит 10 минут)
        if video.duration > 600:  # 10 минут
            await message.answer(
                f"❌ <b>Видео слишком длинное!</b>\n\n"
                f"Длительность: {video.duration // 60}:{video.duration % 60:02d}\n"
                f"Максимум: 10:00\n\n"
                f"Пожалуйста, обрежьте видео и попробуйте снова.",
                parse_mode="HTML"
            )
            return
        
        # Устанавливаем состояние обработки
        await state.set_state(VideoProcessingStates.processing_video)
        
        # Показываем информацию о видео
        video_info = f"""
✅ <b>Видео получено!</b>

📊 <b>Информация о файле:</b>
• Название: {video.file_name or 'Без названия'}
• Размер: {video.file_size / 1024 / 1024:.1f} МБ
• Длительность: {video.duration // 60}:{video.duration % 60:02d}
• Разрешение: {video.width}x{video.height}

🔄 <b>Начинаем обработку...</b>
Это может занять несколько минут. Мы уведомим вас о прогрессе.
"""
        
        progress_message = await message.answer(video_info, parse_mode="HTML")
        
        # Сохраняем ID сообщения прогресса
        await state.update_data(progress_message_id=progress_message.message_id)
        
        # Скачиваем видео
        processing_text = "📥 Скачивание видео..."
        await progress_message.edit_text(
            video_info + "\n" + processing_text,
            parse_mode="HTML"
        )
        
        # Создаем временный файл
        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as temp_file:
            temp_video_path = temp_file.name
        
        try:
            # Скачиваем файл
            logger.info(f"Starting download of video {video.file_id} to {temp_video_path}")
            await message.bot.download(video.file_id, temp_video_path)
            if os.path.exists(temp_video_path):
                logger.info(f"Video successfully downloaded to {temp_video_path}, size: {os.path.getsize(temp_video_path)} bytes")
            else:
                logger.error(f"Failed to download video to {temp_video_path}")
            
            logger.info(f"Video downloaded to {temp_video_path}")
            
            # Запускаем обработку в фоне
            asyncio.create_task(
                process_video_for_users(
                    temp_video_path,
                    message.from_user.id,
                    progress_message,
                    state
                )
            )
            
        except Exception as e:
            # Удаляем временный файл в случае ошибки
            if os.path.exists(temp_video_path):
                os.unlink(temp_video_path)
            raise e
            
    except Exception as e:
        logger.error(f"Error handling video upload: {e}")
        await message.answer(
            f"❌ <b>Ошибка при обработке видео:</b>\n\n{str(e)}",
            parse_mode="HTML"
        )
        await state.clear()

@router.message(VideoProcessingStates.waiting_for_video)
async def handle_non_video_message(message: types.Message, state: FSMContext):
    """Обработка сообщений, которые не являются видео"""
    await message.answer(
        "⚠️ <b>Пожалуйста, отправьте видео файл</b>\n\n"
        "Поддерживаются только видео в формате MP4.\n"
        "Для отмены напишите /cancel или любое другое сообщение после завершения.",
        parse_mode="HTML"
    )

async def process_video_for_users(temp_video_path: str, user_id: int, 
                                progress_message: types.Message, state: FSMContext):
    """Фоновая обработка видео для всех пользователей"""
    try:
        logger.info(f"Starting background video processing for user {user_id}")
        
        # Функция для обновления прогресса (закомментировано для пользователей)
        async def update_progress(current: int, total: int, current_user: str):
            try:
                progress_percent = int((current / total) * 100)
                
                progress_text = f"""
✅ <b>Видео получено!</b>

🔄 <b>Обработка видео...</b>

📊 <b>Прогресс:</b> {current}/{total} ({progress_percent}%)
👤 <b>Текущий пользователь:</b> {current_user}

⏳ Пожалуйста, подождите. Процесс может занять несколько минут.
"""
                
                # Закомментировано: обновление сообщений для пользователей
                """
                await progress_message.edit_text(progress_text, parse_mode="HTML")
                """
                
                # Логируем прогресс для админа
                logger.info(f"Progress: {current}/{total} ({progress_percent}%) for user {current_user}")
                
            except Exception as e:
                logger.error(f"Error updating progress: {e}")
        
        # Запускаем обработку
        result = await video_uniquifier_service.process_video_for_all_users(
            temp_video_path,
            progress_callback=update_progress
        )
        
        # Формируем финальное сообщение (закомментировано для пользователей)
        if result['success']:
            final_text = f"""
🎉 <b>Обработка завершена успешно!</b>

📊 <b>Результаты:</b>
• Обработано: {result['processed']}/{result['total']} пользователей
• Успешность: {result['success_rate']:.1f}%

✅ Уникальные видео созданы и сохранены в персональные папки пользователей на Google Drive.

📁 Все видео находятся в папке "видео-материалы" → [имя пользователя]

🔄 Для обработки другого видео напишите: m_video_unikal
"""
            
            if result.get('errors'):
                final_text += f"\n⚠️ Ошибки ({len(result['errors'])} шт.):\n"
                for error in result['errors'][:3]:  # Показываем только первые 3 ошибки
                    final_text += f"• {error}\n"
                if len(result['errors']) > 3:
                    final_text += f"• ... и еще {len(result['errors']) - 3} ошибок"
        else:
            final_text = f"""
❌ <b>Обработка завершена с ошибками</b>

📊 <b>Результаты:</b>
• Обработано: {result['processed']}/{result['total']} пользователей
• Успешность: {result['success_rate']:.1f}%

❌ <b>Основные ошибки:</b>
{chr(10).join(f"• {error}" for error in result.get('errors', ['Неизвестная ошибка'])[:5])}

🔄 Для повторной попытки напишите: m_video_unikal
Обратитесь к администратору для решения проблем.
"""
        
        # Закомментировано: отправка финального сообщения пользователю
        """
        try:
            await progress_message.edit_text(final_text, parse_mode="HTML")
        except:
            # Если не можем отредактировать, отправляем новое сообщение
            await progress_message.answer(final_text, parse_mode="HTML")
        """
        
        # Очищаем состояние
        await state.clear()
        
        # Отправляем уведомление админу
        await send_admin_notification(user_id, result)
        
    except Exception as e:
        logger.error(f"Error in background video processing: {e}")
        
        error_text = f"""
❌ <b>Критическая ошибка обработки</b>

Произошла непредвиденная ошибка при обработке видео:
{str(e)}

🔄 Для повторной попытки напишите: m_video_unikal
Пожалуйста, попробуйте позже или обратитесь к администратору.
"""
        
        # Закомментировано: отправка ошибки пользователю
        """
        try:
            await progress_message.edit_text(error_text, parse_mode="HTML")
        except:
            # Если не можем отредактировать, отправляем новое сообщение
            await progress_message.answer(error_text, parse_mode="HTML")
        """
        
        await state.clear()
    
    finally:
        # Всегда удаляем временный файл
        try:
            if os.path.exists(temp_video_path):
                os.unlink(temp_video_path)
                logger.info(f"Temporary video file deleted: {temp_video_path}")
        except Exception as e:
            logger.error(f"Error deleting temp file: {e}")

async def send_admin_notification(user_id: int, result: dict):
    """Отправка уведомления админу о результатах обработки"""
    try:
        from aiogram import Bot
        
        bot = Bot(token=settings.BOT_TOKEN)
        
        notification_text = f"""
📊 <b>Отчет об обработке видео</b>

👤 <b>Инициатор:</b> {user_id}
⏰ <b>Время:</b> {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}

📈 <b>Результаты:</b>
• Обработано: {result['processed']}/{result['total']}
• Успешность: {result['success_rate']:.1f}%
• Статус: {'✅ Успешно' if result['success'] else '❌ С ошибками'}

{f"❌ Ошибки: {len(result.get('errors', []))}" if result.get('errors') else "✅ Ошибок нет"}
"""
        
        await bot.send_message(
            chat_id=settings.ADMIN_ID,
            text=notification_text,
            parse_mode="HTML"
        )
        
        await bot.session.close()
        
    except Exception as e:
        logger.error(f"Error sending admin notification: {e}")

# Функция для регистрации хэндлеров
def register_video_uniquifier_handlers(dp):
    """Регистрация хэндлеров обработки видео"""
    dp.include_router(router)
