"""
Планировщик для автоматической ежедневной отправки отчетов администратору
"""
import asyncio
import csv
import io
import logging
from datetime import datetime, timedelta, time as dt_time
from aiogram import Bot
from aiogram.types import BufferedInputFile

from app.config import settings
from app.database.connection import AsyncSessionLocal
from app.database.statistics_crud import StatisticsCRUD

logger = logging.getLogger(__name__)


class DailyReportsScheduler:
    """Планировщик для ежедневных отчетов"""

    def __init__(self, bot: Bot, send_time: dt_time = None):
        """
        Args:
            bot: Экземпляр бота
            send_time: Время отправки отчета (по умолчанию 09:00)
        """
        self.bot = bot
        self.send_time = send_time or dt_time(9, 0)  # 09:00 по умолчанию
        self.is_running = False
        self.task = None

    async def generate_and_send_report(self, admin_id: int, date: datetime = None):
        """
        Генерирует и отправляет отчет администратору

        Args:
            admin_id: ID администратора
            date: Дата для отчета (по умолчанию вчера)
        """
        if date is None:
            # По умолчанию отчет за вчерашний день
            date = datetime.now() - timedelta(days=1)

        logger.info(f"Generating daily report for {date.strftime('%d.%m.%Y')}")

        try:
            async with AsyncSessionLocal() as session:
                # Получаем данные за день
                sales_data = await StatisticsCRUD.get_daily_sales(session, date)
                buyers = await StatisticsCRUD.get_daily_buyers(session, date)
                new_leads = await StatisticsCRUD.get_new_leads(session, date)
                new_partners = await StatisticsCRUD.get_new_partners(session, date)
                partners_no_team = await StatisticsCRUD.get_partners_without_team(session, date)

            # Формируем текстовый отчет
            report_text = f"""
📊 <b>АВТОМАТИЧЕСКИЙ ЕЖЕДНЕВНЫЙ ОТЧЕТ</b>
📅 Дата: {date.strftime('%d.%m.%Y')}

━━━━━━━━━━━━━━━━━━━━━━

💰 <b>ПРОДАЖИ ЗА ДЕНЬ</b>
• Количество: {sales_data['count']}
• Сумма: {sales_data['total_amount']:,.0f} руб.
• Комиссия: {sales_data['total_commission']:,.0f} руб.

━━━━━━━━━━━━━━━━━━━━━━

👥 <b>ПОКУПАТЕЛИ ({len(buyers)})</b>
"""
            if buyers:
                for buyer in buyers[:10]:  # Первые 10
                    username = f"@{buyer['username']}" if buyer['username'] else "Нет username"
                    time_str = buyer['purchased_at'].strftime('%H:%M')
                    report_text += f"\n• {buyer['full_name']} ({username})\n"
                    report_text += f"  Сумма: {buyer['amount']:,.0f} руб., {time_str}\n"
                if len(buyers) > 10:
                    report_text += f"\n... и еще {len(buyers) - 10} покупателей\n"
            else:
                report_text += "\nНет покупателей за этот день\n"

            report_text += f"""
━━━━━━━━━━━━━━━━━━━━━━

🆕 <b>НОВЫЕ ЛИДЫ ({len(new_leads)})</b>
"""
            if new_leads:
                for lead in new_leads[:10]:  # Первые 10
                    username = f"@{lead.username}" if lead.username else "Нет username"
                    time_str = lead.created_at.strftime('%H:%M')
                    report_text += f"• {lead.full_name} ({username}), {time_str}\n"
                if len(new_leads) > 10:
                    report_text += f"\n... и еще {len(new_leads) - 10} лидов\n"
            else:
                report_text += "Нет новых лидов за этот день\n"

            report_text += f"""
━━━━━━━━━━━━━━━━━━━━━━

🤝 <b>НОВЫЕ ПАРТНЕРЫ ({len(new_partners)})</b>
"""
            if new_partners:
                for partner in new_partners[:10]:  # Первые 10
                    username = f"@{partner.username}" if partner.username else "Нет username"
                    time_str = partner.stage_completed_at.strftime('%H:%M') if partner.stage_completed_at else "N/A"
                    report_text += f"• {partner.full_name} ({username}), {time_str}\n"
                if len(new_partners) > 10:
                    report_text += f"\n... и еще {len(new_partners) - 10} партнеров\n"
            else:
                report_text += "Нет новых партнеров за этот день\n"

            report_text += f"""
━━━━━━━━━━━━━━━━━━━━━━

⚠️ <b>ПАРТНЕРЫ БЕЗ КОМАНДЫ ({len(partners_no_team)})</b>
"""
            if partners_no_team:
                for user in partners_no_team[:10]:  # Первые 10
                    username = f"@{user.username}" if user.username else "Нет username"
                    report_text += f"• {user.full_name} ({username})\n"
                    report_text += f"  Стадия: {user.onboarding_stage}\n"
                if len(partners_no_team) > 10:
                    report_text += f"\n... и еще {len(partners_no_team) - 10} пользователей\n"
            else:
                report_text += "Нет таких пользователей за этот день\n"

            # Отправляем текстовый отчет
            await self.bot.send_message(
                chat_id=admin_id,
                text=report_text,
                parse_mode="HTML"
            )

            # Генерируем и отправляем CSV файл
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
                filename=f"daily_report_{date.strftime('%Y%m%d')}.csv"
            )

            await self.bot.send_document(
                document=csv_file,
                chat_id=admin_id,
                caption=f"📊 CSV отчет за {date.strftime('%d.%m.%Y')}"
            )

            logger.info(f"Daily report sent successfully to admin {admin_id}")

        except Exception as e:
            logger.error(f"Error generating/sending daily report: {e}", exc_info=True)
            try:
                await self.bot.send_message(
                    chat_id=admin_id,
                    text=f"❌ Ошибка при генерации ежедневного отчета:\n{str(e)}"
                )
            except:
                pass

    async def _scheduler_loop(self):
        """Основной цикл планировщика"""
        logger.info(f"Daily reports scheduler started. Report time: {self.send_time}")

        while self.is_running:
            try:
                now = datetime.now()
                target_time = datetime.combine(now.date(), self.send_time)

                # Если уже прошло время отправки сегодня, планируем на завтра
                if now >= target_time:
                    target_time += timedelta(days=1)

                # Вычисляем время ожидания
                wait_seconds = (target_time - now).total_seconds()
                logger.info(f"Next report scheduled at {target_time.strftime('%d.%m.%Y %H:%M')}")

                # Ждем до времени отправки
                await asyncio.sleep(wait_seconds)

                # Отправляем отчеты всем администраторам
                for admin_id in settings.admin_ids_list:
                    try:
                        await self.generate_and_send_report(admin_id)
                        await asyncio.sleep(1)  # Небольшая задержка между отправками
                    except Exception as e:
                        logger.error(f"Error sending report to admin {admin_id}: {e}")

            except asyncio.CancelledError:
                logger.info("Scheduler loop cancelled")
                break
            except Exception as e:
                logger.error(f"Error in scheduler loop: {e}", exc_info=True)
                await asyncio.sleep(60)  # Подождать минуту перед повтором при ошибке

    async def start(self):
        """Запустить планировщик"""
        if self.is_running:
            logger.warning("Scheduler already running")
            return

        self.is_running = True
        self.task = asyncio.create_task(self._scheduler_loop())
        logger.info("Daily reports scheduler started")

    async def stop(self):
        """Остановить планировщик"""
        if not self.is_running:
            return

        self.is_running = False
        if self.task:
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                pass

        logger.info("Daily reports scheduler stopped")
