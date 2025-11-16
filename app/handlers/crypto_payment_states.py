"""
FSM состояния для обработки криптоплатежей
"""
from aiogram.fsm.state import State, StatesGroup


class CryptoPaymentStates(StatesGroup):
    """Состояния для процесса оплаты криптовалютой"""
    selecting_crypto = State()  # Выбор криптовалюты
    waiting_hash = State()      # Ожидание ввода хеша транзакции
