"""
Централизованный список всех админских команд для избежания конфликтов handlers
app/constants/admin_commands.py
"""

from aiogram import F


# === СПЕЦИФИЧНЫЕ АДМИНСКИЕ КОМАНДЫ ===
# При добавлении новой команды - добавляй ТОЛЬКО СЮДА!

# Команды из admin_delete_user.py
ADMIN_DELETE_COMMANDS = [
    "clean_db_user",           # удаление пользователя из БД
]

# Команды из broadcast_handler.py  
ADMIN_BROADCAST_COMMANDS = [
    "/broadcast",              # система рассылки
]

# Команды из video_uniquifier
ADMIN_VIDEO_COMMANDS = [
    "m_video_unikal",          # обработка видео
]

# Команды из enhanced_support.py
ADMIN_SUPPORT_COMMANDS = [
    "/tickets",                # показать открытые тикеты
]

# Команды из admin_menu.py (если есть дополнительные)
ADMIN_MENU_COMMANDS = [
    # добавь здесь специфичные команды admin_menu, если есть
]

# GetCourse callback команды (из payment.py)
ADMIN_GETCOURSE_CALLBACKS = [
    "admin_approve_getcourse:",    # одобрение GetCourse (префикс)
    "admin_reject_getcourse:",     # отклонение GetCourse (префикс)
]

# === ПОЛНЫЙ СПИСОК ВСЕХ СПЕЦИФИЧНЫХ КОМАНД ===
ADMIN_SPECIFIC_COMMANDS = (
    ADMIN_DELETE_COMMANDS + 
    ADMIN_BROADCAST_COMMANDS + 
    ADMIN_VIDEO_COMMANDS + 
    ADMIN_SUPPORT_COMMANDS + 
    ADMIN_MENU_COMMANDS
)

# === CALLBACK ПРЕФИКСЫ (для callback_query handlers) ===
ADMIN_SPECIFIC_CALLBACK_PREFIXES = ADMIN_GETCOURSE_CALLBACKS


# === ФУНКЦИИ ДЛЯ УДОБСТВА ===

def get_admin_exclusion_filter():
    """
    Возвращает фильтр исключения админских команд для MESSAGE handlers
    
    Использование:
    @router.message(
        F.from_user.id == settings.ADMIN_ID,
        get_admin_exclusion_filter(),  # 🎯 Единый источник истины!
        # остальные фильтры...
    )
    """
    return ~F.text.in_(ADMIN_SPECIFIC_COMMANDS)


def get_admin_callback_exclusion_filter():
    """
    Возвращает фильтр исключения админских callback'ов для CALLBACK handlers
    
    Использование:
    @router.callback_query(
        F.from_user.id == settings.ADMIN_ID,
        get_admin_callback_exclusion_filter(),
        # остальные фильтры...
    )
    """
    # Создаем фильтр который исключает callback'и начинающиеся с админских префиксов
    exclusion_conditions = []
    for prefix in ADMIN_SPECIFIC_CALLBACK_PREFIXES:
        exclusion_conditions.append(~F.data.startswith(prefix))
    
    # Объединяем все условия через &
    if exclusion_conditions:
        result = exclusion_conditions[0]
        for condition in exclusion_conditions[1:]:
            result = result & condition
        return result
    else:
        # Если нет префиксов, возвращаем True (не исключаем ничего)
        return F.data.regexp(r'.*')  # всегда True


def is_admin_command(text: str) -> bool:
    """
    Проверяет, является ли текст специфичной админской командой
    
    Args:
        text: Текст сообщения для проверки
        
    Returns:
        bool: True если это специфичная админская команда
    """
    return text in ADMIN_SPECIFIC_COMMANDS


def is_admin_callback(callback_data: str) -> bool:
    """
    Проверяет, является ли callback_data специфичным админским callback'ом
    
    Args:
        callback_data: Данные callback'а для проверки
        
    Returns:
        bool: True если это специфичный админский callback
    """
    return any(callback_data.startswith(prefix) for prefix in ADMIN_SPECIFIC_CALLBACK_PREFIXES)


# === ЛОГИРОВАНИЕ ДЛЯ ОТЛАДКИ ===
def log_admin_commands():
    """Выводит все админские команды в лог (для отладки)"""
    import logging
    logger = logging.getLogger(__name__)
    
    logger.info("📋 ADMIN COMMANDS REGISTRY:")
    logger.info(f"   Delete commands: {ADMIN_DELETE_COMMANDS}")
    logger.info(f"   Broadcast commands: {ADMIN_BROADCAST_COMMANDS}")
    logger.info(f"   Video commands: {ADMIN_VIDEO_COMMANDS}")
    logger.info(f"   Support commands: {ADMIN_SUPPORT_COMMANDS}")
    logger.info(f"   Menu commands: {ADMIN_MENU_COMMANDS}")
    logger.info(f"   Callback prefixes: {ADMIN_SPECIFIC_CALLBACK_PREFIXES}")
    logger.info(f"   TOTAL specific commands: {len(ADMIN_SPECIFIC_COMMANDS)}")


# === ВАЛИДАЦИЯ (опционально) ===
def validate_command_uniqueness():
    """
    Проверяет уникальность всех команд (без дублирования)
    Можно вызвать при запуске приложения для проверки
    """
    all_commands = ADMIN_SPECIFIC_COMMANDS
    unique_commands = set(all_commands)
    
    if len(all_commands) != len(unique_commands):
        duplicates = []
        seen = set()
        for cmd in all_commands:
            if cmd in seen:
                duplicates.append(cmd)
            seen.add(cmd)
        
        raise ValueError(f"🚨 DUPLICATE ADMIN COMMANDS FOUND: {duplicates}")
    
    return True
