"""
Админское меню с функционалом обнуления баланса (упрощенная версия)
"""
import logging
from aiogram import Router, types, F
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from app.database.connection import AsyncSessionLocal
from app.database.crud import UserCRUD, SaleCRUD
from app.config import settings, is_admin  # Импортируем функцию is_admin
from aiogram.filters import Command

from sqlalchemy import text

logger = logging.getLogger(__name__)
router = Router()

class AdminStates(StatesGroup):
    waiting_for_user_id = State()
    waiting_for_partial_amount = State()

# Создаем фильтр для проверки админов
def admin_filter():
    """Создает фильтр для проверки множественных админов"""
    admin_ids = settings.admin_ids_list
    return F.from_user.id.in_(admin_ids)

@router.message(Command("reset_balance"), admin_filter())
async def reset_balance_command(message: types.Message, state: FSMContext):
    """Команда /reset_balance - сразу переходим к обнулению баланса"""
    if not is_admin(message.from_user.id):
        await message.answer("❌ У вас нет прав доступа к админ панели")
        return
    
    text = """
💸 <b>Обнуление баланса пользователя</b>

🆔 Введите Telegram ID пользователя для удаления:
Например: 8181794729
"""
    
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="❌ Отмена",
                    callback_data="admin_cancel"
                )
            ]
        ]
    )
    
    await message.answer(text, parse_mode="HTML", reply_markup=keyboard)
    await state.set_state(AdminStates.waiting_for_user_id)

@router.callback_query(F.data == "admin_cancel")
async def admin_cancel(callback: types.CallbackQuery, state: FSMContext):
    """Отмена операции"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Нет доступа", show_alert=True)
        return
    
    await callback.message.edit_text("❌ Операция отменена")
    await state.clear()
    await callback.answer()

@router.message(AdminStates.waiting_for_user_id)
async def process_user_id(message: types.Message, state: FSMContext):
    """Обработка введенного ID пользователя"""
    if not is_admin(message.from_user.id):
        await message.answer("❌ У вас нет прав для выполнения этой операции")
        await state.clear()
        return
        
    try:
        user_telegram_id = int(message.text.strip())
    except ValueError:
        await message.answer("❌ Неверный формат ID. Введите числовой ID:")
        return
    
    try:
        async with AsyncSessionLocal() as session:
            user = await UserCRUD.get_user_by_telegram_id(session, user_telegram_id)
            
            if not user:
                await message.answer(f"❌ Пользователь с ID {user_telegram_id} не найден")
                await state.clear()
                return
            
            # Получаем текущий баланс
            total_commission = await SaleCRUD.get_total_commission(session, user.ref_code) or 0.0
            formatted_balance = f"{total_commission:,.0f} руб.".replace(",", " ")
            
            # Сохраняем данные в state
            await state.update_data(
                target_user_id=user_telegram_id,
                target_ref_code=user.ref_code,
                current_balance=total_commission,
                username=user.username or "Без username",
                full_name=user.full_name
            )
        
        text = f"""
👤 <b>Информация о пользователе</b>

🆔 <b>Telegram ID:</b> <code>{user_telegram_id}</code>
👤 <b>Имя:</b> {user.full_name}
🏷️ <b>Username:</b> @{user.username or 'отсутствует'}
🔗 <b>Реф. код:</b> <code>{user.ref_code}</code>
💰 <b>Текущий баланс:</b> {formatted_balance}

Выберите действие:
"""
        
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="🗑️ Обнулить баланс",
                        callback_data="confirm_full_reset"
                    )
                ],
                [
                    InlineKeyboardButton(
                        text="📝 Частично обнулить",
                        callback_data="partial_reset"
                    )
                ],
                [
                    InlineKeyboardButton(
                        text="❌ Отмена",
                        callback_data="admin_cancel"
                    )
                ]
            ]
        )
        
        await message.answer(text, parse_mode="HTML", reply_markup=keyboard)
        
    except Exception as e:
        logger.error(f"❌ Error getting user info {user_telegram_id}: {e}")
        await message.answer(f"❌ Ошибка получения информации о пользователе: {e}")
        await state.clear()

@router.callback_query(F.data == "confirm_full_reset")
async def confirm_full_reset(callback: types.CallbackQuery, state: FSMContext):
    """Подтверждение полного обнуления баланса"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Нет доступа", show_alert=True)
        return
    
    data = await state.get_data()
    target_user_id = data.get('target_user_id')
    target_ref_code = data.get('target_ref_code')
    current_balance = data.get('current_balance', 0.0)
    full_name = data.get('full_name', 'Неизвестно')
    
    if not target_ref_code:
        await callback.answer("❌ Ошибка: данные пользователя не найдены", show_alert=True)
        await state.clear()
        return
    
    try:
        async with AsyncSessionLocal() as session:
            async with session.begin():
                # Сначала проверяем, есть ли продажи
                check_query = text("SELECT COUNT(*) as count FROM sales WHERE ref_code = :ref_code")
                result = await session.execute(check_query, {"ref_code": target_ref_code})
                sales_count = result.scalar()
                
                if sales_count == 0:
                    await callback.answer("⚠️ У пользователя нет продаж для удаления", show_alert=True)
                    await state.clear()
                    return
                
                # Удаляем все продажи
                delete_query = text("DELETE FROM sales WHERE ref_code = :ref_code")
                delete_result = await session.execute(delete_query, {"ref_code": target_ref_code})
                deleted_count = delete_result.rowcount
                
                logger.info(f"🗑️ Deleted {deleted_count} sales for user {target_user_id} (ref_code: {target_ref_code})")
        
        # Форматируем сумму
        formatted_balance = f"{current_balance:,.0f} руб.".replace(",", " ")
        
        success_text = f"""
✅ <b>Баланс успешно обнулен</b>

👤 <b>Пользователь:</b> {full_name}
🆔 <b>ID:</b> <code>{target_user_id}</code>
💰 <b>Обнулено:</b> {formatted_balance}
🗑️ <b>Удалено продаж:</b> {deleted_count}
👤 <b>Обнулил:</b> {callback.from_user.full_name}

<i>Все комиссии пользователя удалены из базы данных</i>
"""
        
        await callback.message.edit_text(success_text, parse_mode="HTML")
        await callback.answer("✅ Баланс обнулен!")
        
        logger.info(f"✅ Balance reset for user {target_user_id} by admin {callback.from_user.id}")
        
    except Exception as e:
        logger.error(f"❌ Error resetting balance for user {target_user_id}: {e}")
        await callback.answer("❌ Ошибка при обнулении баланса", show_alert=True)
        error_text = f"❌ Ошибка обнуления баланса: {str(e)}"
        await callback.message.edit_text(error_text)
    
    finally:
        await state.clear()

@router.callback_query(F.data == "partial_reset")
async def partial_reset_start(callback: types.CallbackQuery, state: FSMContext):
    """Начало частичного обнуления баланса"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Нет доступа", show_alert=True)
        return
    
    data = await state.get_data()
    current_balance = data.get('current_balance', 0.0)
    formatted_balance = f"{current_balance:,.0f} руб.".replace(",", " ")
    
    if current_balance <= 0:
        await callback.answer("⚠️ У пользователя нет баланса для частичного обнуления", show_alert=True)
        return
    
    text = f"""
📝 <b>Частичное обнуление баланса</b>

💰 <b>Текущий баланс:</b> {formatted_balance}

Введите ТОЧНУЮ сумму для списания:
<i>(например: 700 или 1500.50)</i>

⚠️ <b>Алгоритм списания:</b>
1. Сначала ищем продажи точно по сумме
2. Если не найдены - уменьшаем самую крупную продажу
3. Если сумма больше крупной продажи - комбинируем несколько продаж
"""
    
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="❌ Отмена",
                    callback_data="admin_cancel"
                )
            ]
        ]
    )
    
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=keyboard)
    await state.set_state(AdminStates.waiting_for_partial_amount)
    await callback.answer()

@router.message(AdminStates.waiting_for_partial_amount)
async def process_partial_amount(message: types.Message, state: FSMContext):
    """Обработка суммы для ТОЧНОГО частичного обнуления"""
    if not is_admin(message.from_user.id):
        await message.answer("❌ У вас нет прав для выполнения этой операции")
        await state.clear()
        return
    
    try:
        amount = float(message.text.strip())
        if amount <= 0:
            await message.answer("❌ Сумма должна быть больше 0")
            return
    except ValueError:
        await message.answer("❌ Неверный формат суммы. Введите число:")
        return
    
    data = await state.get_data()
    target_user_id = data.get('target_user_id')
    target_ref_code = data.get('target_ref_code')
    current_balance = data.get('current_balance', 0.0)
    full_name = data.get('full_name', 'Неизвестно')
    
    if amount > current_balance:
        await message.answer(
            f"❌ Сумма списания ({amount:,.0f} руб.) больше текущего баланса "
            f"({current_balance:,.0f} руб.)"
        )
        return
    
    try:
        async with AsyncSessionLocal() as session:
            async with session.begin():
                # Получаем ВСЕ продажи пользователя
                select_query = text("""
                    SELECT id, commission_amount FROM sales 
                    WHERE ref_code = :ref_code AND status = 'confirmed'
                    ORDER BY commission_amount DESC, created_at DESC
                """)
                result = await session.execute(select_query, {"ref_code": target_ref_code})
                sales = result.fetchall()
                
                if not sales:
                    await message.answer("❌ У пользователя нет подтвержденных продаж")
                    await state.clear()
                    return
                
                # АЛГОРИТМ ТОЧНОГО СПИСАНИЯ
                
                # 1. Сначала ищем точное совпадение по сумме
                exact_match = None
                for sale in sales:
                    if abs(sale.commission_amount - amount) < 0.01:  # Учитываем погрешность float
                        exact_match = sale
                        break
                
                if exact_match:
                    # Найдено точное совпадение - удаляем эту продажу
                    delete_query = text("DELETE FROM sales WHERE id = :sale_id")
                    await session.execute(delete_query, {"sale_id": exact_match.id})
                    
                    actual_deleted = amount
                    method = "Удалена продажа с точной суммой"
                    
                else:
                    # 2. Точного совпадения нет - ищем самую крупную продажу больше суммы
                    larger_sale = None
                    for sale in sales:
                        if sale.commission_amount > amount:
                            larger_sale = sale
                            break  # Берем первую (самую крупную из-за ORDER BY DESC)
                    
                    if larger_sale:
                        # Уменьшаем крупную продажу на нужную сумму
                        new_amount = larger_sale.commission_amount - amount
                        update_query = text("""
                            UPDATE sales 
                            SET commission_amount = :new_amount 
                            WHERE id = :sale_id
                        """)
                        await session.execute(update_query, {
                            "new_amount": new_amount,
                            "sale_id": larger_sale.id
                        })
                        
                        actual_deleted = amount
                        method = f"Уменьшена продажа с {larger_sale.commission_amount} до {new_amount}"
                        
                    else:
                        # 3. Нет продажи больше суммы - комбинируем несколько продаж
                        remaining_amount = amount
                        sales_to_delete = []
                        sales_to_update = []
                        
                        for sale in reversed(sales):  # Берем от меньших к большим
                            if remaining_amount <= 0:
                                break
                                
                            if sale.commission_amount <= remaining_amount:
                                # Удаляем полностью
                                sales_to_delete.append(sale.id)
                                remaining_amount -= sale.commission_amount
                            else:
                                # Частично уменьшаем
                                new_amount = sale.commission_amount - remaining_amount
                                sales_to_update.append((sale.id, new_amount))
                                remaining_amount = 0
                        
                        # Выполняем удаления
                        if sales_to_delete:
                            delete_query = text("DELETE FROM sales WHERE id = ANY(:ids)")
                            await session.execute(delete_query, {"ids": sales_to_delete})
                        
                        # Выполняем обновления
                        for sale_id, new_amount in sales_to_update:
                            update_query = text("""
                                UPDATE sales 
                                SET commission_amount = :new_amount 
                                WHERE id = :sale_id
                            """)
                            await session.execute(update_query, {
                                "new_amount": new_amount,
                                "sale_id": sale_id
                            })
                        
                        actual_deleted = amount - remaining_amount
                        method = f"Удалено {len(sales_to_delete)} продаж, изменено {len(sales_to_update)}"
        
        formatted_amount = f"{actual_deleted:,.0f} руб.".replace(",", " ")
        new_balance = current_balance - actual_deleted
        formatted_new_balance = f"{new_balance:,.0f} руб.".replace(",", " ")
        
        success_text = f"""
✅ <b>Баланс частично обнулен</b>

👤 <b>Пользователь:</b> {full_name}
🆔 <b>ID:</b> <code>{target_user_id}</code>
💸 <b>Списано:</b> {formatted_amount}
💰 <b>Новый баланс:</b> {formatted_new_balance}
🔧 <b>Метод:</b> {method}
👤 <b>Обнулил:</b> {message.from_user.full_name}
"""
        
        await message.answer(success_text, parse_mode="HTML")
        
        logger.info(f"✅ Exact partial balance reset for user {target_user_id}: -{actual_deleted} by admin {message.from_user.id}. Method: {method}")
        
    except Exception as e:
        logger.error(f"❌ Error partial resetting balance for user {target_user_id}: {e}")
        await message.answer(f"❌ Ошибка при частичном обнулении баланса: {str(e)}")
    
    finally:
        await state.clear()

def register_admin_handlers(dp):
    """Регистрация хендлеров админского меню"""
    dp.include_router(router)