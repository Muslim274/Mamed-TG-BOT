"""
ОТЛАДОЧНАЯ версия universal_start.py с подробным логированием и новой логикой реферала
"""
import logging
from aiogram import Router, types
from aiogram.filters import CommandStart
from aiogram.types import ReplyKeyboardRemove

from app.database.connection import AsyncSessionLocal
from app.database.crud import UserCRUD
from app.database.models import OnboardingStage
from app.utils.helpers import generate_ref_code
from app.utils.constants import ONBOARDING_TEXTS
from app.helpers.stage_helper import StageUpdateHelper
from app.config import settings


logger = logging.getLogger(__name__)
router = Router()

@router.message(CommandStart())
async def universal_start_handler(message: types.Message):
    """🔍 ОТЛАДОЧНЫЙ универсальный обработчик /start"""
    telegram_id = message.from_user.id
    username = message.from_user.username or "no_username"
    full_name = message.from_user.full_name
    first_name = message.from_user.first_name or "друг"
    
    logger.info(f"🔥 UNIVERSAL START HANDLER TRIGGERED!")
    logger.info(f"   user_id: {telegram_id}")
    logger.info(f"   username: @{username}")
    logger.info(f"   full_name: {full_name}")
    logger.info(f"   command: {message.text}")
    
    try:
        logger.info(f"📊 Opening database session...")
        async with AsyncSessionLocal() as session:
            logger.info(f"🔍 Searching for user {telegram_id} in database...")
            user = await UserCRUD.get_user_by_telegram_id(session, telegram_id)
            
            # Обрабатываем реферальную ссылку (НОВАЯ ЛОГИКА)
            args = message.text.split()
            referred_by = None
            
            if len(args) > 1 and args[1].startswith("ref_"):
                referred_by = args[1]
                logger.info(f"🔗 User {telegram_id} referred by {referred_by}")
                
                # Записываем клик по реферальной ссылке с новой логикой
                try:
                    from app.database.crud import ClickCRUD, ReferralHistoryCRUD
                    
                    # ВАЖНО: Записываем клик с user_telegram_id (если пользователь существует)
                    await ClickCRUD.create_click(
                        session=session,
                        ref_code=referred_by,
                        ip_address="telegram",
                        user_agent="telegram_bot",
                        source="telegram",
                        user_telegram_id=telegram_id if user else None  # Передаем telegram_id
                    )
                    logger.info(f"✅ Click recorded for ref_code {referred_by} with user_id {telegram_id}")
                    
                    # Логируем для аналитики (если пользователь уже существует)
                    if user:
                        await ReferralHistoryCRUD.log_action(
                            session=session,
                            user_telegram_id=telegram_id,
                            ref_code=referred_by,
                            action_type="click",
                            ip_address="telegram",
                            user_agent="telegram_bot"
                        )
                        logger.info(f"✅ Referral history logged for existing user {telegram_id}")
                        
                except Exception as e:
                    logger.error(f"❌ Error recording click: {e}")
            
            if not user:
                logger.info(f"👤 User {telegram_id} NOT FOUND - creating new user...")
                
                # Создаем нового пользователя
                ref_code = generate_ref_code(telegram_id)
                logger.info(f"🆔 Generated ref_code: {ref_code}")
                
                logger.info(f"💾 Creating user in database...")
                user = await UserCRUD.create_user(
                    session=session,
                    telegram_id=telegram_id,
                    username=username,
                    full_name=full_name,
                    ref_code=ref_code,
                    referred_by=referred_by,  # Это для fallback логики
                    onboarding_stage=OnboardingStage.NEW_USER
                )
                
                logger.info(f"✅ User created successfully!")
                logger.info(f"   user.id: {user.id}")
                logger.info(f"   user.telegram_id: {user.telegram_id}")
                logger.info(f"   user.ref_code: {user.ref_code}")
                logger.info(f"   user.referred_by: {user.referred_by}")
                logger.info(f"   user.onboarding_stage: {user.onboarding_stage}")
                
                
                # ВАЖНО: Планируем автоматические сообщения для нового пользователя
                await StageUpdateHelper.update_user_stage(
                    session, telegram_id, OnboardingStage.NEW_USER, message.bot
                )
                logger.info(f"✅ Automated messages scheduled for NEW_USER")
                
                # Если новый пользователь пришел по реферальной ссылке - логируем
                if referred_by:
                    try:
                        from app.database.crud import ReferralHistoryCRUD
                        await ReferralHistoryCRUD.log_action(
                            session=session,
                            user_telegram_id=telegram_id,
                            ref_code=referred_by,
                            action_type="click",
                            ip_address="telegram",
                            user_agent="telegram_bot"
                        )
                        logger.info(f"✅ Referral history logged for new user {telegram_id}")
                    except Exception as e:
                        logger.error(f"❌ Error logging referral history: {e}")
                
            else:
                logger.info(f"👤 Found existing user {telegram_id}")
                logger.info(f"   user.id: {user.id}")
                logger.info(f"   user.onboarding_stage: {user.onboarding_stage}")
                logger.info(f"   user.ref_code: {user.ref_code}")
            
            # Проверяем стадию онбординга
            stage = user.onboarding_stage
            logger.info(f"🎯 User {telegram_id} is at stage: {stage}")
            
            # ГЛАВНАЯ ЛОГИКА: проверяем онбординг
            if settings.ONBOARDING_ENABLED and stage != OnboardingStage.COMPLETED:
                # Начинаем или продолжаем онбординг
                logger.info(f"🚀 Starting/continuing onboarding for user {telegram_id}")
                await start_onboarding(message, user, first_name)
            else:
                # Пользователь завершил онбординг - показываем главное меню
                logger.info(f"🎛️ Showing main menu for completed user {telegram_id}")
                await show_main_menu(message, user)
    
    except Exception as e:
        logger.error(f"💥 CRITICAL ERROR in universal_start_handler: {e}", exc_info=True)
        await message.answer(
            "❌ Произошла техническая ошибка. Попробуйте еще раз через несколько секунд.",
            reply_markup=ReplyKeyboardRemove()
        )

async def start_onboarding(message: types.Message, user, first_name):
    """Запуск онбординга с правильной обработкой стадий"""
    logger.info(f"🎯 start_onboarding called for user {message.from_user.id}")
    logger.info(f"   current_stage: {user.onboarding_stage}")
    
    try:
        # Определяем что показать в зависимости от стадии
        if user.onboarding_stage == OnboardingStage.NEW_USER:
            logger.info(f"📹 Showing intro video for NEW_USER...")
            # Показываем приветствие и вводное видео
            await show_intro_video(message, first_name)
            
            # ИСПРАВЛЕНИЕ: НЕ обновляем стадию сразу!
            # Стадия будет обновлена только при нажатии кнопки "📚 Получить урок"
            # async with AsyncSessionLocal() as session:
            #     success = await UserCRUD.update_onboarding_stage(session, message.from_user.id, OnboardingStage.INTRO_SHOWN)
            #     logger.info(f"📊 Stage updated to INTRO_SHOWN: {success}")
        
        elif user.onboarding_stage == OnboardingStage.INTRO_SHOWN:
            logger.info(f"📹 Re-showing intro video for INTRO_SHOWN (video was shown but button not clicked)...")
            # ИСПРАВЛЕНИЕ: Если пользователь на стадии INTRO_SHOWN, значит он видел видео, 
            # но еще не нажал кнопку - показываем только видео, БЕЗ предложения оплаты
            await show_intro_video(message, first_name)
            
        elif user.onboarding_stage == OnboardingStage.WAIT_PAYMENT:
            logger.info(f"🎥💳 Showing BOTH intro video AND payment offer for WAIT_PAYMENT...")
            # Показываем ОБА сообщения для пользователей на этапе оплаты
            # 1. Сначала показываем вводное видео (чтобы пользователь не потерял контекст)
            await show_intro_video(message, first_name)
            
            # 2. Затем показываем предложение оплаты
            await show_payment_offer(message)
        
        elif user.onboarding_stage in [OnboardingStage.PAYMENT_OK, OnboardingStage.WANT_JOIN]:
            logger.info(f"🎉 Showing after-payment content...")
            # Показываем следующий этап после оплаты
            await show_after_payment(message)
        
        else:
            logger.info(f"🔄 Showing intermediate message for stage: {user.onboarding_stage}")
            # Для других стадий показываем промежуточное сообщение
            await message.answer(
                f"🔄 Продолжаем с этапа: {user.onboarding_stage}\n\nИспользуйте кнопки в чате для продолжения.",
                reply_markup=ReplyKeyboardRemove()
            )
        
        logger.info(f"✅ Onboarding step completed for user {message.from_user.id}")
        
    except Exception as e:
        logger.error(f"❌ Error in start_onboarding: {e}", exc_info=True)
        await message.answer("❌ Ошибка запуска обучения. Обратитесь в поддержку.")


async def show_intro_video(message: types.Message, first_name):
    """Показ вводного видео"""
    logger.info(f"📹 show_intro_video called for {message.from_user.id}")
    
    # Приветственное сообщение
    welcome_text = ONBOARDING_TEXTS["welcome"].format(first_name=first_name)
    await message.answer(welcome_text, parse_mode="HTML", reply_markup=ReplyKeyboardRemove())
    logger.info(f"✅ Welcome message sent")
    
    # Отправляем вводное видео
    video_file_id = settings.VIDEO2_ID
    logger.info(f"🎥 Video file_id: {video_file_id[:20]}...")
    
    if video_file_id and video_file_id != "BAACAgIAAxkBAAI...":
        from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
        
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="📚 Получить урок",
                        callback_data="intro_continue"
                    )
                ]
            ]
        )
        
        try:
            await message.answer_video(
                video=video_file_id,
                parse_mode="HTML",
                reply_markup=keyboard,
                supports_streaming=True
            )
            logger.info(f"✅ Intro video sent successfully")
            
            # ИСПРАВЛЕНИЕ: Обновляем стадию НА INTRO_SHOWN только после успешной отправки видео
            async with AsyncSessionLocal() as session:
                success = await StageUpdateHelper.update_user_stage(session, message.from_user.id, OnboardingStage.INTRO_SHOWN, message.bot)
                logger.info(f"📊 Stage updated to INTRO_SHOWN after video sent: {success}")
                
        except Exception as e:
            logger.error(f"❌ Error sending video: {e}")
            # Fallback - отправляем текстовое сообщение
            await message.answer(
                "📹 <b>Вводное видео</b>\n\n<i>Ошибка загрузки видео. Попробуйте еще раз через несколько секунд.</i>",
                parse_mode="HTML",
                reply_markup=keyboard
            )
    else:
        logger.warning(f"⚠️ Video file_id not configured properly: {video_file_id}")
        # Если видео не настроено
        from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
        
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="📚 Получить урок",
                        callback_data="intro_continue"
                    )
                ]
            ]
        )
        
        await message.answer(
            "📹 <b>Вводное видео</b>\n\n<i>Администратор: настройте ONBOARDING_INTRO_VIDEO_ID в .env</i>",
            parse_mode="HTML",
            reply_markup=keyboard
        )
        
        # ИСПРАВЛЕНИЕ: Обновляем стадию даже если видео не настроено
        async with AsyncSessionLocal() as session:
            success = await StageUpdateHelper.update_user_stage(session, message.from_user.id, OnboardingStage.INTRO_SHOWN, message.bot)
            logger.info(f"📊 Stage updated to INTRO_SHOWN (fallback): {success}")

async def show_payment_offer(message: types.Message):
    """Показ предложения оплаты"""
    logger.info(f"💳 show_payment_offer called for {message.from_user.id}")
    
    from app.handlers.onboarding.payment import get_integrated_payment_keyboard
    
    # Форматируем цену
    price = settings.ONBOARDING_COURSE_PRICE
    formatted_amount = f"{price:,.0f}".replace(",", "\u202F") + f" {settings.ONBOARDING_COURSE_CURRENCY}"
    
    payment_text = ONBOARDING_TEXTS["payment_offer"].format(
        formatted_amount=formatted_amount
    )
    
    # Создаем платеж через Robokassa (если не mock режим)
    payment_url = None
    if not settings.ONBOARDING_MOCK_PAYMENT:
        try:
            from app.services.robokassa_handler import robokassa_handler
            payment_url, invoice_id = await robokassa_handler.create_payment(
                user_id=message.from_user.id,
                amount=settings.ONBOARDING_COURSE_PRICE,
                description="Онбординг курс партнерской программы"
            )
            logger.info(f"✅ Payment created: {invoice_id}")
        except Exception as e:
            logger.error(f"❌ Error creating Robokassa payment: {e}")
    
    await message.answer(
        payment_text,
        parse_mode="HTML",
        reply_markup=get_integrated_payment_keyboard(payment_url)
    )
    logger.info(f"✅ Payment offer sent")

async def show_after_payment(message: types.Message):
    """Показ контента после оплаты"""
    logger.info(f"🎉 show_after_payment called for {message.from_user.id}")
    
    await message.answer(
        "🎉 <b>Поздравляю с успешной оплатой!</b>\n\nИспользуйте кнопки в предыдущих сообщениях для продолжения обучения.",
        parse_mode="HTML",
        reply_markup=ReplyKeyboardRemove()
    )

async def show_main_menu(message: types.Message, user):
    """Показ главного меню для завершивших онбординг"""
    logger.info(f"🎛️ show_main_menu called for completed user {message.from_user.id}")
    
    from app.handlers.main_menu import get_main_menu_keyboard
            
    # Формируем реферальную ссылку
    referral_link = f"https://t.me/{settings.BOT_USERNAME}?start={user.ref_code}"
    
    welcome_text = f"""
👋 Добро пожаловать, {message.from_user.full_name}!

🔗 <b>Вот твоя реферальная ссылка:</b>

<code>{referral_link}</code>

<i>*⬆️ нажми прямо на неё, чтобы скопировать ⬆️*</i>

Выберите нужный раздел:
"""
    
    keyboard = await get_main_menu_keyboard(message.from_user.id)
    await message.answer(
        welcome_text,
        parse_mode="HTML",
        reply_markup=keyboard
    )
    logger.info(f"✅ Main menu sent")