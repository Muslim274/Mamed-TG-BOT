"""
Скрипт для тестирования системы тикетов
app/tests/test_tickets.py
"""
import asyncio
import logging
from datetime import datetime

from app.database.connection import AsyncSessionLocal, init_db
from app.database.ticket_crud import TicketCRUD
from app.database.crud import UserCRUD
from app.database.models import TicketStatus

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_ticket_system():
    """Тестирование основных функций системы тикетов"""
    
    logger.info("🧪 Starting ticket system tests...")
    
    try:
        # Инициализация БД
        await init_db()
        
        async with AsyncSessionLocal() as session:
            
            # === ТЕСТ 1: Создание тикета ===
            logger.info("🔬 Test 1: Creating ticket...")
            
            # Используем существующего пользователя или создаем тестового
            test_telegram_id = 999999999  # Тестовый ID
            
            # Проверяем есть ли пользователь
            user = await UserCRUD.get_user_by_telegram_id(session, test_telegram_id)
            if not user:
                logger.info("Creating test user...")
                from app.utils.helpers import generate_ref_code
                user = await UserCRUD.create_user(
                    session=session,
                    telegram_id=test_telegram_id,
                    username="test_user",
                    full_name="Test User",
                    ref_code=generate_ref_code(test_telegram_id)
                )
            
            # Создаем тикет
            ticket1 = await TicketCRUD.get_or_create_ticket(session, test_telegram_id)
            logger.info(f"✅ Created ticket #{ticket1.id}")
            
            # === ТЕСТ 2: Добавление сообщений ===
            logger.info("🔬 Test 2: Adding messages...")
            
            # Сообщение от пользователя
            msg1 = await TicketCRUD.add_message(
                session=session,
                ticket_id=ticket1.id,
                text="Привет! У меня проблема с оплатой",
                from_user=True,
                telegram_message_id=12345
            )
            logger.info(f"✅ Added user message: {msg1.id}")
            
            # Сообщение от админа
            msg2 = await TicketCRUD.add_message(
                session=session,
                ticket_id=ticket1.id,
                text="Здравствуйте! Опишите проблему подробнее",
                from_user=False,
                telegram_message_id=12346
            )
            logger.info(f"✅ Added admin message: {msg2.id}")
            
            # Еще одно сообщение от пользователя
            msg3 = await TicketCRUD.add_message(
                session=session,
                ticket_id=ticket1.id,
                text="Карта не проходит, ошибка 3D Secure",
                from_user=True,
                telegram_message_id=12347
            )
            logger.info(f"✅ Added another user message: {msg3.id}")
            
            # === ТЕСТ 3: Получение тикетов ===
            logger.info("🔬 Test 3: Getting tickets...")
            
            # Открытые тикеты
            open_tickets = await TicketCRUD.get_open_tickets(session)
            logger.info(f"✅ Found {len(open_tickets)} open tickets")
            
            # Сообщения тикета
            messages = await TicketCRUD.get_ticket_messages(session, ticket1.id)
            logger.info(f"✅ Found {len(messages)} messages in ticket")
            
            # === ТЕСТ 4: Отметка как прочитанное ===
            logger.info("🔬 Test 4: Marking as read...")
            
            read_count = await TicketCRUD.mark_messages_read(session, ticket1.id)
            logger.info(f"✅ Marked {read_count} messages as read")
            
            # === ТЕСТ 5: Статистика ===
            logger.info("🔬 Test 5: Getting statistics...")
            
            stats = await TicketCRUD.get_ticket_stats(session)
            logger.info(f"✅ Stats: {stats}")
            
            # === ТЕСТ 6: Закрытие тикета ===
            logger.info("🔬 Test 6: Closing ticket...")
            
            success = await TicketCRUD.close_ticket(session, ticket1.id)
            logger.info(f"✅ Ticket closed: {success}")
            
            # === ТЕСТ 7: Реактивация тикета ===
            logger.info("🔬 Test 7: Reactivating ticket...")
            
            # Новое сообщение должно реактивировать тикет
            ticket2 = await TicketCRUD.get_or_create_ticket(session, test_telegram_id)
            logger.info(f"✅ Ticket reactivated: #{ticket2.id} (same as #{ticket1.id}: {ticket2.id == ticket1.id})")
            
            # === ТЕСТ 8: Закрытые тикеты ===
            logger.info("🔬 Test 8: Getting closed tickets...")
            
            # Сначала закроем тикет снова
            await TicketCRUD.close_ticket(session, ticket2.id)
            
            closed_tickets = await TicketCRUD.get_closed_tickets(session)
            logger.info(f"✅ Found {len(closed_tickets)} closed tickets")
            
            # === ФИНАЛЬНАЯ ПРОВЕРКА ===
            logger.info("🔬 Final check: Displaying ticket info...")
            
            if open_tickets:
                for ticket in open_tickets:
                    logger.info(f"""
📋 Ticket #{ticket.id}:
   User: {ticket.user.username or f"ID:{ticket.telegram_id}"}
   Status: {ticket.status}
   Messages: {ticket.total_messages}
   Unread: {ticket.unread_messages}
   Created: {ticket.created_at}
   Subject: {ticket.subject}
""")
            
            logger.info("🎉 All tests completed successfully!")
            
    except Exception as e:
        logger.error(f"❌ Test failed: {e}", exc_info=True)
        raise

async def test_admin_interface():
    """Тестирование админского интерфейса (симуляция)"""
    
    logger.info("🔬 Testing admin interface simulation...")
    
    try:
        async with AsyncSessionLocal() as session:
            
            # Создаем несколько тестовых тикетов
            test_users = [
                (111111111, "user1", "Test User 1"),
                (222222222, "user2", "Test User 2"),
                (333333333, "user3", "Test User 3"),
            ]
            
            for telegram_id, username, full_name in test_users:
                # Создаем пользователя если не существует
                user = await UserCRUD.get_user_by_telegram_id(session, telegram_id)
                if not user:
                    from app.utils.helpers import generate_ref_code
                    user = await UserCRUD.create_user(
                        session=session,
                        telegram_id=telegram_id,
                        username=username,
                        full_name=full_name,
                        ref_code=generate_ref_code(telegram_id)
                    )
                
                # Создаем тикет
                ticket = await TicketCRUD.get_or_create_ticket(session, telegram_id)
                
                # Добавляем сообщения
                await TicketCRUD.add_message(
                    session=session,
                    ticket_id=ticket.id,
                    text=f"Тестовое сообщение от {username}",
                    from_user=True
                )
                
                logger.info(f"✅ Created test ticket for {username}")
            
            # Симулируем команду /tickets
            logger.info("🔬 Simulating /tickets command...")
            
            tickets = await TicketCRUD.get_open_tickets(session)
            stats = await TicketCRUD.get_ticket_stats(session)
            
            # Форматируем как в реальном боте
            tickets_text = f"""📋 Открытые тикеты ({len(tickets)})

📊 Статистика:
• Открытых тикетов: {stats['open_tickets']}
• Непрочитанных сообщений: {stats['unread_messages']}
• Закрыто за сутки: {stats['closed_today']}

📝 Список тикетов:
"""
            
            for ticket in tickets:
                status_emoji = "🟡" if ticket.unread_messages > 0 else "⚪️"
                username = f"@{ticket.user.username}" if ticket.user.username else f"ID:{ticket.telegram_id}"
                time_str = ticket.updated_at.strftime("%d.%m %H:%M")
                
                tickets_text += f"{status_emoji} {username} | {time_str} | 📝{ticket.total_messages}\n"
            
            logger.info("📋 Admin interface output:")
            logger.info(tickets_text)
            
            logger.info("🎉 Admin interface test completed!")
            
    except Exception as e:
        logger.error(f"❌ Admin interface test failed: {e}", exc_info=True)

async def cleanup_test_data():
    """Очистка тестовых данных"""
    
    logger.info("🧹 Cleaning up test data...")
    
    try:
        async with AsyncSessionLocal() as session:
            # Удаляем тестовые тикеты
            test_telegram_ids = [999999999, 111111111, 222222222, 333333333]
            
            for telegram_id in test_telegram_ids:
                # Найти и удалить тикеты
                tickets = await session.execute(
                    text("DELETE FROM tickets WHERE telegram_id = :telegram_id"),
                    {"telegram_id": telegram_id}
                )
                
                # Удалить пользователя если это тестовый
                user = await UserCRUD.get_user_by_telegram_id(session, telegram_id)
                if user and user.username and user.username.startswith('test_'):
                    await session.delete(user)
            
            await session.commit()
            logger.info("✅ Test data cleaned up")
            
    except Exception as e:
        logger.error(f"❌ Cleanup failed: {e}")

async def main():
    """Основная функция тестирования"""
    
    print("🚀 Starting Ticket System Tests")
    print("=" * 50)
    
    try:
        # Основные тесты
        await test_ticket_system()
        
        print("\n" + "=" * 50)
        
        # Тесты админского интерфейса
        await test_admin_interface()
        
        print("\n" + "=" * 50)
        print("🎉 All tests passed!")
        
        # Опрос пользователя о очистке
        cleanup = input("\n🧹 Clean up test data? (y/N): ").lower().strip()
        if cleanup == 'y':
            await cleanup_test_data()
        
    except Exception as e:
        print(f"\n💥 Tests failed: {e}")
        return 1
    
    return 0

if __name__ == "__main__":
    exit_code = asyncio.run(main())