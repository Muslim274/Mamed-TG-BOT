"""
Простой хендлер для удаления пользователей через бота (только для админов)
С КАСКАДНЫМ УДАЛЕНИЕМ связанных записей
"""
import logging
from aiogram import Router, types, F
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from sqlalchemy import text
from aiogram.filters import Command

from app.database.connection import AsyncSessionLocal
from app.config import settings, is_admin  # Импортируем функцию is_admin

logger = logging.getLogger(__name__)

router = Router()

class DeleteUserStates(StatesGroup):
    waiting_for_telegram_id = State()

# Создаем фильтр для проверки админов
def admin_filter():
    """Создает фильтр для проверки множественных админов"""
    admin_ids = settings.admin_ids_list
    return F.from_user.id.in_(admin_ids)

@router.message(Command("clean_db_user"), admin_filter())
async def initiate_user_deletion(message: types.Message, state: FSMContext):
    """Инициация процесса удаления пользователя (только для админов)"""
    
    # Дополнительная проверка через функцию
    if not is_admin(message.from_user.id):
        await message.answer("❌ У вас нет прав для выполнения этой команды")
        return
    
    text = f"""
🗑️ <b>Удаление пользователя из базы данных</b>

🆔 <b>Введите Telegram ID пользователя для удаления:</b>
<i>Например: 8181794729</i>

"""
    
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="❌ Отмена",
                    callback_data="delete_user_cancel"
                )
            ]
        ]
    )
    
    await message.answer(text, parse_mode="HTML", reply_markup=keyboard)
    await state.set_state(DeleteUserStates.waiting_for_telegram_id)

@router.callback_query(F.data == "delete_user_cancel")
async def delete_user_cancel(callback: types.CallbackQuery, state: FSMContext):
    """Отмена удаления пользователя"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Нет доступа", show_alert=True)
        return
    
    await callback.message.edit_text("❌ Удаление пользователя отменено")
    await state.clear()
    await callback.answer()

@router.message(DeleteUserStates.waiting_for_telegram_id)
async def process_telegram_id(message: types.Message, state: FSMContext):
    """Проверка пользователя перед удалением"""
    
    # Проверяем, что команду отправил админ
    if not is_admin(message.from_user.id):
        await message.answer("❌ У вас нет прав для выполнения этой команды")
        await state.clear()
        return
    
    # Проверяем, что ID является числом
    try:
        telegram_id = int(message.text.strip())
    except ValueError:
        await message.answer("❌ Введите числовой ID")
        return
    

    
    try:
        async with AsyncSessionLocal() as session:
            # Получаем полную информацию о пользователе и связанных данных
            user_query = text("""
                SELECT u.id, u.telegram_id, u.username, u.full_name, u.ref_code,
                       u.created_at, u.onboarding_stage,
                       COUNT(DISTINCT p.id) as payments_count,
                       COUNT(DISTINCT s.id) as sales_count,
                       COUNT(DISTINCT c.id) as clicks_count
                FROM users u
                LEFT JOIN payments p ON u.id = p.user_id
                LEFT JOIN sales s ON u.ref_code = s.ref_code
                LEFT JOIN clicks c ON u.ref_code = c.ref_code
                WHERE u.telegram_id = :telegram_id
                GROUP BY u.id, u.telegram_id, u.username, u.full_name, u.ref_code, u.created_at, u.onboarding_stage
            """)
            
            result = await session.execute(user_query, {"telegram_id": telegram_id})
            user_data = result.fetchone()
            
            if not user_data:
                await message.answer(f"❌ Пользователь с ID {telegram_id} не найден в базе данных")
                await state.clear()
                return
            
            # Показываем подробную информацию и подтверждение удаления
            confirmation_text = f"""
⚠️ <b>ПОДТВЕРЖДЕНИЕ ПОЛНОГО УДАЛЕНИЯ</b>

👤 <b>Пользователь:</b> {user_data.full_name or 'Без имени'}
🆔 <b>ID:</b> <code>{telegram_id}</code>
🏷️ <b>Username:</b> @{user_data.username or 'отсутствует'}
🔗 <b>Ref код:</b> <code>{user_data.ref_code}</code>
📅 <b>Регистрация:</b> {user_data.created_at.strftime('%d.%m.%Y %H:%M') if user_data.created_at else 'Неизвестно'}
🎯 <b>Стадия:</b> {user_data.onboarding_stage}

📊 <b>СВЯЗАННЫЕ ДАННЫЕ (будут удалены):</b>

💸 Продаж: {user_data.sales_count}


<b>⚠️ ЭТО ДЕЙСТВИЕ НЕЛЬЗЯ ОТМЕНИТЬ!</b>
Все данные пользователя будут удалены навсегда.
"""
            
            keyboard = InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        InlineKeyboardButton(
                            text="🗑️ ДА, УДАЛИТЬ ПОЛНОСТЬЮ",
                            callback_data=f"confirm_delete:{telegram_id}"
                        )
                    ],
                    [
                        InlineKeyboardButton(
                            text="❌ Отмена",
                            callback_data="delete_user_cancel"
                        )
                    ]
                ]
            )
            
            await message.answer(confirmation_text, parse_mode="HTML", reply_markup=keyboard)
            
    except Exception as e:
        logger.error(f"❌ Error checking user {telegram_id}: {e}")
        await message.answer(f"❌ Ошибка при проверке пользователя: {e}")
        await state.clear()

@router.callback_query(F.data.startswith("confirm_delete:"))
async def confirm_delete_user(callback: types.CallbackQuery, state: FSMContext):
    """КАСКАДНОЕ УДАЛЕНИЕ пользователя и всех связанных данных"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Нет доступа", show_alert=True)
        return
    
    try:
        telegram_id = int(callback.data.split(":")[1])
    except (ValueError, IndexError):
        await callback.answer("❌ Ошибка обработки данных", show_alert=True)
        return
    

    
    try:
        async with AsyncSessionLocal() as session:
            # Получаем данные пользователя перед удалением
            user_query = text("""
                SELECT u.id, u.telegram_id, u.username, u.full_name, u.ref_code,
                       COUNT(DISTINCT p.id) as payments_count,
                       COUNT(DISTINCT s.id) as sales_count,
                       COUNT(DISTINCT c.id) as clicks_count
                FROM users u
                LEFT JOIN payments p ON u.id = p.user_id
                LEFT JOIN sales s ON u.ref_code = s.ref_code
                LEFT JOIN clicks c ON u.ref_code = c.ref_code
                WHERE u.telegram_id = :telegram_id
                GROUP BY u.id, u.telegram_id, u.username, u.full_name, u.ref_code
            """)
            
            result = await session.execute(user_query, {"telegram_id": telegram_id})
            user_data = result.fetchone()
            
            if not user_data:
                await callback.message.edit_text(f"❌ Пользователь с ID {telegram_id} не найден в базе данных")
                await callback.answer()
                await state.clear()
                return
            
            user_id = user_data.id
            ref_code = user_data.ref_code
            
            # КАСКАДНОЕ УДАЛЕНИЕ в правильном порядке
            
            # 1. Удаляем платежи (ссылаются на user_id)
            payments_deleted = await session.execute(
                text("DELETE FROM payments WHERE user_id = :user_id"),
                {"user_id": user_id}
            )
            payments_count = payments_deleted.rowcount
            
            # 2. Удаляем продажи (ссылаются на ref_code)
            sales_deleted = await session.execute(
                text("DELETE FROM sales WHERE ref_code = :ref_code"),
                {"ref_code": ref_code}
            )
            sales_count = sales_deleted.rowcount
            
            # 3. Удаляем клики (ссылаются на ref_code)
            clicks_deleted = await session.execute(
                text("DELETE FROM clicks WHERE ref_code = :ref_code"),
                {"ref_code": ref_code}
            )
            clicks_count = clicks_deleted.rowcount
            
            # 4. Удаляем тикеты поддержки (если есть таблица tickets)
            try:
                tickets_deleted = await session.execute(
                    text("DELETE FROM tickets WHERE user_id = :user_id"),
                    {"user_id": user_id}
                )
                tickets_count = tickets_deleted.rowcount
            except Exception:
                tickets_count = 0  # Таблица может не существовать
                
            # 5. УДАЛЯЕМ automated_messages 
            try:
                automated_deleted = await session.execute(
                    text("DELETE FROM automated_messages WHERE user_id = :user_id"),
                    {"user_id": user_id}
                )
                automated_count = automated_deleted.rowcount
            except Exception:
                automated_count = 0    
            
            # 6. Наконец удаляем самого пользователя
            user_deleted = await session.execute(
                text("DELETE FROM users WHERE telegram_id = :telegram_id"),
                {"telegram_id": telegram_id}
            )
            
            # Коммитим все изменения
            await session.commit()
            
            # Подтверждение полного удаления
            success_text = f"""
✅ <b>ПОЛЬЗОВАТЕЛЬ ПОЛНОСТЬЮ УДАЛЕН</b>

🗑️ <b>Удален:</b> {user_data.full_name or 'Без имени'}
🆔 <b>ID:</b> <code>{telegram_id}</code>
🏷️ <b>Username:</b> @{user_data.username or 'отсутствует'}
🔗 <b>Ref код:</b> <code>{ref_code}</code>

📊 <b>УДАЛЕНО ЗАПИСЕЙ:</b>

💸 Продаж: {sales_count}


👤 <b>Удалил:</b> {callback.from_user.full_name}
⏰ <b>Время:</b> {callback.message.date.strftime('%d.%m.%Y %H:%M')}

<i>✅ Все данные пользователя успешно удалены из базы данных</i>
"""
            
            await callback.message.edit_text(success_text, parse_mode="HTML")
            await callback.answer("✅ Пользователь и все связанные данные удалены!")
            
            logger.info(f"✅ User {telegram_id} ({user_data.full_name}) and all related data completely deleted by admin {callback.from_user.id}")
            logger.info(f"   Deleted: {payments_count} payments, {sales_count} sales, {clicks_count} clicks, {tickets_count} tickets")
            
    except Exception as e:
        logger.error(f"❌ Error deleting user {telegram_id}: {e}")
        await callback.answer("❌ Ошибка при удалении пользователя", show_alert=True)
        
        # Показываем детальную ошибку админу
        error_text = f"""
❌ <b>Ошибка удаления пользователя</b>

🆔 <b>ID:</b> <code>{telegram_id}</code>
⚠️ <b>Ошибка:</b> {str(e)[:500]}

Обратитесь к разработчику для решения проблемы.
"""
        await callback.message.edit_text(error_text, parse_mode="HTML")
    
    finally:
        await state.clear()