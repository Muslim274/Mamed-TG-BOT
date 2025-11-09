"""
Исправленный хэндлер оплаты с интеграцией Robokassa + GetCourse
"""
import asyncio
import logging
import random
import os

from aiogram.types import FSInputFile

from aiogram import Router, types, F
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardRemove
from typing import Optional, Tuple, Union

from datetime import datetime

from app.database.connection import AsyncSessionLocal
from app.database.crud import UserCRUD, SaleCRUD, ClickCRUD
from app.database.models import OnboardingStage
from app.middlewares.onboarding_check import OnboardingStageMiddleware
from app.utils.constants import ONBOARDING_TEXTS
from app.helpers.stage_helper import StageUpdateHelper
from app.config import settings
from app.services.robokassa_handler import robokassa_handler
from app.services.google_sheets import add_payment_to_sheets, init_google_sheets

logger = logging.getLogger(__name__)

ADMIN_ID = settings.ADMIN_ID
message_links = {}
getcourse_pending = {}

router = Router()

@router.callback_query.middleware()
async def onboarding_filter_middleware(handler, event, data):
    user_id = event.from_user.id
    
    if user_id == ADMIN_ID:
        return await handler(event, data)
    
    # Разрешаем GetCourse callback'ы для админа
    if (event.data and (event.data.startswith("admin_approve_getcourse:") or 
                       event.data.startswith("admin_reject_getcourse:"))):
        return await handler(event, data)
    
    if (event.data and event.data.startswith("joined_community:")):
        return await handler(event, data)
    
    allowed_stages = [
        OnboardingStage.NEW_USER,
        OnboardingStage.INTRO_SHOWN,
        OnboardingStage.WAIT_PAYMENT,
        OnboardingStage.PAYMENT_OK,
        OnboardingStage.WANT_JOIN,
        OnboardingStage.READY_START,
        OnboardingStage.PARTNER_LESSON,
        OnboardingStage.LESSON_DONE,
        OnboardingStage.GOT_LINK,
        OnboardingStage.COMPLETED
    ]
    
    onboarding_stage = data.get('onboarding_stage', OnboardingStage.NEW_USER)
    
    if onboarding_stage not in allowed_stages:
        logger.debug(f"Skipping handler for user {user_id} - stage {onboarding_stage} not allowed")
        return
    
    return await handler(event, data)

def get_integrated_payment_keyboard(payment_url: str = None):
    keyboard_buttons = []
    
    if settings.ONBOARDING_MOCK_PAYMENT:
        keyboard_buttons.extend([
            [
                InlineKeyboardButton(
                    text="✅ Robokassa: Оплата прошла (ТЕСТ)",
                    callback_data="payment_success"
                )
            ],
            [
                InlineKeyboardButton(
                    text="❌ Robokassa: Не оплатил (ТЕСТ)",
                    callback_data="payment_cancel"
                )
            ]
        ])
    else:
        if payment_url:
            keyboard_buttons.extend([
                [
                    InlineKeyboardButton(
                        text="💳 Перейти к оплате",
                        url=payment_url
                    )
                # ],
                # [
                    # InlineKeyboardButton(
                        # text="✅ Robokassa: Я оплатил",
                        # callback_data="payment_check"
                    # )
                ]
            ])
        # else:
            # keyboard_buttons.append([
                # InlineKeyboardButton(
                    # text="❌ Robokassa: Ошибка создания платежа",
                    # callback_data="payment_error"
                # )
            # ])
    
    keyboard_buttons.extend([
        # [
            # InlineKeyboardButton(
                # text="💳 Перейти к оплате",
                ## url="https://web.tribute.tg/p/krq"
                # url="https://tets-desert-school.getcourse.ru/affiliate"
                
            # )
        # ],
        [
            InlineKeyboardButton(
                text="🔐 Оплата криптой",
                callback_data="show_crypto_payment"
            )
        ],
        [
            InlineKeyboardButton(
                text="✅ Я оплатил(а)",
                callback_data="getcourse_payment_confirm"
            )
        ],
        [
            InlineKeyboardButton(
                text="❓ Задать вопрос, у меня не получается",
                callback_data="ask_question_help"
            )
        ]        
    ])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)

@router.callback_query(F.data == "intro_continue")
async def intro_continue(callback: types.CallbackQuery, onboarding_user):
    logger.info("User %s continuing after intro - showing INTEGRATED payment options", callback.from_user.id)
    
    price = settings.ONBOARDING_COURSE_PRICE
    formatted_amount = f"{price:,.0f}".replace(",", "\u202F") + f" {settings.ONBOARDING_COURSE_CURRENCY}"

    payment_text = f"""
📚 <b>Урок «Инструкция партнерской системы»</b>

💡 <b>Бонус:</b>
• Место в команде Мамеда 🧑‍💻
• Поддержка команды 💪

<b>Стоимость: {formatted_amount}</b>

<i>Внимание! Оплата по частям не относится к нашей программе т.к. противоречат нашим религиозным принципам! Мы принимаем оплату только полной стоимости продукта ✅</i>
"""

    try:
        # Создаем платеж через Robokassa
        payment_url = None
        if not settings.ONBOARDING_MOCK_PAYMENT:
            try:
                payment_url, invoice_id = await robokassa_handler.create_payment(
                    user_id=callback.from_user.id,
                    amount=settings.ONBOARDING_COURSE_PRICE,
                    description="Онбординг курс партнерской программы"
                )
                logger.info(f"✅ Robokassa payment created: {invoice_id}")
            except Exception as e:
                logger.error(f"❌ Error creating Robokassa payment: {e}")

        keyboard = get_integrated_payment_keyboard(payment_url)
        
        
        
        # Обновляем стадию пользователя до WAIT_PAYMENT
        async with AsyncSessionLocal() as session:
            await StageUpdateHelper.update_user_stage(session, callback.from_user.id, OnboardingStage.WAIT_PAYMENT, callback.bot)
            await session.commit()  # Обязательно коммитим изменения!
            logger.info(f"✅ Пользователь {callback.from_user.id} переведен в стадию WAIT_PAYMENT")
        
        await callback.message.answer(
            payment_text, 
            parse_mode="HTML", 
            reply_markup=keyboard
        )
        await callback.answer("🚀 Выберите способ оплаты!")
        
    except Exception as e:
        logger.error("Error in intro_continue: %s", e, exc_info=True)
        await callback.answer("❌ Произошла ошибка", show_alert=True)

@router.callback_query(F.data == "getcourse_payment_confirm")
async def getcourse_payment_confirm(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    logger.info(f"🎓 User {user_id} confirmed GetCourse payment")
    
    try:
        if user_id in getcourse_pending:
            last_request = getcourse_pending[user_id]["timestamp"]
            time_diff = (datetime.now() - last_request).total_seconds()
            
            if time_diff < 300:
                await callback.answer(
                    "⏳ GetCourse заявка уже отправлена! Ожидайте подтверждения администратора.",
                    show_alert=True
                )
                return
        
        async with AsyncSessionLocal() as session:
            user = await UserCRUD.get_user_by_telegram_id(session, user_id)
        
        if not user:
            await callback.answer("❌ Ошибка: пользователь не найден", show_alert=True)
            return
        
        user_info = {
            "telegram_id": user_id,
            "username": callback.from_user.username,
            "full_name": callback.from_user.full_name,
            "ref_code": user.ref_code,
            "referred_by": user.referred_by
        }
        
        getcourse_pending[user_id] = {
            "timestamp": datetime.now(),
            "user_info": user_info
        }
        
        await send_getcourse_confirmation_to_admin(callback.message.bot, user_info)
        
        confirmation_text = f"""
✅ <b>Отлично! Заявка на подтверждение оплаты отправлена!</b>

⏳ Скоро мы тебе откроем доступ к урокам


"""
        
        await callback.message.answer(confirmation_text, parse_mode="HTML")
        await callback.answer("✅ GetCourse заявка отправлена!")
        
        logger.info(f"✅ GetCourse payment confirmation request sent to admin for user {user_id}")
        
    except Exception as e:
        logger.error(f"❌ Error in getcourse_payment_confirm: {e}")
        await callback.answer("❌ Ошибка отправки GetCourse заявки", show_alert=True)

async def send_getcourse_confirmation_to_admin(bot, user_info):
    try:
        user_display = f"@{user_info['username']}" if user_info['username'] else "Без username"
        current_time = datetime.now().strftime("%d.%m.%Y %H:%M:%S")
        
        price = settings.ONBOARDING_COURSE_PRICE
        formatted_amount = f"{price:,.0f}".replace(",", " ") + f" {settings.ONBOARDING_COURSE_CURRENCY}"
        
        admin_message = f"""
🎓 <b>GETCOURSE: ЗАЯВКА НА ПОДТВЕРЖДЕНИЕ ОПЛАТЫ</b>

👤 <b>Пользователь:</b> {user_info['full_name']}
🆔 <b>Telegram ID:</b> <code>{user_info['telegram_id']}</code>
🅰️ <b>Username:</b> {user_display}
🔗 <b>Реф. код:</b> {user_info['ref_code']}
👥 <b>Пригласил:</b> {user_info['referred_by'] or 'Самостоятельно'}

💰 <b>Сумма:</b> {formatted_amount}
⏰ <b>Время заявки:</b> {current_time}
🎓 <b>Способ оплаты:</b> GetCourse

<b>❓ Проверьте поступление платежа в GetCourse системе и подтвердите:</b>
"""
        
        admin_keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="✅ GETCOURSE: ПОДТВЕРДИТЬ ОПЛАТУ",
                        callback_data=f"admin_approve_getcourse:{user_info['telegram_id']}"
                    )
                ],
                [
                    InlineKeyboardButton(
                        text="❌ GETCOURSE: ОТКЛОНИТЬ",
                        callback_data=f"admin_reject_getcourse:{user_info['telegram_id']}"
                    )
                ]
            ]
        )
        
        await bot.send_message(
            chat_id=settings.ADMIN_ID,
            text=admin_message,
            parse_mode="HTML",
            reply_markup=admin_keyboard
        )
        
        logger.info(f"✅ GetCourse confirmation sent to admin for user {user_info['telegram_id']}")
        
    except Exception as e:
        logger.error(f"❌ Error sending GetCourse confirmation to admin: {e}")

@router.callback_query(F.data.startswith("admin_approve_getcourse:"))
async def admin_approve_getcourse_payment(callback: types.CallbackQuery):
    if callback.from_user.id != settings.ADMIN_ID:
        await callback.answer("❌ Доступ запрещен", show_alert=True)
        return
    
    try:
        user_id = int(callback.data.split(":")[1])
        logger.info(f"🎓 Admin approving GetCourse payment for user {user_id}")
        
        if user_id not in getcourse_pending:
            await callback.answer("❌ GetCourse заявка не найдена или уже обработана", show_alert=True)
            return
        
        async with AsyncSessionLocal() as session:
            success = await UserCRUD.complete_payment(session, user_id)
            
            if not success:
                await callback.answer("❌ Ошибка обновления БД", show_alert=True)
                return
            
            # НОВАЯ ЛОГИКА: Получаем последнего реферала
            last_referrer_code = await UserCRUD.get_last_referrer(session, user_id)
            
            invited_by_telegram_id = None
            if last_referrer_code:
                referrer = await UserCRUD.get_user_by_ref_code(session, last_referrer_code)
                if referrer:
                    invited_by_telegram_id = referrer.telegram_id
                    
                    sale = await SaleCRUD.create_sale(
                        session=session,
                        ref_code=last_referrer_code,
                        amount=float(settings.ONBOARDING_COURSE_PRICE),
                        commission_percent=float(settings.COMMISSION_PERCENT),
                        customer_email=f"user_{user_id}",
                        product="Onboarding Course (GetCourse)"
                    )
                    
                    logger.info(f"🎉 GetCourse sale created: ID={sale.id}, commission={sale.commission_amount}")
                    
                    # Логируем в историю
                    from app.database.crud import ReferralHistoryCRUD
                    await ReferralHistoryCRUD.log_action(
                        session=session,
                        user_telegram_id=user_id,
                        ref_code=last_referrer_code,
                        action_type="payment",
                        amount=sale.amount,
                        commission_amount=sale.commission_amount
                    )
                    
                    await send_sale_notification(
                        bot=callback.message.bot,
                        referrer_telegram_id=referrer.telegram_id,
                        sale_amount=sale.amount,
                        commission_amount=sale.commission_amount,
                        payment_method="GetCourse"
                    )
        
        await send_getcourse_approved_to_user(callback.message.bot, user_id)
        
        del getcourse_pending[user_id]
        
        approved_text = f"""
✅ <b>GETCOURSE: ОПЛАТА ПОДТВЕРЖДЕНА</b>

{callback.message.text}

<i>✅ Обработано: {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}</i>
"""
        
        await callback.message.edit_text(approved_text, parse_mode="HTML")
        await callback.answer("✅ GetCourse оплата подтверждена!")
        
        asyncio.create_task(record_payment_to_sheets(
            telegram_id=user_id,
            username=getcourse_pending.get(user_id, {}).get("user_info", {}).get("username"),
            user_ref_code=getcourse_pending.get(user_id, {}).get("user_info", {}).get("ref_code"),
            invited_by_telegram_id=invited_by_telegram_id,
            payment_method="GetCourse"
        ))
        
        logger.info(f"✅ GetCourse payment approved by admin for user {user_id}")
        
    except Exception as e:
        logger.error(f"❌ Error in admin_approve_getcourse_payment: {e}")
        await callback.answer("❌ Ошибка подтверждения GetCourse", show_alert=True)

@router.callback_query(F.data.startswith("admin_reject_getcourse:"))
async def admin_reject_getcourse_payment(callback: types.CallbackQuery):
    if callback.from_user.id != settings.ADMIN_ID:
        await callback.answer("❌ Доступ запрещен", show_alert=True)
        return
    
    try:
        user_id = int(callback.data.split(":")[1])
        logger.info(f"🎓 Admin rejecting GetCourse payment for user {user_id}")
        
        if user_id not in getcourse_pending:
            await callback.answer("❌ GetCourse заявка не найдена или уже обработана", show_alert=True)
            return
        
        await send_getcourse_rejected_to_user(callback.message.bot, user_id)
        
        del getcourse_pending[user_id]
        
        rejected_text = f"""
❌ <b>GETCOURSE: ОПЛАТА ОТКЛОНЕНА</b>

{callback.message.text}

<i>❌ Отклонено: {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}</i>
"""
        
        await callback.message.edit_text(rejected_text, parse_mode="HTML")
        await callback.answer("❌ GetCourse оплата отклонена!")
        
        logger.info(f"❌ GetCourse payment rejected by admin for user {user_id}")
        
    except Exception as e:
        logger.error(f"❌ Error in admin_reject_getcourse_payment: {e}")
        await callback.answer("❌ Ошибка отклонения GetCourse", show_alert=True)

async def send_getcourse_approved_to_user(bot, user_id):
    try:
        success_text = """
🎉 <b>Поздравляю! оплата подтверждена!</b>

Смотреть урок ⤵️
"""
        
        await bot.send_message(
            chat_id=user_id,
            text=success_text,
            parse_mode="HTML"
        )
        
        # Сразу вызываем основную функцию с видео
        await send_getcourse_approved_video(bot, user_id)
        
        logger.info(f"✅ GetCourse payment approval sent to user {user_id}")
        
    except Exception as e:
        logger.error(f"❌ Error sending GetCourse approval to user: {e}")



async def send_getcourse_rejected_to_user(bot, user_id):
    try:
        rejection_text = f"""
❌ <b>GetCourse оплата не подтверждена</b>

К сожалению, ваша GetCourse оплата не была найдена в системе.

💡 <b>Возможные причины:</b>
• Платеж еще обрабатывается системой GetCourse
• Указаны неверные данные при оплате
• Технические проблемы платежной системы

🔄 <b>Что делать:</b>
• Проверьте списание средств с карты/счета
• Попробуйте оплатить через Robokassa
• Обратитесь в поддержку с чеком об оплате

💬 <b>Связаться с поддержкой</b> {settings.SUPPORT_CONTACT}
"""
        
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="🔄 К выбору способа оплаты",
                        callback_data="intro_continue"
                    )
                ],
                [
                    InlineKeyboardButton(
                        text="💬 Связаться с поддержкой",
                        callback_data="ask_question_help"
                    )
                ]
            ]
        )
        
        await bot.send_message(
            chat_id=user_id,
            text=rejection_text,
            parse_mode="HTML",
            reply_markup=keyboard
        )
        
        logger.info(f"❌ GetCourse payment rejection sent to user {user_id}")
        
    except Exception as e:
        logger.error(f"❌ Error sending GetCourse rejection to user: {e}")



async def send_instruction_pdf(bot, user_id: int) -> None:
    """Отправляет сообщение с кнопкой 'ХОЧУ В КОМАНДУ!'"""
    logger.info(f"📤 Отправка сообщения о завершении обучения пользователю {user_id}")
    
    try:
        # Создаем клавиатуру с кнопкой
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="🚀 ХОЧУ В КОМАНДУ МАМЕДА!",
                        callback_data="send_video_guide"
                    )
                ]
            ]
        )
        
        # Текст сообщения
        completion_text = """
<b>Поздравляю тебя с завершением обучения💪</b>

Если хочешь стать моим партнёром и работать в нашей команде, то нажми на кнопку внизу⤵️
"""
        
        # Отправляем сообщение с кнопкой
        await bot.send_message(
            chat_id=user_id,
            text=completion_text,
            parse_mode="HTML",
            reply_markup=keyboard
        )
        
        logger.info(f"✅ Сообщение о завершении обучения успешно отправлено пользователю {user_id}")
        
    except Exception as e:
        logger.error(f"❌ Ошибка при отправке сообщения: {e}", exc_info=True)
        await bot.send_message(
            chat_id=user_id, 
            text="❌ Ошибка отправки сообщения. Попробуйте позже или обратитесь в поддержку."
        )
            
            
async def send_getcourse_approved_video(bot, user_id: int):
    """Отправляет первый урок и запускает последовательное обучение"""
    try:
        # Обновляем стадию онбординга
        async with AsyncSessionLocal() as session:
            await StageUpdateHelper.update_user_stage(session, user_id, OnboardingStage.WANT_JOIN, bot)
        
        # Отправляем только первый урок
        await send_lesson(bot, user_id, lesson_number=1)
        logger.info(f"✅ First lesson sent to user {user_id}")
        
    except Exception as e:
        logger.error(f"❌ Error starting lessons: {e}")


"""
🔒 ПРОСТАЯ ЗАЩИТА УРОКОВ - БЕЗ КРУГЛЫХ ВИДЕО
Обычное видео + protect_content
"""

async def send_lesson(bot, user_id: int, lesson_number: int):
    """Отправляет конкретный урок с кнопкой продолжения"""
    
    lessons = [
        ("1 Урок. Оформление страниц", getattr(settings, "lesson_1", None)),
        ("2 Урок. Подготовка видео", getattr(settings, "lesson_2", None)),
        ("3 Урок. Уникализация", getattr(settings, "lesson_3", None)),
        ("4 Урок. Правила публикации", getattr(settings, "lesson_4", None)),
        ("5 Урок. Стратегия продаж", getattr(settings, "lesson_5", None))
    ]
    
    if lesson_number < 1 or lesson_number > len(lessons):
        logger.error(f"❌ Invalid lesson number: {lesson_number}")
        return
    
    lesson_title, lesson_video_id = lessons[lesson_number - 1]
    
    try:
        # Отправляем заголовок урока с защитой от пересылки
        await bot.send_message(
            chat_id=user_id,
            text=f"📚 <b>{lesson_title}</b> ⤵️\n\n🔒 <i>Материал защищен от копирования и пересылки</i>",
            parse_mode="HTML",
            protect_content=True  # ✅ Защита от пересылки
        )
        
        # Отправляем ОБЫЧНОЕ видео урока с защитой
        if lesson_video_id and lesson_video_id != "BAACAgIAAxkBAAI...":
            await bot.send_video(
                chat_id=user_id,
                video=lesson_video_id,
                caption=f"🔒 Урок {lesson_number} из {len(lessons)}",
                parse_mode="HTML",
                supports_streaming=True,
                protect_content=True  # ✅ Защита от пересылки и сохранения
            )
            logger.info(f"🔒 Урок {lesson_number} отправлен с защитой пользователю {user_id}")
        else:
            logger.warning(f"⚠️ Видео для {lesson_title} не найдено для пользователя {user_id}")
            await bot.send_message(
                chat_id=user_id,
                text="📹 <i>Видео временно недоступно</i>",
                parse_mode="HTML",
                protect_content=True
            )
        
        # Создаем кнопку в зависимости от номера урока
        if lesson_number < len(lessons):
            # Кнопка "Следующий урок"
            keyboard = InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        InlineKeyboardButton(
                            text="📖 Смотреть следующий урок ⤵️",
                            callback_data=f"next_lesson:{lesson_number + 1}"
                        )
                    ]
                ]
            )
            
            message = await bot.send_message(
                chat_id=user_id,
                text="👆 <i>После просмотра нажми кнопку для перехода к следующему уроку</i>",
                parse_mode="HTML",
                reply_markup=keyboard
            )
            
            # Сохраняем ID сообщения для последующего удаления
            if not hasattr(bot, 'user_button_messages'):
                bot.user_button_messages = {}
            bot.user_button_messages[user_id] = message.message_id
        else:
            # Последний урок - показываем кнопку "Продолжить"
            keyboard = InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        InlineKeyboardButton(
                            text="📖 Продолжить",
                            callback_data="complete_lessons"
                        )
                    ]
                ]
            )
            
            message = await bot.send_message(
                chat_id=user_id,
                text="👆 После просмотра нажми кнопку «📖 Продолжить», <b>и переходи к следующему шагу</b>.",
                parse_mode="HTML",
                reply_markup=keyboard
            )
            
            # Сохраняем ID сообщения для последующего удаления
            if not hasattr(bot, 'user_complete_messages'):
                bot.user_complete_messages = {}
            bot.user_complete_messages[user_id] = message.message_id
            
    except Exception as e:
        logger.error(f"❌ Error sending lesson {lesson_number}: {e}")



async def complete_lessons(bot, user_id: int):
    """Завершает показ всех уроков и отправляет финальные материалы"""
    try:
        # Отправляем фото (ИСПРАВЛЕНО)
        from aiogram.types import FSInputFile
        photo_path = "/root/telegram-referral-bot/faq_1.png"
        try:
            photo_file = FSInputFile(path=photo_path, filename="faq_1.png")
            await bot.send_photo(
                chat_id=user_id,
                photo=photo_file
            )
        except FileNotFoundError:
            logger.warning(f"⚠️ Фото {photo_path} не найдено для пользователя {user_id}")
        except Exception as e:
            logger.error(f"❌ Ошибка отправки фото: {e}")
        
        # После всех видео отправляем инструкцию PDF (теперь упрощенную)
        await send_instruction_pdf(bot, user_id)
        logger.info(f"✅ All lessons completed for user {user_id}")
        
    except Exception as e:
        logger.error(f"❌ Error completing lessons: {e}")


# Обработчик кнопок "Следующий урок" и "Продолжить"
@router.callback_query(F.data.startswith("next_lesson:"))
async def handle_next_lesson(callback: types.CallbackQuery):
    """Обработчик перехода к следующему уроку"""
    try:
        # Извлекаем номер урока из callback_data
        lesson_number = int(callback.data.split(":")[1])
        user_id = callback.from_user.id
        
        logger.info(f"User {user_id} requesting lesson {lesson_number}")
        
        # Удаляем сообщение с кнопкой и текстом полностью
        try:
            if hasattr(callback.message.bot, 'user_button_messages') and user_id in callback.message.bot.user_button_messages:
                message_id = callback.message.bot.user_button_messages[user_id]
                await callback.message.bot.delete_message(chat_id=user_id, message_id=message_id)
                del callback.message.bot.user_button_messages[user_id]
        except Exception as e:
            logger.warning(f"Could not delete button message: {e}")
        
        # Отправляем следующий урок
        await send_lesson(callback.message.bot, user_id, lesson_number)
        
        await callback.answer(f"▶️ Урок {lesson_number}")
        
    except Exception as e:
        logger.error(f"❌ Error handling next lesson: {e}")
        await callback.answer("❌ Ошибка перехода к уроку", show_alert=True)


@router.callback_query(F.data == "complete_lessons")
async def handle_complete_lessons(callback: types.CallbackQuery):
    """Обработчик завершения всех уроков"""
    try:
        user_id = callback.from_user.id
        logger.info(f"User {user_id} completing all lessons")
        
        # Удаляем сообщение с кнопкой "Продолжить" полностью
        try:
            if hasattr(callback.message.bot, 'user_complete_messages') and user_id in callback.message.bot.user_complete_messages:
                message_id = callback.message.bot.user_complete_messages[user_id]
                await callback.message.bot.delete_message(chat_id=user_id, message_id=message_id)
                del callback.message.bot.user_complete_messages[user_id]
        except Exception as e:
            logger.warning(f"Could not delete complete button message: {e}")
        
        # Отправляем финальные материалы
        await complete_lessons(callback.message.bot, user_id)
        
        await callback.answer("🎓 Завершение обучения")
        
    except Exception as e:
        logger.error(f"❌ Error completing lessons: {e}")
        await callback.answer("❌ Ошибка завершения", show_alert=True)

async def record_payment_to_sheets(
    telegram_id: int, 
    username: str = None, 
    user_ref_code: str = None, 
    invited_by_telegram_id: int = None,
    payment_method: str = "Unknown"
):
    try:
        logger.info(f"📊 STARTING Google Sheets recording for user {telegram_id} via {payment_method}")
        
        # Открываем сессию и берем актуальные данные о пользователе и приглашающем
        async with AsyncSessionLocal() as session:
            user = await UserCRUD.get_user_by_telegram_id(session, telegram_id)
            if not user:
                logger.error(f"❌ User {telegram_id} not found in DB")
                return
            
            # user_ref_code
            user_ref_code = user.ref_code
            
            # ✅ ИСПРАВЛЕНИЕ: Используем НОВУЮ логику get_last_referrer
            real_invited_by_telegram_id = None
            
            # Получаем последний реферальный код (из кликов или fallback на referred_by)
            last_referrer_code = await UserCRUD.get_last_referrer(session, telegram_id)
            
            if last_referrer_code:
                logger.info(f"🔗 Last referrer code found: {last_referrer_code}")
                referrer = await UserCRUD.get_user_by_ref_code(session, last_referrer_code)
                if referrer:
                    real_invited_by_telegram_id = referrer.telegram_id
                    logger.info(f"🔗 Referrer found: {real_invited_by_telegram_id}")
                else:
                    logger.warning(f"⚠️ Referrer with code {last_referrer_code} not found")
            else:
                logger.info(f"ℹ️ User {telegram_id} has no referrer")
            
            username = user.username  # username берем из БД
            
        # Инициализация и запись в Google Sheets
        logger.info(f"📊 Initializing Google Sheets...")
        success = await init_google_sheets()
        if not success:
            logger.error("❌ Failed to initialize Google Sheets")
            return

        logger.info(f"✅ Google Sheets initialized")
        await add_payment_to_sheets(
            telegram_id=telegram_id,
            username=username,
            user_ref_code=user_ref_code,
            invited_by_telegram_id=real_invited_by_telegram_id
        )
        logger.info(f"✅ {payment_method} payment recorded to Google Sheets: {telegram_id} (referrer: {real_invited_by_telegram_id})")

    except Exception as e:
        logger.error(f"❌ Error recording {payment_method} payment to Google Sheets: {e}", exc_info=True)


async def send_sale_notification(bot, referrer_telegram_id: int, sale_amount: float, commission_amount: float, payment_method: str = "Unknown"):
    try:
        async with AsyncSessionLocal() as session:
            referrer = await UserCRUD.get_user_by_telegram_id(session, referrer_telegram_id)
            if referrer:
                total_commission = await SaleCRUD.get_total_commission(session, referrer.ref_code)
                formatted_balance = f"{total_commission:,.0f} руб.".replace(",", " ")
                logger.info(f"📊 Referrer {referrer_telegram_id} total balance: {total_commission}")
            else:
                formatted_balance = "0 руб."
                logger.warning(f"❌ Referrer {referrer_telegram_id} not found for balance calculation")
        
        formatted_commission = f"{commission_amount:,.0f} руб.".replace(",", " ")
        
        notification_text = f"""
🎉 <b>Новая продажа по вашей ссылке!</b>

💵 <b>Ваша комиссия:</b> {formatted_commission}
💰 <b>Мой баланс:</b> {formatted_balance}


"""
        
        await bot.send_message(
            chat_id=referrer_telegram_id,
            text=notification_text,
            parse_mode="HTML"
        )
        
        logger.info(f"✅ {payment_method} sale notification sent to referrer {referrer_telegram_id}, commission: {formatted_commission}, balance: {formatted_balance}")
        
    except Exception as e:
        logger.error(f"❌ Error sending {payment_method} sale notification: {e}", exc_info=True)

@router.callback_query(F.data == "payment_error")
async def payment_error(callback: types.CallbackQuery):
    error_text = f"""
❌ <b>Ошибка создания Robokassa платежа</b>

Произошла техническая ошибка при создании платежа через Robokassa.

💡 <b>Что делать:</b>
- Попробуйте еще раз через несколько минут
- Попробуйте оплату через GetCourse
- Свяжитесь с поддержкой если проблема повторяется

📞 <b>Поддержка:</b> {settings.SUPPORT_CONTACT}
"""
    
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🔄 Попробовать снова",
                    callback_data="intro_continue"
                )
            ],
            [
                InlineKeyboardButton(
                    text="💬 Связаться с поддержкой",
                    callback_data="main_support"
                )
            ]
        ]
    )
    
    await callback.message.edit_text(error_text, parse_mode="HTML", reply_markup=keyboard)
    await callback.answer()

@router.callback_query(F.data == "payment_check")
async def payment_check(callback: types.CallbackQuery):
    logger.info(f"User {callback.from_user.id} checking Robokassa payment status")
    
    try:
        async with AsyncSessionLocal() as session:
            user = await UserCRUD.get_user_by_telegram_id(session, callback.from_user.id)
            
            if not user:
                await callback.answer("❌ Пользователь не найден", show_alert=True)
                return
            
            if user.payment_completed and user.onboarding_stage == OnboardingStage.PAYMENT_OK:
                success_text = """
🎉 <b>Поздравляю! Robokassa оплата прошла успешно!</b>

Смотреть урок ⤵️
"""
                
                await callback.message.answer(success_text, parse_mode="HTML")
                await callback.answer("🎉 Отлично!")
                
                await send_combined_video(callback.message, callback.from_user.id)
                return
            
            check_text = """
⏳ <b>Проверяем статус Robokassa оплаты...</b>

Обычно обработка Robokassa платежа занимает от нескольких секунд до 5 минут.

🔄 Если платеж прошел успешно, вы автоматически получите уведомление и доступ к курсу.

💡 Вы также можете попробовать оплату через GetCourse или обратиться за помощью.
"""
            
            keyboard = InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        InlineKeyboardButton(
                            text="🔄 Проверить еще раз",
                            callback_data="payment_check"
                        )
                    ],
                    [
                        InlineKeyboardButton(
                            text="🔙 К выбору способа оплаты",
                            callback_data="intro_continue"
                        )
                    ],
                    [
                        InlineKeyboardButton(
                            text="❓ Помощь с оплатой",
                            callback_data="main_support"
                        )
                    ]
                ]
            )
            
            try:
                await callback.message.edit_text(check_text, parse_mode="HTML", reply_markup=keyboard)
            except:
                await callback.answer("🔍 Проверяем...")
            
    except Exception as e:
        logger.error(f"Error in payment_check: {e}")
        await callback.answer("❌ Ошибка проверки", show_alert=True)

@router.callback_query(F.data == "payment_success")
async def payment_success(callback: types.CallbackQuery, onboarding_user):
    logger.info(f"🔥 ROBOKASSA payment_success for user {callback.from_user.id}")

    try:
        async with AsyncSessionLocal() as session:
            user = await UserCRUD.get_user_by_telegram_id(session, callback.from_user.id)
            
            if not user:
                logger.error(f"❌ User {callback.from_user.id} not found")
                await callback.answer("❌ Ошибка: пользователь не найден", show_alert=True)
                return
            
            logger.info(f"✅ User found: {user.ref_code}")
            
            success = await UserCRUD.complete_payment(session, callback.from_user.id)
            
            if not success:
                logger.error(f"❌ Failed to update payment status")
                await callback.answer("❌ Ошибка обновления данных", show_alert=True)
                return
            
            # НОВАЯ ЛОГИКА: Получаем последнего реферала
            last_referrer_code = await UserCRUD.get_last_referrer(session, callback.from_user.id)
            
            invited_by_telegram_id = None
            if last_referrer_code:
                logger.info(f"🔗 Last referrer code: {last_referrer_code}")
                
                # Находим пользователя по реферальному коду
                referrer = await UserCRUD.get_user_by_ref_code(session, last_referrer_code)
                if referrer:
                    invited_by_telegram_id = referrer.telegram_id
                    logger.info(f"🔗 Referrer found: {referrer.telegram_id}")
                    
                    try:
                        # Создаем продажу
                        sale = await SaleCRUD.create_sale(
                            session=session,
                            ref_code=last_referrer_code,
                            amount=float(settings.ONBOARDING_COURSE_PRICE),
                            commission_percent=float(settings.COMMISSION_PERCENT),
                            customer_email=callback.from_user.username or f"user_{callback.from_user.id}",
                            product="Onboarding Course (Robokassa)"
                        )
                        
                        logger.info(f"🎉 Robokassa sale created: ID={sale.id}, commission={sale.commission_amount}")
                        
                        # ВАЖНО: Логируем в историю реферальных действий
                        from app.database.crud import ReferralHistoryCRUD
                        await ReferralHistoryCRUD.log_action(
                            session=session,
                            user_telegram_id=callback.from_user.id,
                            ref_code=last_referrer_code,
                            action_type="payment",
                            amount=sale.amount,
                            commission_amount=sale.commission_amount
                        )
                        
                        # Отправляем уведомление реферу
                        await send_sale_notification(
                            bot=callback.message.bot,
                            referrer_telegram_id=referrer.telegram_id,
                            sale_amount=sale.amount,
                            commission_amount=sale.commission_amount,
                            payment_method="Robokassa"
                        )
                        
                    except Exception as e:
                        logger.error(f"❌ Error creating Robokassa sale: {e}")
                else:
                    logger.warning(f"⚠️ Referrer with code {last_referrer_code} not found")
            else:
                logger.info(f"ℹ️ User {callback.from_user.id} has no referrer")
            
            asyncio.create_task(record_payment_to_sheets(
                telegram_id=callback.from_user.id,
                username=callback.from_user.username,
                user_ref_code=user.ref_code,
                invited_by_telegram_id=invited_by_telegram_id,
                payment_method="Robokassa"
            ))

        success_text = """
🎉 <b>Поздравляю! Robokassa оплата прошла успешно!</b>

Смотреть урок ⤵️
"""
        
        await callback.message.answer(success_text, parse_mode="HTML")
        await callback.answer("🎉 Отлично!")
        
        await send_combined_video(callback.message, callback.from_user.id)
        
    except Exception as e:
        logger.error(f"💥 Error in Robokassa payment_success: {e}", exc_info=True)
        await callback.answer("❌ Произошла ошибка", show_alert=True)

@router.callback_query(F.data == "payment_cancel")
async def payment_cancel(callback: types.CallbackQuery):
    logger.info(f"Robokassa payment cancelled for user {callback.from_user.id}")
    
    cancel_text = """
😔 <b>Robokassa оплата отменена</b>

Ничего страшного! Вы можете:
- Попробовать Robokassa еще раз
- Использовать оплату через GetCourse
- Обратиться в поддержку

💡 Помните: инвестиция в знания всегда окупается!
"""
    
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🔙 К выбору способа оплаты",
                    callback_data="intro_continue"
                )
            ]
        ]
    )
    
    await callback.message.answer(
        cancel_text,
        parse_mode="HTML",
        reply_markup=keyboard
    )
    
    await callback.answer("💡 Попробуйте другой способ!")





@router.callback_query(F.data == "send_video_guide")
async def send_video_guide(callback: types.CallbackQuery):
    logger.info(f"User {callback.from_user.id} clicked 'ХОЧУ В КОМАНДУ!' from PDF")
    
    try:
        async with AsyncSessionLocal() as session:
            await StageUpdateHelper.update_user_stage(session, callback.from_user.id, OnboardingStage.PARTNER_LESSON, callback.bot)
        
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="Я заполнил анкету и прочитал договор 🚀",
                        callback_data="show_referral_link"
                    )
                ]
            ]
        )
        
        welcome_text = """
<b>Приветствую тебя в своей команде</b> 🤝

Для того чтобы стать частью моей команды, тебе необходимо выполнить 2️⃣ шага:

1️⃣ Принять договор со мной 🤝

2️⃣ Заполнить анкету✅

В анкете тебе нужно прикрепить ссылки на свои страницы в Instagram, YouTube и TikTok, через которые ты будешь работать со мной по партнерке 🚀

📋 <a href="https://drive.google.com/file/d/1n0YKHd0CA7M6V7iMKPeb05pymeXeO1hN/view?usp=sharing">Договор о партнерстве с Мамедом</a>

📝 <a href="https://forms.yandex.ru/u/68f002c702848f24b38c1ee9">Заполнить анкету</a>

⬆️ Кликни прямо на договор и анкету, чтобы открыть

Как только выполнишь эти два шага, нажми на кнопку внизу "Я заполнил анкету и прочитал договор 🚀"
"""
        
        # Отправляем обычное текстовое сообщение с кнопкой
        await callback.message.answer(
            welcome_text,
            parse_mode="HTML",
            reply_markup=keyboard,
            disable_web_page_preview=True  # Отключаем превью ссылок для чистоты
        )
        
        await callback.answer("🚀 Добро пожаловать!")
        logger.info(f"✅ Сообщение с договором и анкетой отправлено пользователю {callback.from_user.id}")
            
    except Exception as e:
        logger.error(f"Error sending video guide: {e}")
        await callback.answer("❌ Ошибка", show_alert=True)

@router.callback_query(F.data == "show_referral_link")
async def show_referral_link(callback: types.CallbackQuery):
    logger.info(f"User {callback.from_user.id} requesting referral link")
    
    try:
        async with AsyncSessionLocal() as session:
            await StageUpdateHelper.update_user_stage(session, callback.from_user.id, OnboardingStage.GOT_LINK, callback.bot)
            user = await UserCRUD.get_user_by_telegram_id(session, callback.from_user.id)
        
        if not user:
            await callback.answer("❌ Ошибка получения данных", show_alert=True)
            return
        
        referral_link = f"https://t.me/{settings.BOT_USERNAME}?start={user.ref_code}"
        
        link_message = f"""
✅ <b>Поздравляем! Теперь ты наш партнёр!</b>

🔗 <b>Вот твоя реферальная ссылка:</b>

<code>{referral_link}</code>

<i>*⬆️ нажми прямо на неё, чтобы скопировать ⬆️*</i>

🧑‍💻 А это, кстати, чат партнеров, где наш менеджер каждый день проверяет публикации моих партнеров и корректирует их шаги. Жду тебя там ⤵️

<b>ПОСЛЕ ТОГО, КАК ВЫБЕРЕШЬ СВОЙ ЧАТ И ПЕРЕЙДЕШЬ В НЕГО, ОБЯЗАТЕЛЬНО-ВЕРНИСЬ СЮДА И НАЖМИ НА ГАЛОЧКУ: ✅ Я скопировал ссылку, и перешел в чат</b>

"""
        
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="🧕 ЧАТ ДЛЯ ЖЕНЩИН",
                        url="https://t.me/+4RMI9SL55tplZDc6"
                    )
                ],
                [
                    InlineKeyboardButton(
                        text="🧔🏻 ЧАТ ДЛЯ МУЖЧИН",
                        url="https://t.me/+POs7aysnUmhmM2Uy"
                    )
                ],
                [
                    InlineKeyboardButton(
                        text="✅ Я скопировал ссылку, и перешел в чат",
                        callback_data="completed_steps"
                    )
                ],
                [
                    InlineKeyboardButton(
                        text="❓ Задать вопрос, у меня не получается",
                        callback_data="ask_question_help"
                    )
                ]
            ]
        )
        
        await callback.message.answer(
            link_message,
            parse_mode="HTML",
            reply_markup=keyboard
        )
        
        await callback.answer("🔗 Твоя ссылка готова!")
        
    except Exception as e:
        logger.error(f"Error in show_referral_link: {e}")
        await callback.answer("❌ Ошибка", show_alert=True)

@router.callback_query(F.data == "completed_steps")
async def completed_steps(callback: types.CallbackQuery):
    """Завершение онбординга с переходом в главное меню"""
    logger.info(f"User {callback.from_user.id} completed both steps")
    
    try:
        user_id = callback.from_user.id
        
        # Завершаем онбординг
        async with AsyncSessionLocal() as session:
            await UserCRUD.complete_onboarding(session, user_id)
            user = await UserCRUD.get_user_by_telegram_id(session, user_id)
        
        # Уведомление админу
        user_info = f"@{callback.from_user.username}" if callback.from_user.username else "Без username"
        current_time = datetime.now().strftime("%d.%m.%Y %H:%M")
        
        admin_message = f"""
🚨 <b>НОВЫЙ ПОЛЬЗОВАТЕЛЬ</b>
👤 <b>Имя:</b> {callback.from_user.full_name}
🆔 <b>ID:</b> <code>{callback.from_user.id}</code>
🅰 <b>Username:</b> {user_info}
🔗 <b>Реф. код:</b> {user.ref_code if user else "Не найден"}
⏰ <b>Время:</b> {current_time}
"""
        
        await callback.message.bot.send_message(
            chat_id=settings.ADMIN_ID,
            text=admin_message,
            parse_mode="HTML"
        )
        
        # Создаем главное меню как новое сообщение
        from app.handlers.main_menu import get_main_menu_keyboard
        
        menu_text = f"""
🎛️ <b>Главное меню</b>

Поздравляю с выполнением всех шагов! ✅

Смотри, внизу у тебя доступно раздел "Меню", где ты всегда можешь получить свою реферальную ссылку 🔗 , а также узнать свой балас и вывести свои деньги. 

❓Но если у тебя есть вопросы, напиши нам в поддержку и мы тебе поможем во всем разобраться 🙌
"""
        
        keyboard = await get_main_menu_keyboard(callback.from_user.id)
        await callback.message.answer(
            menu_text,
            parse_mode="HTML",
            reply_markup=keyboard
        )
        
        await callback.answer("🎉 Добро пожаловать в команду!")
        
        logger.info(f"✅ User {user_id} completed onboarding and redirected to main menu")
        
    except Exception as e:
        logger.error(f"❌ Error in completed_steps: {e}", exc_info=True)
        await callback.answer("❌ Ошибка завершения онбординга", show_alert=True)



@router.callback_query(F.data == "show_instruction_pdf")
async def show_instruction_pdf(callback: types.CallbackQuery):
    logger.info(f"User {callback.from_user.id} requested instruction PDF")
    
    try:
        import os
        from aiogram.types import FSInputFile
        
        pdf_path = "/root/telegram-referral-bot/app/Инструкция.pdf"
        
        if not os.path.exists(pdf_path):
            logger.error(f"❌ PDF file not found: {pdf_path}")
            await callback.answer("❌ Файл инструкции не найден", show_alert=True)
            return
        
        pdf_file = FSInputFile(
            path=pdf_path,
            filename="Инструкция.pdf"
        )
        
        await callback.message.answer_document(
            document=pdf_file,
            caption="📋 <b>Инструкция по публикации видео в социальных сетях</b>\n\nИзучи внимательно эти правила перед началом работы!",
            parse_mode="HTML"
        )
        
        await callback.answer("📋 Инструкция отправлена!")
        logger.info(f"✅ PDF instruction sent to user {callback.from_user.id}")
        
    except Exception as e:
        logger.error(f"❌ Error sending PDF instruction: {e}")
        await callback.answer("❌ Ошибка отправки файла", show_alert=True)