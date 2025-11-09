"""
Команда /reset для сброса пользователя и автоматического перезапуска бота
"""
import logging
from aiogram import Router, types
from aiogram.filters import Command
from sqlalchemy import text

from app.database.connection import AsyncSessionLocal
from app.database.models import OnboardingStage
from app.helpers.stage_helper import StageUpdateHelper
from app.config import settings

logger = logging.getLogger(__name__)

router = Router()


@router.message(Command("reset"))
async def reset_user_command(message: types.Message):
    """Полный сброс пользователя и автоматический перезапуск бота"""
    
    telegram_id = message.from_user.id
    logger.info(f"🔄 Reset command triggered for user {telegram_id}")
    
    # Переменная для отслеживания типа пользователя
    is_early_stage_user = False
    
    try:
        async with AsyncSessionLocal() as session:
            # Проверяем существует ли пользователь и его стадию
            check_user = await session.execute(
                text("SELECT id, onboarding_stage, payment_completed FROM users WHERE telegram_id = :tid"),
                {"tid": telegram_id}
            )
            user_data = check_user.fetchone()
            
            if not user_data:
                logger.info(f"User {telegram_id} not found, will be created by /start")
            else:
                user_id = user_data[0]
                current_stage = user_data[1]
                payment_completed = user_data[2]
                logger.info(f"Found user {telegram_id} with id {user_id}, current stage: {current_stage}, paid: {payment_completed}")
                
                # Определяем тип сброса в зависимости от стадии
                early_stages = [OnboardingStage.NEW_USER, OnboardingStage.INTRO_SHOWN, OnboardingStage.WAIT_PAYMENT]
                is_early_stage = current_stage in early_stages
                is_early_stage_user = is_early_stage  # Сохраняем для использования вне блока
                
                # ===== ПОЛНОЕ ОБНУЛЕНИЕ для ВСЕХ =====
                logger.info(f"🔄 User {telegram_id} - performing FULL reset")
                
                # 1. Удаляем payments
                await session.execute(
                    text("DELETE FROM payments WHERE user_id = :uid"),
                    {"uid": user_id}
                )
                logger.info(f"✅ Deleted payments for user {user_id}")
                
                # 2. Удаляем automated_messages
                await session.execute(
                    text("DELETE FROM automated_messages WHERE telegram_id = :tid"),
                    {"tid": telegram_id}
                )
                logger.info(f"✅ Deleted automated_messages for user {telegram_id}")
                
                # 3. Удаляем user_course_progress
                await session.execute(
                    text("DELETE FROM user_course_progress WHERE user_id = :uid"),
                    {"uid": user_id}
                )
                logger.info(f"✅ Deleted course progress for user {user_id}")
                
                # 4. Обнуляем флаги
                await session.execute(
                    text("""
                        UPDATE users 
                        SET payment_completed = FALSE,
                            current_course_step = 0,
                            course_completed_at = NULL,
                            partner_offer_shown_at = NULL,
                            onboarding_completed_at = NULL,
                            stage_intro_shown_at = NULL,
                            stage_wait_payment_at = NULL,
                            stage_payment_ok_at = NULL,
                            stage_want_join_at = NULL,
                            stage_completed_at = NULL
                        WHERE telegram_id = :tid
                    """),
                    {"tid": telegram_id}
                )
                logger.info(f"✅ Full reset for user {telegram_id}")
                
                if is_early_stage:
                    # ===== НЕ ОПЛАТИВШИЕ - стандартный сброс =====
                    logger.info(f"🔵 User {telegram_id} on early stage - standard reset to NEW_USER")
                    
                    # Обновляем стадию на NEW_USER
                    await StageUpdateHelper.update_user_stage(
                        session, telegram_id, OnboardingStage.NEW_USER, message.bot
                    )
                    logger.info(f"✅ Updated stage to NEW_USER for {telegram_id}")
                    
                    # Коммитим изменения для раннего этапа
                    await session.commit()
                    logger.info(f"✅ All changes committed for early-stage user {telegram_id}")
                    
                else:
                    # ===== ОПЛАТИВШИЕ - восстанавливаем доступ БЕЗ создания sale =====
                    logger.info(f"💰 User {telegram_id} was paid - restoring access WITHOUT creating duplicate sale")
                    
                    # ✅ Устанавливаем payment_completed = TRUE
                    from app.database.crud import UserCRUD
                    await UserCRUD.complete_payment(session, telegram_id)
                    logger.info(f"✅ Set payment_completed = TRUE for {telegram_id}")
                    
                    # ❌ НЕ СОЗДАЕМ SALE - она уже существует от реальной оплаты!
                    # Продажа была создана когда админ одобрил платеж через GetCourse/Robokassa
                    # /reset это просто сброс прогресса, а не новая покупка курса
                    
                    # ✅ Обновляем стадию на WANT_JOIN
                    await StageUpdateHelper.update_user_stage(
                        session, telegram_id, OnboardingStage.WANT_JOIN, message.bot
                    )
                    logger.info(f"✅ Updated stage to WANT_JOIN for paid user {telegram_id}")
                    
                    # Коммитим изменения
                    await session.commit()
                    logger.info(f"✅ All changes committed for user {telegram_id}")
                    
                    # КАСКАД: Автоматическая отправка одобрения и первого урока
                    logger.info(f"📤 Sending approval and first lesson to paid user {telegram_id}")
                    try:
                        # Отправляем сообщение об одобрении
                        success_text = """
🎉 <b>Поздравляю! оплата подтверждена!</b>

Смотреть урок ⤵️
"""
                        await message.bot.send_message(
                            chat_id=telegram_id,
                            text=success_text,
                            parse_mode="HTML"
                        )
                        logger.info(f"✅ Approval message sent to {telegram_id}")
                        
                        # Отправляем первый урок
                        await send_first_lesson(message.bot, telegram_id)
                        logger.info(f"✅ First lesson sent to {telegram_id}")
                        
                    except Exception as e:
                        logger.error(f"❌ Error sending approval/lesson to {telegram_id}: {e}")
                    
                    # НЕ вызываем universal_start_handler для оплативших
                    # так как уже все отправили
                    return
        
        # Для НЕ оплативших: вызываем /start чтобы начать с начала
        if not user_data or is_early_stage_user:
            logger.info(f"🚀 Triggering /start for early-stage user {telegram_id}")
            from app.handlers.onboarding.universal_start import universal_start_handler
            await universal_start_handler(message)
        
        logger.info(f"✅ Reset completed successfully for user {telegram_id}")
        
    except Exception as e:
        logger.error(f"❌ Reset error for user {telegram_id}: {e}", exc_info=True)
        await message.answer(
            "❌ Произошла ошибка при сбросе. Попробуйте /start",
            parse_mode="HTML"
        )


async def send_first_lesson(bot, user_id: int):
    """Отправляет первый урок пользователю с защитой от копирования"""
    try:
        # Отправляем заголовок урока с защитой от пересылки
        await bot.send_message(
            chat_id=user_id,
            text="📚 <b>1 Урок. Оформление страницы</b> ⤵️\n\n🔒 <i>Материал защищен от копирования и пересылки</i>",
            parse_mode="HTML",
            protect_content=True  # ✅ Защита от пересылки
        )
        
        # Получаем ID первого урока из настроек
        lesson_1_video_id = getattr(settings, "lesson_1", None)
        
        # Отправляем видео урока с защитой
        if lesson_1_video_id and lesson_1_video_id != "BAACAgIAAxkBAAI...":
            await bot.send_video(
                chat_id=user_id,
                video=lesson_1_video_id,
                caption="🔒 Урок 1 из 5",
                parse_mode="HTML",
                supports_streaming=True,
                protect_content=True  # ✅ Защита от пересылки и сохранения
            )
            logger.info(f"🔒 Урок 1 отправлен с защитой пользователю {user_id}")
        else:
            logger.warning(f"⚠️ Lesson 1 video not configured for user {user_id}")
            await bot.send_message(
                chat_id=user_id,
                text="🔹 <i>Видео временно недоступно</i>",
                parse_mode="HTML",
                protect_content=True
            )
        
        # Создаем кнопку "Следующий урок"
        from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="📖 Смотреть следующий урок ⤵️",
                        callback_data="next_lesson:2"
                    )
                ]
            ]
        )
        
        await bot.send_message(
            chat_id=user_id,
            text="👆 <i>После просмотра нажми кнопку для перехода к следующему уроку</i>",
            reply_markup=keyboard,
            parse_mode="HTML"
        )
        
        logger.info(f"✅ First lesson sent successfully to {user_id}")
        
    except Exception as e:
        logger.error(f"❌ Error sending first lesson to {user_id}: {e}", exc_info=True)