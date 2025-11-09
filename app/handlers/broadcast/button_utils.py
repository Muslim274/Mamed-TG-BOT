"""
Утилиты для работы с кнопками в рассылке
app/handlers/broadcast/button_utils.py
"""
import re
import logging
from typing import List, Tuple, Optional
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

logger = logging.getLogger(__name__)


def parse_buttons(text: str) -> Tuple[List[List[dict]], List[str]]:
    """
    Парсинг кнопок из текста в смешанном формате
    
    Поддерживаемые форматы:
    - Текст кнопки | url:https://example.com
    - Текст кнопки | callback:action_name  
    - Текст кнопки | простой_текст (автоматически станет broadcast_простой_текст)
    
    Args:
        text: Текст с кнопками (каждая кнопка с новой строки)
    
    Returns:
        Tuple[List[List[dict]], List[str]]: (структура кнопок, список ошибок)
    """
    lines = text.strip().split('\n')
    buttons_data = []
    errors = []
    
    for i, line in enumerate(lines, 1):
        line = line.strip()
        if not line:
            continue
            
        # Проверяем формат: Текст | данные
        if '|' not in line:
            errors.append(f"Строка {i}: Неверный формат. Используйте: Текст | данные")
            continue
            
        parts = line.split('|', 1)
        if len(parts) != 2:
            errors.append(f"Строка {i}: Неверный формат разделения")
            continue
            
        button_text = parts[0].strip()
        button_data = parts[1].strip()
        
        if not button_text:
            errors.append(f"Строка {i}: Пустой текст кнопки")
            continue
            
        if not button_data:
            errors.append(f"Строка {i}: Пустые данные кнопки")
            continue
        
        # Проверяем длину текста кнопки (лимит Telegram)
        if len(button_text) > 64:
            errors.append(f"Строка {i}: Текст кнопки слишком длинный (максимум 64 символа)")
            continue
        
        # Определяем тип кнопки
        button_info = parse_button_data(button_text, button_data, i)
        if button_info:
            if 'error' in button_info:
                errors.append(button_info['error'])
            else:
                # Каждая кнопка в отдельном ряду
                buttons_data.append([button_info])
        
    return buttons_data, errors


def parse_button_data(text: str, data: str, line_num: int) -> Optional[dict]:
    """
    Парсинг данных одной кнопки
    
    Args:
        text: Текст кнопки
        data: Данные кнопки
        line_num: Номер строки (для ошибок)
    
    Returns:
        dict: Информация о кнопке или ошибка
    """
    # URL кнопка
    if data.startswith('url:'):
        url = data[4:].strip()
        if not url:
            return {'error': f"Строка {line_num}: Пустой URL"}
        
        # Базовая валидация URL
        if not (url.startswith('http://') or url.startswith('https://') or url.startswith('tg://')):
            return {'error': f"Строка {line_num}: URL должен начинаться с http://, https:// или tg://"}
        
        return {
            'type': 'url',
            'text': text,
            'url': url
        }
    
    # Callback кнопка с явным указанием
    elif data.startswith('callback:'):
        callback_data = data[9:].strip()
        if not callback_data:
            return {'error': f"Строка {line_num}: Пустой callback_data"}
            
        # Проверяем длину callback_data (лимит Telegram)
        if len(callback_data) > 64:
            return {'error': f"Строка {line_num}: callback_data слишком длинный (максимум 64 символа)"}
        
        return {
            'type': 'callback',
            'text': text,
            'callback_data': callback_data
        }
    
    # Простой текст - автоматически добавляем префикс broadcast_
    else:
        # Очищаем данные от недопустимых символов
        clean_data = re.sub(r'[^a-zA-Z0-9_]', '_', data.lower())
        callback_data = f"broadcast_{clean_data}"
        
        # Проверяем итоговую длину
        if len(callback_data) > 64:
            return {'error': f"Строка {line_num}: Слишком длинное название действия"}
        
        return {
            'type': 'callback',
            'text': text,
            'callback_data': callback_data,
            'original_data': data  # Сохраняем оригинальные данные для логирования
        }


def create_keyboard_from_buttons(buttons_data: List[List[dict]]) -> InlineKeyboardMarkup:
    """
    Создание InlineKeyboardMarkup из структуры кнопок
    
    Args:
        buttons_data: Структура кнопок [[{кнопка1}, {кнопка2}], [{кнопка3}]]
    
    Returns:
        InlineKeyboardMarkup: Готовая клавиатура
    """
    keyboard_rows = []
    
    for row in buttons_data:
        keyboard_row = []
        for button in row:
            if button['type'] == 'url':
                keyboard_row.append(
                    InlineKeyboardButton(
                        text=button['text'],
                        url=button['url']
                    )
                )
            elif button['type'] == 'callback':
                keyboard_row.append(
                    InlineKeyboardButton(
                        text=button['text'],
                        callback_data=button['callback_data']
                    )
                )
        
        if keyboard_row:
            keyboard_rows.append(keyboard_row)
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard_rows)


def format_buttons_preview(buttons_data: List[List[dict]]) -> str:
    """
    Форматирование предпросмотра кнопок для показа админу
    
    Args:
        buttons_data: Структура кнопок
    
    Returns:
        str: Текстовое представление кнопок
    """
    if not buttons_data:
        return "Кнопки не добавлены"
    
    preview = "🔘 <b>Кнопки:</b>\n"
    
    for i, row in enumerate(buttons_data, 1):
        for j, button in enumerate(row):
            if button['type'] == 'url':
                preview += f"   {i}.{j+1} 🔗 {button['text']} → {button['url']}\n"
            elif button['type'] == 'callback':
                action = button.get('original_data', button['callback_data'])
                preview += f"   {i}.{j+1} 🎯 {button['text']} → {action}\n"
    
    return preview


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
