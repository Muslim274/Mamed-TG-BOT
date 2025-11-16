"""
Inline клавиатуры
"""
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


def get_referral_menu(ref_code: str) -> InlineKeyboardMarkup:
    """Меню для реферальной ссылки"""
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="📋 Скопировать ссылку",
                    callback_data=f"copy_link:{ref_code}"
                )
            ],
            [
                InlineKeyboardButton(
                    text="📈 Статистика по ссылке",
                    callback_data=f"link_stats:{ref_code}"
                )
            ],
            [
                InlineKeyboardButton(
                    text="🔙 В главное меню",
                    callback_data="back_to_menu"
                )
            ]
        ]
    )
    return keyboard


def get_materials_menu() -> InlineKeyboardMarkup:
    """Меню материалов"""
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="📝 Тексты для постов",
                    callback_data="materials:texts"
                )
            ],
            [
                InlineKeyboardButton(
                    text="🖼 Баннеры и креативы",
                    callback_data="materials:banners"
                )
            ],
            [
                InlineKeyboardButton(
                    text="🎥 Видео-инструкции",
                    callback_data="materials:videos"
                )
            ],
            [
                InlineKeyboardButton(
                    text="💡 Кейсы и примеры",
                    callback_data="materials:cases"
                )
            ],
            [
                InlineKeyboardButton(
                    text="🔙 Назад",
                    callback_data="back_to_menu"
                )
            ]
        ]
    )
    return keyboard


def get_faq_menu() -> InlineKeyboardMarkup:
    """FAQ меню"""
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="💵 О выплатах",
                    callback_data="faq:payments"
                )
            ],
            [
                InlineKeyboardButton(
                    text="🔗 О реферальных ссылках", 
                    callback_data="faq:links"
                )
            ],
            [
                InlineKeyboardButton(
                    text="📊 О статистике",
                    callback_data="faq:stats"
                )
            ],
            [
                InlineKeyboardButton(
                    text="🛠 Технические вопросы",
                    callback_data="faq:tech"
                )
            ],
            [
                InlineKeyboardButton(
                    text="➕ Задать свой вопрос",
                    callback_data="faq:ask"
                )
            ],
            [
                InlineKeyboardButton(
                    text="🔙 В главное меню",
                    callback_data="back_to_menu"
                )
            ]
        ]
    )
    return keyboard
