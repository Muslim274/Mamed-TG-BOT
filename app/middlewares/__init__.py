"""
Регистрация middleware
"""
from aiogram import Dispatcher

from app.middlewares.throttling import ThrottlingMiddleware
from app.middlewares.logging import LoggingMiddleware


def register_all_middlewares(dp: Dispatcher):
    """Регистрация всех middleware"""
    dp.message.middleware(ThrottlingMiddleware())
    dp.message.middleware(LoggingMiddleware())
