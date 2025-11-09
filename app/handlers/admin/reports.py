"""
Обработчики для админских отчетов
"""
import csv
import io
import logging
from datetime import datetime, timedelta
from aiogram import Router, types, F
from aiogram.filters import Command
from aiogram.types import BufferedInputFile

from app.config import settings
from app.database.connection import AsyncSessionLocal
from app.database.statistics_crud import StatisticsCRUD, UserSegmentCRUD

logger = logging.getLogger(__name__)

router = Router()


def is_admin(user_id: int) -> bool:
    """Проверка, является ли пользователь администратором"""
    return user_id in settings.admin_ids_list


@router.message(Command("get_info"))
async def cmd_get_info(message: types.Message):
    """
    Команда /get_info - ежедневный отчет для администратора
    """
    if not is_admin(message.from_user.id):
        await message.answer("У вас нет доступа к этой команде.")
        return

    logger.info(f"Admin {message.from_user.id} requested daily report")

    # Отправляем сообщение о начале генерации отчета
    status_msg = await message.answer("Генерирую отчет...")

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

            # Отправляем текстовый отчет
            await status_msg.edit_text(report_text, parse_mode="HTML")

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

            await message.answer_document(
                document=csv_file,
                caption=f"📊 CSV отчет за {today.strftime('%d.%m.%Y')}"
            )

            logger.info(f"Daily report sent to admin {message.from_user.id}")

    except Exception as e:
        logger.error(f"Error generating daily report: {e}", exc_info=True)
        await status_msg.edit_text(
            f"❌ Ошибка при генерации отчета:\n{str(e)}"
        )


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
