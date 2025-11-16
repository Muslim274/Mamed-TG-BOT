"""
FSM состояния для системы рассылки с поддержкой кнопок
app/handlers/broadcast/broadcast_states.py
"""
from aiogram.fsm.state import State, StatesGroup


class BroadcastStates(StatesGroup):
    """Состояния для системы рассылки"""
    
    # Выбор аудитории (всем или определенным)
    choosing_audience = State()
    
    # Ввод списка Telegram ID
    entering_user_ids = State()
    
    # Валидация введенных ID
    validating_ids = State()
    
    # Ввод сообщения для рассылки
    entering_message = State()
    
    # 🆕 НОВЫЕ СОСТОЯНИЯ ДЛЯ КНОПОК
    # Выбор - добавлять кнопки или нет
    choosing_buttons = State()
    
    # Ввод кнопок
    entering_buttons = State()
    
    # Подтверждение перед отправкой
    confirming = State()
    
    # Процесс рассылки
    broadcasting = State()