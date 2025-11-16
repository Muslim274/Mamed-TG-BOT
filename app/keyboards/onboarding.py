"""
Клавиатуры для онбординга
"""
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from app.config import settings


def get_intro_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура после просмотра вводного видео"""
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🚀 Продолжить",
                    callback_data="intro_continue"
                )
            ],
            [
                InlineKeyboardButton(
                    text="💬 Связаться с поддержкой",
                    url="https://t.me/support"
                )
            ]
        ]
    )
    return keyboard


def get_payment_keyboard() -> InlineKeyboardMarkup:
    """Mock клавиатура для имитации оплаты"""
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Оплата прошла (ТЕСТ)",
                    callback_data="payment_success"
                )
            ],
            [
                InlineKeyboardButton(
                    text="❌ Не оплатил (ТЕСТ)",
                    callback_data="payment_cancel"
                )
            ],
            [
                InlineKeyboardButton(
                    text="❓ Помощь с оплатой",
                    callback_data="payment_help"
                )
            ]
        ]
    )
    return keyboard


def get_partner_offer_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура предложения партнерства"""
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Да, хочу стать партнером!",
                    callback_data="partner_accept"
                )
            ],
            [
                InlineKeyboardButton(
                    text="🤔 Расскажите подробнее",
                    callback_data="partner_info"
                )
            ],
            [
                InlineKeyboardButton(
                    text="❌ Возможно позже",
                    callback_data="partner_decline"
                )
            ]
        ]
    )
    return keyboard


def get_course_navigation_keyboard(current_lesson: int, total_lessons: int = 10) -> InlineKeyboardMarkup:
    """Клавиатура навигации по курсу"""
    buttons = []
    
    # Первый ряд - основная навигация
    nav_row = []
    
    if current_lesson > 1:
        nav_row.append(
            InlineKeyboardButton(
                text="⬅️ Предыдущий",
                callback_data=f"course_lesson:{current_lesson - 1}"
            )
        )
    
    if current_lesson < total_lessons:
        nav_row.append(
            InlineKeyboardButton(
                text="➡️ Следующий",
                callback_data=f"course_lesson:{current_lesson + 1}"
            )
        )
    
    if nav_row:
        buttons.append(nav_row)
    
    # Второй ряд - дополнительные действия
    action_row = []
    
    # Кнопка повтора текущего урока
    action_row.append(
        InlineKeyboardButton(
            text="🔄 Пересмотреть",
            callback_data=f"course_replay:{current_lesson}"
        )
    )
    
    # Меню курса (список всех уроков)
    action_row.append(
        InlineKeyboardButton(
            text="📋 Меню курса",
            callback_data="course_menu"
        )
    )
    
    buttons.append(action_row)
    
    # Третий ряд - прогресс и завершение
    if current_lesson == total_lessons:
        buttons.append([
            InlineKeyboardButton(
                text="🎓 Завершить курс",
                callback_data="course_complete"
            )
        ])
    else:
        # Показываем прогресс
        progress_text = f"📊 Прогресс: {current_lesson}/{total_lessons}"
        buttons.append([
            InlineKeyboardButton(
                text=progress_text,
                callback_data="course_progress"
            )
        ])
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)
