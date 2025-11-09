"""
Вспомогательные функции для системы рассылки с поддержкой кнопок
app/handlers/broadcast/broadcast_utils.py
"""
import re
import logging
from typing import List, Tuple, Set
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

logger = logging.getLogger(__name__)


def parse_telegram_ids(text: str) -> List[int]:
    """
    Парсинг списка Telegram ID из текста
    
    Поддерживаемые форматы:
    - "123456789, 987654321, 555444333"
    - "123456789 987654321 555444333" 
    - "123456789\n987654321\n555444333"
    - Смешанные форматы
    
    Returns:
        List[int]: Список уникальных Telegram ID
    """
    # Удаляем все нечисловые символы кроме разделителей
    # Заменяем запятые, пробелы, переводы строк на пробелы
    cleaned_text = re.sub(r'[^\d\s,\n]', ' ', text)
    cleaned_text = re.sub(r'[,\s\n]+', ' ', cleaned_text)
    
    # Извлекаем числа
    ids = []
    for part in cleaned_text.split():
        part = part.strip()
        if part and part.isdigit():
            telegram_id = int(part)
            # Проверяем что это похоже на Telegram ID (обычно > 100000)
            if telegram_id > 100000:
                ids.append(telegram_id)
    
    # Удаляем дубликаты, сохраняя порядок
    unique_ids = []
    seen = set()
    for id in ids:
        if id not in seen:
            unique_ids.append(id)
            seen.add(id)
    
    logger.info(f"Parsed {len(unique_ids)} unique IDs from text: {unique_ids[:5]}...")
    return unique_ids


def get_audience_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура выбора аудитории"""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📊 Всем пользователям", callback_data="send_all")],
            [InlineKeyboardButton(text="🆕 Новые лиды (не оплатили)", callback_data="send_leads")],
            [InlineKeyboardButton(text="🤝 Партнеры", callback_data="send_partners")],
            [InlineKeyboardButton(text="🎓 Партнёры завершили обучение", callback_data="send_done")],
            [InlineKeyboardButton(text="⚠️ Партнёры не вступили в команду", callback_data="send_no_team")],
            [InlineKeyboardButton(text="💪 Партнёры вступили в команду", callback_data="send_in_team")],
            [InlineKeyboardButton(text="📚 Еще обучаются", callback_data="send_learning")],
            [InlineKeyboardButton(text="👥 Определенным пользователям", callback_data="send_custom")],
            [InlineKeyboardButton(text="❌ Отменить", callback_data="cancel_broadcast")]
        ]
    )


def get_validation_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура после валидации ID"""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Да, продолжить",
                    callback_data="broadcast_confirm_users"  # ИСПРАВЛЕНО
                )
            ],
            [
                InlineKeyboardButton(
                    text="✏️ Изменить список",
                    callback_data="broadcast_edit_users"  # ИСПРАВЛЕНО
                )
            ],
            [
                InlineKeyboardButton(
                    text="❌ Отменить",
                    callback_data="cancel_broadcast"
                )
            ]
        ]
    )


def get_confirmation_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура подтверждения рассылки"""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Отправить",
                    callback_data="broadcast_confirm_send"
                )
            ],
            [
                InlineKeyboardButton(
                    text="✏️ Изменить сообщение",
                    callback_data="broadcast_edit_message"
                )
            ],
            [
                InlineKeyboardButton(
                    text="❌ Отменить",
                    callback_data="cancel_broadcast"
                )
            ]
        ]
    )


def get_buttons_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура для выбора - добавлять кнопки или нет"""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="➕ Добавить кнопки",
                    callback_data="broadcast_add_buttons"
                )
            ],
            [
                InlineKeyboardButton(
                    text="➡️ Продолжить без кнопок",
                    callback_data="broadcast_no_buttons"
                )
            ],
            [
                InlineKeyboardButton(
                    text="❌ Отменить",
                    callback_data="cancel_broadcast"
                )
            ]
        ]
    )


def format_user_list_preview(recipients, requested_ids):
    """Форматирование предпросмотра списка пользователей"""
    found_count = len(recipients)
    total_count = len(requested_ids)
    
    if found_count == 0:
        return """
❌ <b>Пользователи не найдены</b>

📊 <b>Результат проверки:</b>
- Найдено пользователей: 0/{}
- Все указанные ID отсутствуют в базе данных

💡 Проверьте правильность ID и попробуйте еще раз.
""".format(total_count)
    
    # Получаем найденные ID
    found_ids = {recipient['telegram_id'] for recipient in recipients}
    not_found_ids = [id for id in requested_ids if id not in found_ids]
    
    preview_text = f"""
✅ <b>Проверка завершена</b>

📊 <b>Результат:</b>
- Найдено пользователей: {found_count}/{total_count}"""
    
    if not_found_ids:
        preview_text += f"\n• Не найдено в БД: {len(not_found_ids)}"
        for id in not_found_ids[:5]:  # Показываем максимум 5 ID
            preview_text += f"\n  - {id} ❌"
        if len(not_found_ids) > 5:
            preview_text += f"\n  ... и еще {len(not_found_ids) - 5}"
    
    preview_text += "\n\n💡 Продолжить с найденными пользователями?"
    
    return preview_text


def format_broadcast_preview(user_count: int, message_text: str, audience_type: str = "пользователям", admin_name: str = "Неизвестно") -> str:
    """
    Форматирование предпросмотра рассылки
    
    Args:
        user_count: Количество получателей
        message_text: Текст сообщения
        audience_type: Тип аудитории (всем/оплатившим/выбранным)
        admin_name: Имя админа
    
    Returns:
        str: Отформатированный предпросмотр
    """
    text = f"📢 <b>ПРЕДПРОСМОТР РАССЫЛКИ</b>\n\n"
    text += f"👤 <b>Отправитель:</b> {admin_name}\n"
    text += f"👥 <b>Получатели:</b> {user_count} {audience_type}\n"
    text += f"📝 <b>Сообщение:</b>\n"
    text += f"━━━━━━━━━━━━━━━━━━━━\n"
    text += f"{message_text}\n"
    text += f"━━━━━━━━━━━━━━━━━━━━\n\n"
    text += f"Отправить сейчас?"
    
    return text


def format_buttons_preview(buttons_data: List[List[dict]]) -> str:
    """
    Форматирование предпросмотра кнопок для показа админу
    
    Args:
        buttons_data: Структура кнопок
    
    Returns:
        str: Текстовое представление кнопок
    """
    if not buttons_data:
        return "🔘 <b>Кнопки:</b> Без кнопок"
    
    preview = "🔘 <b>Кнопки:</b>\n"
    
    for i, row in enumerate(buttons_data, 1):
        for j, button in enumerate(row):
            if button['type'] == 'url':
                preview += f"   {i}.{j+1} 🔗 {button['text']} → {button['url']}\n"
            elif button['type'] == 'callback':
                action = button.get('original_data', button['callback_data'])
                preview += f"   {i}.{j+1} 🎯 {button['text']} → {action}\n"
    
    return preview


def format_progress_message(current: int, total: int, successful: int, errors: int, admin_name: str = "Неизвестно") -> str:
    """
    Форматирование сообщения о прогрессе рассылки
    
    Args:
        current: Текущее количество обработанных
        total: Общее количество
        successful: Успешно доставлено
        errors: Количество ошибок
        admin_name: Имя админа
    
    Returns:
        str: Отформатированное сообщение
    """
    percentage = int((current / total) * 100) if total > 0 else 0
    
    text = f"🚀 <b>Рассылка в процессе...</b>\n\n"
    text += f"👤 <b>Инициатор:</b> {admin_name}\n"
    text += f"📊 <b>Прогресс:</b> {current}/{total} ({percentage}%)\n"
    text += f"✅ <b>Доставлено:</b> {successful}\n"
    
    if errors > 0:
        text += f"❌ <b>Ошибки:</b> {errors}\n"
    
    # Простая полоса прогресса
    filled = int((current / total) * 20) if total > 0 else 0
    empty = 20 - filled
    progress_bar = "█" * filled + "░" * empty
    text += f"\n[{progress_bar}]"
    
    return text


def format_final_report(total: int, successful: int, errors: int, error_details: dict, duration, admin_name: str, admin_id: int) -> str:
    """
    Форматирование финального отчета рассылки
    
    Args:
        total: Общее количество
        successful: Успешно доставлено
        errors: Количество ошибок
        error_details: Детали ошибок
        duration: Длительность (timedelta)
        admin_name: Имя админа
        admin_id: ID админа
    
    Returns:
        str: Отформатированный отчет
    """
    success_rate = (successful / total * 100) if total > 0 else 0
    
    duration_seconds = int(duration.total_seconds())
    minutes = duration_seconds // 60
    seconds = duration_seconds % 60
    duration_str = f"{minutes}м {seconds}с" if minutes > 0 else f"{seconds}с"
    
    text = f"🎉 <b>Рассылка завершена!</b>\n\n"
    text += f"👤 <b>Инициатор:</b> {admin_name} (<code>{admin_id}</code>)\n"
    text += f"📈 <b>Финальная статистика:</b>\n"
    text += f"✅ Успешно доставлено: {successful}/{total} ({success_rate:.1f}%)\n"
    
    if errors > 0:
        text += f"❌ Не доставлено: {errors}\n"
        
        # Детали ошибок
        blocked_count = error_details.get('blocked', 0)
        not_found_count = error_details.get('not_found', 0)
        other_errors = error_details.get('other', 0)
        
        if blocked_count > 0:
            text += f"  - Заблокировали бота: {blocked_count}\n"
        if not_found_count > 0:
            text += f"  - Пользователь не найден: {not_found_count}\n"
        if other_errors > 0:
            text += f"  - Другие ошибки: {other_errors}\n"
    
    text += f"\n⏱ <b>Время выполнения:</b> {duration_str}"
    
    return text


def validate_message_length(text: str) -> bool:
    """
    Валидация длины сообщения для Telegram
    
    Args:
        text: Текст сообщения
    
    Returns:
        bool: True если валидно
    """
    if not text:
        return False
    
    max_length = 4096  # Максимальная длина сообщения в Telegram
    return len(text) <= max_length and len(text.strip()) > 0


def validate_buttons_input(text: str) -> Tuple[bool, str]:
    """
    Валидация ввода кнопок
    
    Args:
        text: Введенный текст с кнопками
    
    Returns:
        Tuple[bool, str]: (валидно, сообщение об ошибке)
    """
    if not text or not text.strip():
        return False, "Введите хотя бы одну кнопку"
    
    lines = [line.strip() for line in text.strip().split('\n') if line.strip()]
    
    if len(lines) > 10:
        return False, f"Слишком много кнопок ({len(lines)}). Максимум: 10"
    
    # Проверяем базовый формат
    for i, line in enumerate(lines, 1):
        if '|' not in line:
            return False, f"Строка {i}: Используйте формат 'Текст кнопки | данные'"
    
    return True, ""