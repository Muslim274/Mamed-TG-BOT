"""
FSM состояния для расширенной версии команды /get_info
"""
from aiogram.fsm.state import State, StatesGroup


class ReportStates(StatesGroup):
    """Состояния для генерации отчётов"""
    choosing_period = State()  # Выбор периода
    entering_start_date = State()  # Ввод начальной даты
    entering_end_date = State()  # Ввод конечной даты
