"""
Регистрация всех хендлеров
"""
from aiogram import Dispatcher

from app.handlers.start import register_start_handlers
from app.handlers.referral import register_referral_handlers
from app.handlers.stats import register_stats_handlers
from app.handlers.instructions import register_instructions_handlers
from app.handlers.faq import register_faq_handlers
from app.handlers.support import register_support_handlers
from app.handlers.main_menu import register_main_menu_handlers
from app.handlers.clear_keyboard import register_clear_handlers


def register_all_handlers(dp: Dispatcher):
    """Регистрация всех хендлеров бота"""
    register_start_handlers(dp)
    register_referral_handlers(dp)
    register_stats_handlers(dp)
    register_instructions_handlers(dp)
    register_faq_handlers(dp)
    register_support_handlers(dp)
    register_main_menu_handlers(dp)
    register_clear_handlers(dp)
