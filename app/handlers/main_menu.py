"""
Главное меню с рабочей функциональностью
"""
import logging
from aiogram import Router, types, F
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from app.database.connection import AsyncSessionLocal
from app.database.crud import UserCRUD, ClickCRUD, SaleCRUD
from app.config import settings

logger = logging.getLogger(__name__)
router = Router()

async def get_main_menu_keyboard(user_id: int):
    """Создание inline клавиатуры главного меню с учетом пола"""
    
    # Получаем ссылку на поддержку в зависимости от пола
    try:
        async with AsyncSessionLocal() as session:
            user = await UserCRUD.get_user_by_telegram_id(session, user_id)
            
            if user and user.gender == 'female':
                support_url = "https://t.me/adm_zarina53"
                community_url = "https://t.me/+0yVptIjnW2djOWVi"
            else:  # male или None
                support_url = "https://t.me/adm_mhmd"
                community_url = "https://t.me/+0yVptIjnW2djOWVi"
    except Exception as e:
        logger.error(f"Error getting user gender: {e}")
        # fallback
        support_url = "https://t.me/adm_mhmd"
        community_url = "https://t.me/+E7X89QWwePllZTdi"
    
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="💰 Моя ссылка",
                    callback_data="main_referral"
                ),
                InlineKeyboardButton(
                    text="💵 Доходы", 
                    callback_data="main_stats"
                )
            ],
            [
                InlineKeyboardButton(
                    text="💸 Вывод средств",
                    callback_data="main_withdrawal"
                ),
                InlineKeyboardButton(
                    text="👨‍💼 Поддержка",
                    callback_data="ask_question_help"
                )
            ]
        ]
    )

@router.callback_query(F.data == "show_main_menu")
async def show_main_menu(callback: types.CallbackQuery):
    """Показ главного меню"""
    logger.info(f"User {callback.from_user.id} opened main menu")
    
    menu_text = f"""
🎛️ <b>Главное меню</b>

Привет, {callback.from_user.full_name}!

Выберите нужный раздел:
"""
    
    try:
        keyboard = await get_main_menu_keyboard(callback.from_user.id)
        await callback.message.edit_text(
            menu_text,
            parse_mode="HTML",
            reply_markup=keyboard
        )
    except:
        keyboard = await get_main_menu_keyboard(callback.from_user.id)
        await callback.message.answer(
            menu_text,
            parse_mode="HTML",
            reply_markup=keyboard
        )
    
    await callback.answer()

@router.callback_query(F.data == "main_referral")
async def main_referral_handler(callback: types.CallbackQuery):
    """Реферальная ссылка"""
    try:
        async with AsyncSessionLocal() as session:
            user = await UserCRUD.get_user_by_telegram_id(session, callback.from_user.id)
            
            if not user:
                await callback.answer("❌ Пользователь не найден", show_alert=True)
                return
            
            referral_link = f"https://t.me/{settings.BOT_USERNAME}?start={user.ref_code}"
            
            text = f"""
🔗 <b>Ваша реферальная ссылка</b>

<code>{referral_link}</code>

<i>*⬆️ нажми прямо на неё, чтобы скопировать ⬆️*</i>

"""
            
            keyboard = InlineKeyboardMarkup(
                inline_keyboard=[

                    [
                        InlineKeyboardButton(
                            text="🔙 Назад в меню",
                            callback_data="show_main_menu"
                        )
                    ]
                ]
            )
            
            await callback.message.edit_text(text, parse_mode="HTML", reply_markup=keyboard)
            await callback.answer()
        
    except Exception as e:
        logger.error(f"Error in referral handler: {e}")
        await callback.answer("❌ Ошибка загрузки реферальной ссылки", show_alert=True)

@router.callback_query(F.data == "main_stats") 
async def main_stats_handler(callback: types.CallbackQuery):
    """ИСПРАВЛЕННАЯ статистика с реальным балансом"""
    try:
        async with AsyncSessionLocal() as session:
            user = await UserCRUD.get_user_by_telegram_id(session, callback.from_user.id)
            
            if not user:
                await callback.answer("❌ Пользователь не найден", show_alert=True)
                return
            
            logger.info(f"📊 Getting stats for user {user.ref_code}")
            
            # Получаем продажи и общую комиссию
            try:
                # Считаем подтвержденные продажи
                sales_count = await SaleCRUD.count_confirmed_sales(session, user.ref_code)
                
                # Считаем общую комиссию из подтвержденных продаж
                total_commission = await SaleCRUD.get_total_commission(session, user.ref_code)
                
                logger.info(f"📊 User {user.ref_code}: {sales_count} sales, total commission: {total_commission}")
                
            except Exception as e:
                logger.error(f"Error getting sales data: {e}")
                sales_count = 0
                total_commission = 0.0
            
            # Форматируем сумму: 7800.0 -> "7 800 руб."
            formatted_balance = f"{total_commission:,.0f} руб.".replace(",", " ")
            
            text = f"""
💵 <b>Доходы</b>

💰 Мой баланс: {formatted_balance}

"""
            
            keyboard = InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        InlineKeyboardButton(
                            text="💸 Вывести средства",
                            callback_data="main_withdrawal"
                        )
                    ],
                    [
                        InlineKeyboardButton(
                            text="🔙 Назад в меню",
                            callback_data="show_main_menu"
                        )
                    ]
                ]
            )
            
            await callback.message.edit_text(text, parse_mode="HTML", reply_markup=keyboard)
            await callback.answer()
        
    except Exception as e:
        logger.error(f"Error in stats handler: {e}", exc_info=True)
        await callback.answer("❌ Ошибка загрузки статистики", show_alert=True)

@router.callback_query(F.data.startswith("main_"))
async def main_menu_placeholder(callback: types.CallbackQuery):
   """Заглушки для других пунктов меню"""
   action = callback.data.replace("main_", "")
   
   if action == "materials":
       text = """
📚 <b>Рекламные материалы</b>
🖼️ <b>Доступные материалы:</b>
- Баннеры для социальных сетей
- Тексты для постов
- Видео презентации
- Email шаблоны
🔧 <i>Раздел находится в разработке</i>
Обратитесь в поддержку для получения материалов.
"""
   elif action == "withdrawal":
       try:
           async with AsyncSessionLocal() as session:
               user = await UserCRUD.get_user_by_telegram_id(
                   session, callback.from_user.id
               )
               if not user:
                   formatted_balance = f"0.00 {settings.CURRENCY}"
               else:
                   total_commission = await SaleCRUD.get_total_commission(
                       session, user.ref_code
                   ) or 0.0
                   formatted_balance = (
                       f"{total_commission:,.0f} {settings.CURRENCY}".replace(",", " ")
                   )
       except Exception as e:
           logger.error(f"Error fetching balance: {e}", exc_info=True)
           formatted_balance = f"0.00 {settings.CURRENCY}"        
       
       text = f"""
💸 <b>Вывод средств</b>
💰 <b>Ваш баланс:</b> {formatted_balance}

Для вывода средств обратитесь в поддержку.
"""
   else:
       text = f"🔧 {action} - в разработке"
   
   # Получаем ссылку на поддержку в зависимости от пола
   try:
       async with AsyncSessionLocal() as session:
           user = await UserCRUD.get_user_by_telegram_id(session, callback.from_user.id)
           
           if user and user.gender == 'female':
               support_url = "https://t.me/adm_zarina53"
           else:
               support_url = "https://t.me/adm_mhmd"
   except:
       support_url = "https://t.me/adm_mhmd"
   
   keyboard = InlineKeyboardMarkup(
       inline_keyboard=[
           [
               InlineKeyboardButton(
                   text="👨‍💼 Поддержка",
                   callback_data="ask_question_help"
               )
           ],
           [
               InlineKeyboardButton(
                   text="🔙 Назад в меню",
                   callback_data="show_main_menu"
               )
           ]
       ]
   )
   
   try:
       await callback.message.edit_text(text, parse_mode="HTML", reply_markup=keyboard)
   except:
       await callback.message.answer(text, parse_mode="HTML", reply_markup=keyboard)
   
   await callback.answer()
   
   
def register_main_menu_handlers(dp):
    """Регистрация хендлеров главного меню"""
    dp.include_router(router)