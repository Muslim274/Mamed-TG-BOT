"""
ИСПРАВЛЕННЫЙ модуль упрощенного онбординга с исключением всех админов
"""
import logging
from aiogram import Router
from aiogram.filters import BaseFilter
from aiogram.types import Message, CallbackQuery

from app.config import settings, is_admin

# Импорты хэндлеров упрощенного онбординга
from .universal_start import router as universal_start_router
from .intro import router as intro_router
from .payment import router as payment_router

logger = logging.getLogger(__name__)


class NotAdminFilter(BaseFilter):
    async def __call__(self, event: Message | CallbackQuery) -> bool:
        user_id = event.from_user.id
        user_is_admin = is_admin(user_id)

        # Разрешаем админские действия по callback_data
        if user_is_admin and hasattr(event, "data") and event.data:
            # ✅ ИСПРАВЛЕНИЕ: Разрешаем админам тестировать онбординг
            allowed_callbacks = [
                "admin_approve_getcourse:",
                "admin_reject_getcourse:",
                "broadcast_",
                "intro_continue",  # Разрешаем кнопку "Получить урок"
                "toggle_doc:",  # Разрешаем чекбоксы документов
                "documents_confirmed",  # Разрешаем подтверждение документов
                "what_i_get",  # Разрешаем "Что я приобретаю"
                "show_crypto_payment",  # Разрешаем криптооплату
                "show_foreign_cards_payment",  # Разрешаем иностранные карты
                "back_to_payment_methods",  # Разрешаем возврат к способам оплаты
                "payment_",  # Разрешаем все кнопки оплаты
                "getcourse_",  # Разрешаем GetCourse
                "send_video_guide",  # Разрешаем видео-гид
                "show_referral_link",  # Разрешаем реферальную ссылку
                "completed_steps",  # Разрешаем завершение шагов
                "joined_community:",  # Разрешаем вступление в сообщество
                "next_lesson:",  # Разрешаем переход к следующему уроку
                "complete_lessons",  # Разрешаем завершение уроков
                "ask_question_help"  # Разрешаем обращение в поддержку
            ]

            for allowed in allowed_callbacks:
                if event.data.startswith(allowed) or event.data == allowed:
                    return True  # НЕ блокируем

        if user_is_admin:
            logger.debug(f"🔑 NotAdminFilter: Blocking admin {user_id} from onboarding")
            return False
        return True


def create_onboarding_router() -> Router:
    """Создание упрощенного роутера онбординга с исключением всех админов"""
    main_router = Router(name="simplified_onboarding")
    
    logger.info("🎯 Creating onboarding router...")
    
    # КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ: Добавляем фильтр для исключения всех админов
    not_admin_filter = NotAdminFilter()
    
    # Применяем фильтр ко всем handlers в каждом роутере
    # universal_start_router.message.filter(not_admin_filter)
    # universal_start_router.callback_query.filter(not_admin_filter)
    
    intro_router.message.filter(not_admin_filter)
    intro_router.callback_query.filter(not_admin_filter)
    
    payment_router.message.filter(not_admin_filter)
    payment_router.callback_query.filter(not_admin_filter)
    
    # Регистрируем роутеры в правильном порядке
    
    # 1. Universal Start - универсальный /start для всех (ПЕРВЫМ!)
    main_router.include_router(universal_start_router)
    logger.info("✅ Universal Start router registered (HIGH PRIORITY)")
    
    # 2. Intro - вводное видео
    main_router.include_router(intro_router)
    logger.info("✅ Intro router registered")
    
    # 3. Payment - упрощенная оплата и весь дальнейший флоу
    main_router.include_router(payment_router)
    logger.info("✅ Payment router registered")
    
    # ОТЛАДКА: Подсчитываем handlers
    total_message_handlers = len(main_router.message.handlers)
    total_callback_handlers = len(main_router.callback_query.handlers)
    
    admin_ids = settings.admin_ids_list
    logger.info(f"🎯 Simplified onboarding router created:")
    logger.info(f"   Message handlers: {total_message_handlers}")
    logger.info(f"   Callback handlers: {total_callback_handlers}")
    logger.info(f"   🔑 Admins {admin_ids} excluded from onboarding")
    
    return main_router


def setup_onboarding_logging(router: Router):
    """Настройка логирования для упрощенного онбординга"""
    async def log_onboarding_update(handler, event, data):
        user_id = event.from_user.id
        stage = data.get('onboarding_stage', 'unknown')

        # ✅ ИСПРАВЛЕНИЕ: Разрешаем админам /start команды и специальные callback'и
        if is_admin(user_id):
            # Разрешаем /start команды для админов
            if hasattr(event, 'text') and event.text and event.text.startswith('/start'):
                logger.info(f"🔑 Admin {user_id} used /start - allowing")
            # Разрешаем админские callback'и
            elif hasattr(event, 'data') and event.data:
                allowed_callbacks = (
                    "admin_approve_getcourse:",
                    "admin_reject_getcourse:",
                    "broadcast_"
                )
                if event.data.startswith(allowed_callbacks):
                    logger.info(f"🔑 Admin {user_id} used admin callback: {event.data}")
                else:
                    logger.warning(f"⚠️ Admin {user_id} reached onboarding with unexpected data: {event.data}")
            else:
                logger.warning(f"⚠️ Admin {user_id} reached onboarding unexpectedly")

        # Логируем обычных пользователей
        if hasattr(event, 'text') and event.text:
            logger.info(f"🎯 Onboarding: User {user_id} at stage {stage} sent: {event.text[:50]}...")
        elif hasattr(event, 'data') and event.data:
            logger.info(f"🎯 Onboarding: User {user_id} at stage {stage} clicked: {event.data}")

        # ✅ ВАЖНО: Всегда вызываем handler
        return await handler(event, data)

    router.message.middleware(log_onboarding_update)
    router.callback_query.middleware(log_onboarding_update)


def get_onboarding_handlers_count() -> dict:
    """Получение количества хэндлеров (для отладки)"""
    return {
        "universal_start": 1,
        "intro": 1,
        "payment": 8,
        "total": 10
    }


# Экспорт основных функций
__all__ = [
    'create_onboarding_router',
    'setup_onboarding_logging', 
    'get_onboarding_handlers_count'
]