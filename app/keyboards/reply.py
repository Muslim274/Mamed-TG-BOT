"""
Reply клавиатуры ОТКЛЮЧЕНЫ - используем только inline
"""
from aiogram.types import ReplyKeyboardRemove

def get_main_menu():
    """Возвращаем None - reply клавиатуры отключены"""
    return None

def remove_keyboard():
    """Удаление клавиатуры"""
    return ReplyKeyboardRemove()

# Все остальные функции reply клавиатур удалены
# Используйте только inline клавиатуры из app.keyboards.onboarding
