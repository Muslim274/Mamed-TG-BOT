"""
Обработчики для админских отчетов
"""
import csv
import io
import logging
from datetime import datetime, timedelta
from aiogram import Router, types, F
from aiogram.filters import Command
from aiogram.types import BufferedInputFile, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext

from app.config import settings
from app.database.connection import AsyncSessionLocal
from app.database.statistics_crud import StatisticsCRUD, UserSegmentCRUD
from app.handlers.admin.report_states import ReportStates

logger = logging.getLogger(__name__)

router = Router()

# Максимальная длина сообщения в Telegram
MAX_MESSAGE_LENGTH = 4096


async def send_long_message(message_or_callback, text: str, parse_mode: str = "HTML", **kwargs):
    """
    Отправляет длинное сообщение, разбивая его на части если необходимо

    Args:
        message_or_callback: Message или CallbackQuery объект
        text: Текст для отправки
        parse_mode: Режим парсинга (HTML/Markdown)
        **kwargs: Дополнительные параметры для answer/edit_text
    """
    # Если это callback, получаем message
    if hasattr(message_or_callback, 'message'):
        message = message_or_callback.message
        is_callback = True
    else:
        message = message_or_callback
        is_callback = False

    # Если сообщение короткое, отправляем как обычно
    if len(text) <= MAX_MESSAGE_LENGTH:
        if is_callback:
            return await message.edit_text(text, parse_mode=parse_mode, **kwargs)
        else:
            return await message.answer(text, parse_mode=parse_mode, **kwargs)

    # Разбиваем длинное сообщение на части
    parts = []
    current_part = ""

    # Разбиваем по строкам, чтобы не ломать форматирование
    lines = text.split('\n')

    for line in lines:
        # Если добавление этой строки превысит лимит
        if len(current_part) + len(line) + 1 > MAX_MESSAGE_LENGTH:
            if current_part:
                parts.append(current_part)
                current_part = line + '\n'
            else:
                # Если одна строка длиннее лимита, режем её насильно
                while len(line) > MAX_MESSAGE_LENGTH:
                    parts.append(line[:MAX_MESSAGE_LENGTH])
                    line = line[MAX_MESSAGE_LENGTH:]
                current_part = line + '\n' if line else ""
        else:
            current_part += line + '\n'

    # Добавляем последнюю часть
    if current_part:
        parts.append(current_part)

    # Отправляем части
    for i, part in enumerate(parts):
        if i == 0 and is_callback:
            # Первую часть отправляем через edit_text для callback
            await message.edit_text(part, parse_mode=parse_mode, **kwargs)
        else:
            # Остальные части через answer
            await message.answer(part, parse_mode=parse_mode, **kwargs)

    return None


def is_admin(user_id: int) -> bool:
    """Проверка, является ли пользователь администратором"""
    return user_id in settings.admin_ids_list


def get_period_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура выбора периода отчёта"""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📅 За день", callback_data="report_daily")],
            [InlineKeyboardButton(text="⏱ За период", callback_data="report_period")],
            [InlineKeyboardButton(text="🧾 За всё время", callback_data="report_all_time")]
        ]
    )


def validate_date(date_str: str) -> tuple[bool, datetime | None]:
    """
    Валидация даты в формате ДД.ММ.ГГГГ

    Returns:
        tuple[bool, datetime | None]: (валидность, объект datetime если валидно)
    """
    try:
        date_obj = datetime.strptime(date_str.strip(), '%d.%m.%Y')
        return True, date_obj
    except ValueError:
        return False, None


@router.message(Command("get_info"))
async def cmd_get_info(message: types.Message, state: FSMContext):
    """
    Команда /get_info - расширенная версия с выбором периода отчёта
    """
    if not is_admin(message.from_user.id):
        await message.answer("У вас нет доступа к этой команде.")
        return

    logger.info(f"Admin {message.from_user.id} requested report")

    # Показываем клавиатуру выбора периода
    await message.answer(
        "📊 <b>Выберите период для отчёта:</b>",
        parse_mode="HTML",
        reply_markup=get_period_keyboard()
    )

    await state.set_state(ReportStates.choosing_period)


@router.callback_query(F.data == "report_daily", ReportStates.choosing_period)
async def report_daily_handler(callback: types.CallbackQuery, state: FSMContext):
    """Обработчик отчёта за день"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Нет доступа", show_alert=True)
        return

    logger.info(f"Admin {callback.from_user.id} requested daily report")

    # Отправляем сообщение о начале генерации отчета
    status_msg = await callback.message.edit_text("Генерирую отчет за сегодня...")

    try:
        async with AsyncSessionLocal() as session:
            # Получаем данные за сегодня
            today = datetime.now()

            # 1. Продажи за день
            sales_data = await StatisticsCRUD.get_daily_sales(session, today)

            # 2. Покупатели за день
            buyers = await StatisticsCRUD.get_daily_buyers(session, today)

            # 3. Новые лиды
            new_leads = await StatisticsCRUD.get_new_leads(session, today)

            # 4. Новые партнеры
            new_partners = await StatisticsCRUD.get_new_partners(session, today)

            # 5. Партнеры без команды (за день)
            partners_no_team = await StatisticsCRUD.get_partners_without_team(session, today)

            # Формируем текстовый отчет
            report_text = f"""
📊 <b>ЕЖЕДНЕВНЫЙ ОТЧЕТ</b>
📅 Дата: {today.strftime('%d.%m.%Y')}

━━━━━━━━━━━━━━━━━━━━━━

💰 <b>ПРОДАЖИ ЗА ДЕНЬ</b>
• Количество: {sales_data['count']}
• Сумма: {sales_data['total_amount']:,.0f} руб.
• Комиссия: {sales_data['total_commission']:,.0f} руб.

━━━━━━━━━━━━━━━━━━━━━━

👥 <b>ПОКУПАТЕЛИ ({len(buyers)})</b>
"""
            if buyers:
                for buyer in buyers:
                    username = f"@{buyer['username']}" if buyer['username'] else "Нет username"
                    time_str = buyer['purchased_at'].strftime('%H:%M')
                    report_text += f"\n• {buyer['full_name']} ({username})\n"
                    report_text += f"  ID: {buyer['telegram_id']}\n"
                    report_text += f"  Сумма: {buyer['amount']:,.0f} руб.\n"
                    report_text += f"  Время: {time_str}\n"
            else:
                report_text += "\nНет покупателей за сегодня\n"

            report_text += f"""
━━━━━━━━━━━━━━━━━━━━━━

🆕 <b>НОВЫЕ ЛИДЫ ({len(new_leads)})</b>
"""
            if new_leads:
                for lead in new_leads:
                    username = f"@{lead.username}" if lead.username else "Нет username"
                    time_str = lead.created_at.strftime('%H:%M')
                    report_text += f"\n• {lead.full_name} ({username})\n"
                    report_text += f"  ID: {lead.telegram_id}\n"
                    report_text += f"  Время: {time_str}\n"
            else:
                report_text += "\nНет новых лидов за сегодня\n"

            report_text += f"""
━━━━━━━━━━━━━━━━━━━━━━

🤝 <b>НОВЫЕ ПАРТНЕРЫ ({len(new_partners)})</b>
"""
            if new_partners:
                for partner in new_partners:
                    username = f"@{partner.username}" if partner.username else "Нет username"
                    time_str = partner.stage_completed_at.strftime('%H:%M')
                    report_text += f"\n• {partner.full_name} ({username})\n"
                    report_text += f"  ID: {partner.telegram_id}\n"
                    report_text += f"  Время: {time_str}\n"
            else:
                report_text += "\nНет новых партнеров за сегодня\n"

            report_text += f"""
━━━━━━━━━━━━━━━━━━━━━━

⚠️ <b>ПАРТНЕРЫ БЕЗ КОМАНДЫ ({len(partners_no_team)})</b>
<i>Купили партнерку, но не нажали "Команда"</i>
"""
            if partners_no_team:
                for user in partners_no_team:
                    username = f"@{user.username}" if user.username else "Нет username"
                    payment_time = user.stage_payment_ok_at.strftime('%H:%M') if user.stage_payment_ok_at else "N/A"
                    report_text += f"\n• {user.full_name} ({username})\n"
                    report_text += f"  ID: {user.telegram_id}\n"
                    report_text += f"  Оплата: {payment_time}\n"
                    report_text += f"  Стадия: {user.onboarding_stage}\n"
            else:
                report_text += "\nНет таких пользователей за сегодня\n"

            # Отправляем текстовый отчет (с автоматическим разбиением на части если нужно)
            await send_long_message(status_msg, report_text, parse_mode="HTML")

            # Генерируем CSV файл
            csv_buffer = io.StringIO()
            csv_writer = csv.writer(csv_buffer)

            # Заголовки CSV
            csv_writer.writerow([
                "Категория", "Имя", "Username", "Telegram ID",
                "Сумма", "Время", "Стадия"
            ])

            # Добавляем покупателей
            for buyer in buyers:
                csv_writer.writerow([
                    "Покупатель",
                    buyer['full_name'],
                    buyer['username'] or "",
                    buyer['telegram_id'],
                    buyer['amount'],
                    buyer['purchased_at'].strftime('%Y-%m-%d %H:%M:%S'),
                    "Paid"
                ])

            # Добавляем новых лидов
            for lead in new_leads:
                csv_writer.writerow([
                    "Новый лид",
                    lead.full_name,
                    lead.username or "",
                    lead.telegram_id,
                    "",
                    lead.created_at.strftime('%Y-%m-%d %H:%M:%S'),
                    lead.onboarding_stage
                ])

            # Добавляем новых партнеров
            for partner in new_partners:
                csv_writer.writerow([
                    "Новый партнер",
                    partner.full_name,
                    partner.username or "",
                    partner.telegram_id,
                    "",
                    partner.stage_completed_at.strftime('%Y-%m-%d %H:%M:%S') if partner.stage_completed_at else "",
                    partner.onboarding_stage
                ])

            # Добавляем партнеров без команды
            for user in partners_no_team:
                csv_writer.writerow([
                    "Партнер без команды",
                    user.full_name,
                    user.username or "",
                    user.telegram_id,
                    "",
                    user.stage_payment_ok_at.strftime('%Y-%m-%d %H:%M:%S') if user.stage_payment_ok_at else "",
                    user.onboarding_stage
                ])

            # Отправляем CSV файл
            csv_data = csv_buffer.getvalue().encode('utf-8-sig')  # utf-8-sig для корректного отображения в Excel
            csv_file = BufferedInputFile(
                csv_data,
                filename=f"daily_report_{today.strftime('%Y%m%d')}.csv"
            )

            await callback.message.answer_document(
                document=csv_file,
                caption=f"📊 CSV отчет за {today.strftime('%d.%m.%Y')}"
            )

            logger.info(f"Daily report sent to admin {callback.from_user.id}")

    except Exception as e:
        logger.error(f"Error generating daily report: {e}", exc_info=True)
        await status_msg.edit_text(
            f"❌ Ошибка при генерации отчета:\n{str(e)}"
        )
    finally:
        await state.clear()


@router.callback_query(F.data == "report_period", ReportStates.choosing_period)
async def report_period_handler(callback: types.CallbackQuery, state: FSMContext):
    """Обработчик выбора отчёта за период"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Нет доступа", show_alert=True)
        return

    logger.info(f"Admin {callback.from_user.id} requested period report")

    await callback.message.edit_text(
        "📅 Введите начальную дату периода в формате <b>ДД.ММ.ГГГГ</b>\n\n"
        "Например: 01.01.2025",
        parse_mode="HTML"
    )
    await state.set_state(ReportStates.entering_start_date)
    await callback.answer()


@router.message(ReportStates.entering_start_date)
async def process_start_date(message: types.Message, state: FSMContext):
    """Обработчик ввода начальной даты"""
    if not is_admin(message.from_user.id):
        await message.answer("❌ Нет доступа")
        return

    is_valid, start_date = validate_date(message.text)

    if not is_valid:
        await message.answer(
            "❌ Неверный формат даты!\n\n"
            "Пожалуйста, введите дату в формате <b>ДД.ММ.ГГГГ</b>\n"
            "Например: 01.01.2025",
            parse_mode="HTML"
        )
        return

    # Сохраняем начальную дату
    await state.update_data(start_date=start_date)

    await message.answer(
        "📅 Теперь введите конечную дату периода в формате <b>ДД.ММ.ГГГГ</b>\n\n"
        "Например: 31.01.2025",
        parse_mode="HTML"
    )
    await state.set_state(ReportStates.entering_end_date)


@router.message(ReportStates.entering_end_date)
async def process_end_date(message: types.Message, state: FSMContext):
    """Обработчик ввода конечной даты и генерация отчёта за период"""
    if not is_admin(message.from_user.id):
        await message.answer("❌ Нет доступа")
        return

    is_valid, end_date = validate_date(message.text)

    if not is_valid:
        await message.answer(
            "❌ Неверный формат даты!\n\n"
            "Пожалуйста, введите дату в формате <b>ДД.ММ.ГГГГ</b>\n"
            "Например: 31.01.2025",
            parse_mode="HTML"
        )
        return

    # Получаем начальную дату
    data = await state.get_data()
    start_date = data.get('start_date')

    if not start_date:
        await message.answer("❌ Ошибка: начальная дата не найдена. Начните заново с /get_info")
        await state.clear()
        return

    # Проверяем, что конечная дата >= начальной
    if end_date < start_date:
        await message.answer(
            "❌ Конечная дата не может быть раньше начальной!\n\n"
            "Пожалуйста, введите корректную конечную дату.",
            parse_mode="HTML"
        )
        return

    # Генерируем отчёт
    status_msg = await message.answer(
        f"Генерирую отчёт за период {start_date.strftime('%d.%m.%Y')} - {end_date.strftime('%d.%m.%Y')}..."
    )

    try:
        async with AsyncSessionLocal() as session:
            # Получаем данные за период
            sales_data = await StatisticsCRUD.get_period_sales(session, start_date, end_date)
            buyers = await StatisticsCRUD.get_period_buyers(session, start_date, end_date)
            new_leads = await StatisticsCRUD.get_period_leads(session, start_date, end_date)
            new_partners = await StatisticsCRUD.get_period_partners(session, start_date, end_date)
            partners_no_team = await StatisticsCRUD.get_period_partners_without_team(session, start_date, end_date)

            # Формируем текстовый отчет
            report_text = f"""
📊 <b>ОТЧЁТ ЗА ПЕРИОД</b>
📅 Период: {start_date.strftime('%d.%m.%Y')} - {end_date.strftime('%d.%m.%Y')}

━━━━━━━━━━━━━━━━━━━━━━

💰 <b>ПРОДАЖИ ЗА ПЕРИОД</b>
• Количество: {sales_data['count']}
• Сумма: {sales_data['total_amount']:,.0f} руб.
• Комиссия: {sales_data['total_commission']:,.0f} руб.

━━━━━━━━━━━━━━━━━━━━━━

👥 <b>ПОКУПАТЕЛИ ({len(buyers)})</b>
"""
            if buyers:
                for buyer in buyers:
                    username = f"@{buyer['username']}" if buyer['username'] else "Нет username"
                    time_str = buyer['purchased_at'].strftime('%d.%m.%Y %H:%M')
                    report_text += f"\n• {buyer['full_name']} ({username})\n"
                    report_text += f"  ID: {buyer['telegram_id']}\n"
                    report_text += f"  Сумма: {buyer['amount']:,.0f} руб.\n"
                    report_text += f"  Дата: {time_str}\n"
            else:
                report_text += "\nНет покупателей за период\n"

            report_text += f"""
━━━━━━━━━━━━━━━━━━━━━━

🆕 <b>НОВЫЕ ЛИДЫ ({len(new_leads)})</b>
"""
            if new_leads:
                for lead in new_leads:
                    username = f"@{lead.username}" if lead.username else "Нет username"
                    time_str = lead.created_at.strftime('%d.%m.%Y %H:%M')
                    report_text += f"\n• {lead.full_name} ({username})\n"
                    report_text += f"  ID: {lead.telegram_id}\n"
                    report_text += f"  Дата: {time_str}\n"
            else:
                report_text += "\nНет новых лидов за период\n"

            report_text += f"""
━━━━━━━━━━━━━━━━━━━━━━

🤝 <b>НОВЫЕ ПАРТНЕРЫ ({len(new_partners)})</b>
"""
            if new_partners:
                for partner in new_partners:
                    username = f"@{partner.username}" if partner.username else "Нет username"
                    time_str = partner.stage_completed_at.strftime('%d.%m.%Y %H:%M')
                    report_text += f"\n• {partner.full_name} ({username})\n"
                    report_text += f"  ID: {partner.telegram_id}\n"
                    report_text += f"  Дата: {time_str}\n"
            else:
                report_text += "\nНет новых партнеров за период\n"

            report_text += f"""
━━━━━━━━━━━━━━━━━━━━━━

⚠️ <b>ПАРТНЕРЫ БЕЗ КОМАНДЫ ({len(partners_no_team)})</b>
<i>Купили партнерку, но не нажали "Команда"</i>
"""
            if partners_no_team:
                for user in partners_no_team:
                    username = f"@{user.username}" if user.username else "Нет username"
                    payment_time = user.stage_payment_ok_at.strftime('%d.%m.%Y %H:%M') if user.stage_payment_ok_at else "N/A"
                    report_text += f"\n• {user.full_name} ({username})\n"
                    report_text += f"  ID: {user.telegram_id}\n"
                    report_text += f"  Оплата: {payment_time}\n"
                    report_text += f"  Стадия: {user.onboarding_stage}\n"
            else:
                report_text += "\nНет таких пользователей за период\n"

            # Отправляем текстовый отчет (с автоматическим разбиением на части если нужно)
            await send_long_message(status_msg, report_text, parse_mode="HTML")

            # Генерируем CSV файл
            csv_buffer = io.StringIO()
            csv_writer = csv.writer(csv_buffer)

            csv_writer.writerow([
                "Категория", "Имя", "Username", "Telegram ID",
                "Сумма", "Дата/Время", "Стадия"
            ])

            for buyer in buyers:
                csv_writer.writerow([
                    "Покупатель",
                    buyer['full_name'],
                    buyer['username'] or "",
                    buyer['telegram_id'],
                    buyer['amount'],
                    buyer['purchased_at'].strftime('%Y-%m-%d %H:%M:%S'),
                    "Paid"
                ])

            for lead in new_leads:
                csv_writer.writerow([
                    "Новый лид",
                    lead.full_name,
                    lead.username or "",
                    lead.telegram_id,
                    "",
                    lead.created_at.strftime('%Y-%m-%d %H:%M:%S'),
                    lead.onboarding_stage
                ])

            for partner in new_partners:
                csv_writer.writerow([
                    "Новый партнер",
                    partner.full_name,
                    partner.username or "",
                    partner.telegram_id,
                    "",
                    partner.stage_completed_at.strftime('%Y-%m-%d %H:%M:%S') if partner.stage_completed_at else "",
                    partner.onboarding_stage
                ])

            for user in partners_no_team:
                csv_writer.writerow([
                    "Партнер без команды",
                    user.full_name,
                    user.username or "",
                    user.telegram_id,
                    "",
                    user.stage_payment_ok_at.strftime('%Y-%m-%d %H:%M:%S') if user.stage_payment_ok_at else "",
                    user.onboarding_stage
                ])

            csv_data = csv_buffer.getvalue().encode('utf-8-sig')
            csv_file = BufferedInputFile(
                csv_data,
                filename=f"period_report_{start_date.strftime('%Y%m%d')}_{end_date.strftime('%Y%m%d')}.csv"
            )

            await message.answer_document(
                document=csv_file,
                caption=f"📊 CSV отчет за период {start_date.strftime('%d.%m.%Y')} - {end_date.strftime('%d.%m.%Y')}"
            )

            logger.info(f"Period report sent to admin {message.from_user.id}")

    except Exception as e:
        logger.error(f"Error generating period report: {e}", exc_info=True)
        await status_msg.edit_text(
            f"❌ Ошибка при генерации отчета:\n{str(e)}"
        )
    finally:
        await state.clear()


@router.callback_query(F.data == "report_all_time", ReportStates.choosing_period)
async def report_all_time_handler(callback: types.CallbackQuery, state: FSMContext):
    """Обработчик отчёта за всё время"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Нет доступа", show_alert=True)
        return

    logger.info(f"Admin {callback.from_user.id} requested all-time report")

    status_msg = await callback.message.edit_text("Генерирую отчет за всё время...")

    try:
        async with AsyncSessionLocal() as session:
            # Получаем данные за всё время
            sales_data = await StatisticsCRUD.get_all_time_sales(session)
            buyers = await StatisticsCRUD.get_all_time_buyers(session)
            new_leads = await StatisticsCRUD.get_all_time_leads(session)
            new_partners = await StatisticsCRUD.get_all_time_partners(session)
            partners_no_team = await StatisticsCRUD.get_all_time_partners_without_team(session)

            # Формируем текстовый отчет
            report_text = f"""
📊 <b>ОТЧЁТ ЗА ВСЁ ВРЕМЯ</b>

━━━━━━━━━━━━━━━━━━━━━━

💰 <b>ПРОДАЖИ</b>
• Количество: {sales_data['count']}
• Сумма: {sales_data['total_amount']:,.0f} руб.
• Комиссия: {sales_data['total_commission']:,.0f} руб.

━━━━━━━━━━━━━━━━━━━━━━

👥 <b>ПОКУПАТЕЛИ ({len(buyers)})</b>
"""
            # Для всех времени показываем только статистику, не весь список
            if buyers:
                report_text += f"\nВсего покупателей: {len(buyers)}\n"
                report_text += "\nПоследние 10 покупателей:\n"
                for buyer in sorted(buyers, key=lambda x: x['purchased_at'], reverse=True)[:10]:
                    username = f"@{buyer['username']}" if buyer['username'] else "Нет username"
                    time_str = buyer['purchased_at'].strftime('%d.%m.%Y %H:%M')
                    report_text += f"\n• {buyer['full_name']} ({username})\n"
                    report_text += f"  ID: {buyer['telegram_id']}\n"
                    report_text += f"  Сумма: {buyer['amount']:,.0f} руб.\n"
                    report_text += f"  Дата: {time_str}\n"
            else:
                report_text += "\nНет покупателей\n"

            report_text += f"""
━━━━━━━━━━━━━━━━━━━━━━

🆕 <b>ЛИДЫ</b>
Всего лидов: {len(new_leads)}

━━━━━━━━━━━━━━━━━━━━━━

🤝 <b>ПАРТНЕРЫ</b>
Всего партнеров: {len(new_partners)}

━━━━━━━━━━━━━━━━━━━━━━

⚠️ <b>ПАРТНЕРЫ БЕЗ КОМАНДЫ</b>
Всего: {len(partners_no_team)}
"""

            # Отправляем текстовый отчет (с автоматическим разбиением на части если нужно)
            await send_long_message(status_msg, report_text, parse_mode="HTML")

            # Генерируем CSV файл
            csv_buffer = io.StringIO()
            csv_writer = csv.writer(csv_buffer)

            csv_writer.writerow([
                "Категория", "Имя", "Username", "Telegram ID",
                "Сумма", "Дата/Время", "Стадия"
            ])

            for buyer in buyers:
                csv_writer.writerow([
                    "Покупатель",
                    buyer['full_name'],
                    buyer['username'] or "",
                    buyer['telegram_id'],
                    buyer['amount'],
                    buyer['purchased_at'].strftime('%Y-%m-%d %H:%M:%S'),
                    "Paid"
                ])

            for lead in new_leads:
                csv_writer.writerow([
                    "Лид",
                    lead.full_name,
                    lead.username or "",
                    lead.telegram_id,
                    "",
                    lead.created_at.strftime('%Y-%m-%d %H:%M:%S'),
                    lead.onboarding_stage
                ])

            for partner in new_partners:
                csv_writer.writerow([
                    "Партнер",
                    partner.full_name,
                    partner.username or "",
                    partner.telegram_id,
                    "",
                    partner.stage_completed_at.strftime('%Y-%m-%d %H:%M:%S') if partner.stage_completed_at else "",
                    partner.onboarding_stage
                ])

            for user in partners_no_team:
                csv_writer.writerow([
                    "Партнер без команды",
                    user.full_name,
                    user.username or "",
                    user.telegram_id,
                    "",
                    user.stage_payment_ok_at.strftime('%Y-%m-%d %H:%M:%S') if user.stage_payment_ok_at else "",
                    user.onboarding_stage
                ])

            csv_data = csv_buffer.getvalue().encode('utf-8-sig')
            csv_file = BufferedInputFile(
                csv_data,
                filename="full_report.csv"
            )

            await callback.message.answer_document(
                document=csv_file,
                caption="📊 CSV отчет за всё время"
            )

            logger.info(f"All-time report sent to admin {callback.from_user.id}")

    except Exception as e:
        logger.error(f"Error generating all-time report: {e}", exc_info=True)
        await status_msg.edit_text(
            f"❌ Ошибка при генерации отчета:\n{str(e)}"
        )
    finally:
        await state.clear()


@router.message(Command("segments"))
async def cmd_segments(message: types.Message):
    """
    Команда /segments - показать статистику по сегментам
    """
    if not is_admin(message.from_user.id):
        await message.answer("У вас нет доступа к этой команде.")
        return

    logger.info(f"Admin {message.from_user.id} requested segments stats")

    try:
        async with AsyncSessionLocal() as session:
            # Получаем количество пользователей в каждом сегменте
            new_leads_count = await UserSegmentCRUD.get_segment_count(session, "new_leads")
            buyers_count = await UserSegmentCRUD.get_segment_count(session, "buyers")
            partners_count = await UserSegmentCRUD.get_segment_count(session, "partners")
            partners_no_team_count = await UserSegmentCRUD.get_segment_count(session, "partners_without_team")

            report = f"""
📊 <b>СТАТИСТИКА ПО СЕГМЕНТАМ</b>

━━━━━━━━━━━━━━━━━━━━━━

🆕 <b>Новые лиды</b>
Пользователи, которые не оплатили
Количество: {new_leads_count}

━━━━━━━━━━━━━━━━━━━━━━

💳 <b>Покупатели</b>
Все, кто совершил покупку
Количество: {buyers_count}

━━━━━━━━━━━━━━━━━━━━━━

🤝 <b>Партнеры</b>
Завершили онбординг полностью
Количество: {partners_count}

━━━━━━━━━━━━━━━━━━━━━━

⚠️ <b>Партнеры без команды</b>
Купили, но не нажали "Команда"
Количество: {partners_no_team_count}

━━━━━━━━━━━━━━━━━━━━━━

💡 Используйте /broadcast для рассылки по сегментам
"""

            await message.answer(report, parse_mode="HTML")

    except Exception as e:
        logger.error(f"Error getting segments stats: {e}", exc_info=True)
        await message.answer(f"❌ Ошибка: {str(e)}")
