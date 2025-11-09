"""
Хэндлер для пользователей, завершивших онбординг - только inline
"""
import logging
from aiogram import Router, types, F
from aiogram.types import ReplyKeyboardRemove, InlineKeyboardMarkup, InlineKeyboardButton
from app.database.models import OnboardingStage
from app.middlewares.onboarding_check import OnboardingStageMiddleware

logger = logging.getLogger(__name__)

# Создаем роутер для завершивших онбординг
router = Router()
router.message.middleware(OnboardingStageMiddleware(allowed_stages=[OnboardingStage.COMPLETED]))
router.callback_query.middleware(OnboardingStageMiddleware(allowed_stages=[OnboardingStage.COMPLETED]))

# Все хендлеры перенесены в main_menu.py и support/
# Этот файл оставляем для совместимости
