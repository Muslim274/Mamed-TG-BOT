"""
Вспомогательные функции
"""
import hashlib
import random
import string


def generate_ref_code(user_id: int) -> str:
    """Генерация уникального реферального кода"""
    # Создаем хеш от user_id
    hash_object = hashlib.md5(str(user_id).encode())
    hash_hex = hash_object.hexdigest()
    
    # Берем первые 6 символов и добавляем префикс
    return f"ref_{hash_hex[:6].upper()}"


def generate_random_string(length: int = 8) -> str:
    """Генерация случайной строки"""
    characters = string.ascii_letters + string.digits
    return ''.join(random.choice(characters) for _ in range(length))


def format_money(amount: float, currency: str) -> str:
    """Форматирование денежной суммы"""
    return f"{amount:,.2f} {currency}"


def validate_email(email: str) -> bool:
    """Валидация email"""
    import re
    pattern = r'^[\w\.-]+@[\w\.-]+\.\w+$'
    return bool(re.match(pattern, email))
