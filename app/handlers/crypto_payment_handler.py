"""
Обработчики для оплаты криптовалютой
"""
import logging
import os
from datetime import datetime
from aiogram import Router, types, F
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, FSInputFile
from aiogram.fsm.context import FSMContext

from app.database.connection import AsyncSessionLocal
from app.database.crud import UserCRUD
from app.config import settings
from app.handlers.crypto_payment_states import CryptoPaymentStates

logger = logging.getLogger(__name__)

router = Router()

# Данные о криптовалютах
CRYPTO_DATA = {
    "usdt": {
        "name": "USDT (TRC-20)",
        "wallet": "TPRbhQ3EBj9yxwD7mHigULAC7UPDk286VE",
        "qr_path": "/root/telegram-referral-bot/qr-crypto/qr-usdt.jpg",
        "emoji": "💵"
    },
    "btc": {
        "name": "Bitcoin (BTC)",
        "wallet": "bc1qk2u2cazxuelnlqqxef8ef96222sehnr0cyuvsv",
        "qr_path": "/root/telegram-referral-bot/qr-crypto/qr-b.jpg",
        "emoji": "₿"
    },
    "ton": {
        "name": "TON",
        "wallet": "UQDuxTbg1UsTafUapFz7YXsDtGR6HH_qPYOCWQ4gvBmxmL8O",
        "qr_path": "/root/telegram-referral-bot/qr-crypto/qr-ton.jpg",
        "emoji": "💎"
    }
}


def get_crypto_selection_keyboard():
    """Клавиатура для выбора криптовалюты"""
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="💵 USDT (TRC-20)",
                    callback_data="crypto_select:usdt"
                )
            ],
            [
                InlineKeyboardButton(
                    text="₿ Bitcoin (BTC)",
                    callback_data="crypto_select:btc"
                )
            ],
            [
                InlineKeyboardButton(
                    text="💎 TON",
                    callback_data="crypto_select:ton"
                )
            ],
            [
                InlineKeyboardButton(
                    text="⬅️ Назад к способам оплаты",
                    callback_data="back_to_payment"
                )
            ]
        ]
    )
    return keyboard


def get_crypto_details_keyboard(crypto_type: str):
    """Клавиатура для конкретной криптовалюты"""
    buttons = []
    
    # Кнопки переключения между криптовалютами
    crypto_buttons = []
    for key, data in CRYPTO_DATA.items():
        if key != crypto_type:
            crypto_buttons.append(
                InlineKeyboardButton(
                    text=f"{data['emoji']} {data['name']}",
                    callback_data=f"crypto_select:{key}"
                )
            )
    
    # Добавляем кнопки переключения по одной в строке
    for btn in crypto_buttons:
        buttons.append([btn])
    
    # Кнопка подтверждения оплаты
    buttons.append([
        InlineKeyboardButton(
            text="✅ Я оплатил(а)",
            callback_data=f"crypto_payment_confirm:{crypto_type}"
        )
    ])
    
    # Кнопка назад к главному меню оплаты
    buttons.append([
        InlineKeyboardButton(
            text="⬅️ Назад к способам оплаты",
            callback_data="back_to_payment"
        )
    ])
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)


@router.callback_query(F.data == "show_crypto_payment")
async def show_crypto_payment_options(callback: types.CallbackQuery, state: FSMContext):
    """Сразу показать USDT (без промежуточного меню)"""
    logger.info(f"User {callback.from_user.id} opened crypto payment - showing USDT by default")
    
    # Сразу показываем USDT
    crypto_type = "usdt"
    crypto = CRYPTO_DATA[crypto_type]
    
    price = settings.ONBOARDING_COURSE_PRICE
    formatted_amount = f"{price:,.0f}".replace(",", "\u202F") + f" {settings.ONBOARDING_COURSE_CURRENCY}"
    
    text = f"""
{crypto['emoji']} <b>Оплата через {crypto['name']}</b>

💰 <b>Стоимость:</b> {formatted_amount}

📱 <b>Адрес кошелька:</b>
<code>{crypto['wallet']}</code>

<i>*⬆️ нажмите прямо на адрес, чтобы скопировать ⬆️*</i>

📸 Сканируйте QR-код для оплаты:
"""
    
    await state.update_data(selected_crypto=crypto_type)
    await state.set_state(CryptoPaymentStates.selecting_crypto)
    
    # Проверяем существование файла
    if not os.path.exists(crypto['qr_path']):
        logger.error(f"QR code file not found: {crypto['qr_path']}")
        await callback.message.answer(
            text + "\n\n❌ QR-код временно недоступен",
            parse_mode="HTML",
            reply_markup=get_crypto_details_keyboard(crypto_type)
        )
        await callback.answer()
        return
    
    try:
        # Удаляем предыдущее сообщение
        await callback.message.delete()
        
        # Отправляем новое сообщение с QR-кодом
        qr_photo = FSInputFile(crypto['qr_path'])
        await callback.message.answer_photo(
            photo=qr_photo,
            caption=text,
            parse_mode="HTML",
            reply_markup=get_crypto_details_keyboard(crypto_type)
        )
        await callback.answer()
        
    except Exception as e:
        logger.error(f"Error sending QR code: {e}")
        await callback.message.answer(
            text + "\n\n❌ Ошибка загрузки QR-кода",
            parse_mode="HTML",
            reply_markup=get_crypto_details_keyboard(crypto_type)
        )
        await callback.answer()


@router.callback_query(F.data.startswith("crypto_select:"))
async def show_crypto_details(callback: types.CallbackQuery, state: FSMContext):
    """Показать детали выбранной криптовалюты"""
    crypto_type = callback.data.split(":")[1]
    
    if crypto_type not in CRYPTO_DATA:
        await callback.answer("❌ Неизвестная криптовалюта", show_alert=True)
        return
    
    crypto = CRYPTO_DATA[crypto_type]
    logger.info(f"User {callback.from_user.id} selected {crypto['name']}")
    
    price = settings.ONBOARDING_COURSE_PRICE
    formatted_amount = f"{price:,.0f}".replace(",", "\u202F") + f" {settings.ONBOARDING_COURSE_CURRENCY}"
    
    text = f"""
{crypto['emoji']} <b>Оплата через {crypto['name']}</b>

💰 <b>Стоимость:</b> {formatted_amount}

📱 <b>Адрес кошелька:</b>
<code>{crypto['wallet']}</code>

<i>*⬆️ нажмите прямо на адрес, чтобы скопировать ⬆️*</i>

📸 Сканируйте QR-код для оплаты:
"""
    
    # Сохраняем выбранную криптовалюту в состоянии
    await state.update_data(selected_crypto=crypto_type)
    await state.set_state(CryptoPaymentStates.selecting_crypto)
    
    # Проверяем существование файла
    if not os.path.exists(crypto['qr_path']):
        logger.error(f"QR code file not found: {crypto['qr_path']}")
        await callback.message.edit_text(
            text + "\n\n❌ QR-код временно недоступен",
            parse_mode="HTML",
            reply_markup=get_crypto_details_keyboard(crypto_type)
        )
        await callback.answer()
        return
    
    try:
        # Удаляем предыдущее сообщение
        await callback.message.delete()
        
        # Отправляем новое сообщение с QR-кодом
        qr_photo = FSInputFile(crypto['qr_path'])
        await callback.message.answer_photo(
            photo=qr_photo,
            caption=text,
            parse_mode="HTML",
            reply_markup=get_crypto_details_keyboard(crypto_type)
        )
        await callback.answer()
        
    except Exception as e:
        logger.error(f"Error sending QR code: {e}")
        await callback.message.edit_text(
            text + "\n\n❌ Ошибка загрузки QR-кода",
            parse_mode="HTML",
            reply_markup=get_crypto_details_keyboard(crypto_type)
        )
        await callback.answer()


@router.callback_query(F.data.startswith("crypto_payment_confirm:"))
async def request_transaction_hash(callback: types.CallbackQuery, state: FSMContext):
    """Запросить хеш транзакции перед подтверждением"""
    crypto_type = callback.data.split(":")[1]
    
    if crypto_type not in CRYPTO_DATA:
        await callback.answer("❌ Неизвестная криптовалюта", show_alert=True)
        return
    
    crypto = CRYPTO_DATA[crypto_type]
    logger.info(f"User {callback.from_user.id} confirming {crypto['name']} payment")
    
    # Сохраняем криптовалюту в состоянии
    await state.update_data(selected_crypto=crypto_type)
    await state.set_state(CryptoPaymentStates.waiting_hash)
    
    text = f"""
✅ <b>Подтверждение оплаты {crypto['name']}</b>

Пожалуйста, отправьте <b>Hash транзакции</b> (идентификатор платежа) следующим сообщением.

Hash можно найти:
• В приложении вашего криптокошелька
• В истории транзакций
• В подтверждении платежа

<i>Пример Hash: 0x1a2b3c4d5e6f...</i>

Просто скопируйте и отправьте его сюда.
"""
    
    # Клавиатура с кнопкой отмены
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="❌ Отменить",
                    callback_data=f"crypto_select:{crypto_type}"
                )
            ]
        ]
    )
    
    await callback.message.edit_caption(
        caption=text,
        parse_mode="HTML",
        reply_markup=keyboard
    )
    await callback.answer("📝 Ожидаю Hash транзакции...")


@router.message(CryptoPaymentStates.waiting_hash)
async def process_transaction_hash(message: types.Message, state: FSMContext):
    """Обработать полученный хеш транзакции"""
    user_id = message.from_user.id
    transaction_hash = message.text.strip()
    
    # Получаем данные из состояния
    data = await state.get_data()
    crypto_type = data.get('selected_crypto')
    
    if not crypto_type or crypto_type not in CRYPTO_DATA:
        await message.answer("❌ Ошибка: криптовалюта не выбрана")
        await state.clear()
        return
    
    crypto = CRYPTO_DATA[crypto_type]
    logger.info(f"User {user_id} provided transaction hash for {crypto['name']}: {transaction_hash}")
    
    # Проверяем, что пользователь не отправлял заявку недавно
    from app.handlers.onboarding.payment import getcourse_pending
    
    if user_id in getcourse_pending:
        last_request = getcourse_pending[user_id]["timestamp"]
        time_diff = (datetime.now() - last_request).total_seconds()
        
        if time_diff < 300:  # 5 минут
            await message.answer(
                "⏳ Заявка уже отправлена! Ожидайте подтверждения администратора.",
                parse_mode="HTML"
            )
            return
    
    try:
        # Получаем данные пользователя
        async with AsyncSessionLocal() as session:
            user = await UserCRUD.get_user_by_telegram_id(session, user_id)
        
        if not user:
            await message.answer("❌ Ошибка: пользователь не найден")
            await state.clear()
            return
        
        user_info = {
            "telegram_id": user_id,
            "username": message.from_user.username,
            "full_name": message.from_user.full_name,
            "ref_code": user.ref_code,
            "referred_by": user.referred_by,
            "crypto_type": crypto['name'],
            "transaction_hash": transaction_hash
        }
        
        # Сохраняем в pending
        getcourse_pending[user_id] = {
            "timestamp": datetime.now(),
            "user_info": user_info
        }
        
        # Отправляем уведомление админу
        await send_crypto_confirmation_to_admin(message.bot, user_info)
        
        # Подтверждаем пользователю
        confirmation_text = f"""
✅ <b>Отлично! Заявка на подтверждение оплаты отправлена!</b>

{crypto['emoji']} <b>Криптовалюта:</b> {crypto['name']}
🔐 <b>Hash транзакции:</b> <code>{transaction_hash}</code>

⏳ Скоро мы тебе откроем доступ к урокам

<i>Администратор проверит платёж и подтвердит его.</i>
"""
        
        await message.answer(confirmation_text, parse_mode="HTML")
        
        # Очищаем состояние
        await state.clear()
        
        logger.info(f"✅ Crypto payment confirmation request sent to admin for user {user_id}")
        
    except Exception as e:
        logger.error(f"❌ Error processing transaction hash: {e}", exc_info=True)
        await message.answer("❌ Ошибка обработки Hash транзакции. Попробуйте позже.")
        await state.clear()


async def send_crypto_confirmation_to_admin(bot, user_info):
    """Отправить запрос на подтверждение крипто-платежа админу"""
    try:
        user_display = f"@{user_info['username']}" if user_info['username'] else "Без username"
        current_time = datetime.now().strftime("%d.%m.%Y %H:%M:%S")
        
        price = settings.ONBOARDING_COURSE_PRICE
        formatted_amount = f"{price:,.0f}".replace(",", " ") + f" {settings.ONBOARDING_COURSE_CURRENCY}"
        
        admin_message = f"""
🔐 <b>CRYPTO: ЗАЯВКА НА ПОДТВЕРЖДЕНИЕ ОПЛАТЫ</b>

👤 <b>Пользователь:</b> {user_info['full_name']}
🆔 <b>Telegram ID:</b> <code>{user_info['telegram_id']}</code>
🅰️ <b>Username:</b> {user_display}
🔗 <b>Реф. код:</b> {user_info['ref_code']}
👥 <b>Пригласил:</b> {user_info['referred_by'] or 'Самостоятельно'}

💰 <b>Сумма:</b> {formatted_amount}
💎 <b>Криптовалюта:</b> {user_info['crypto_type']}
🔐 <b>Hash транзакции:</b> 
<code>{user_info['transaction_hash']}</code>
⏰ <b>Время заявки:</b> {current_time}

<b>❗️ Проверьте поступление платежа и подтвердите:</b>
"""
        
        admin_keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="✅ CRYPTO: ПОДТВЕРДИТЬ ОПЛАТУ",
                        callback_data=f"admin_approve_getcourse:{user_info['telegram_id']}"
                    )
                ],
                [
                    InlineKeyboardButton(
                        text="❌ CRYPTO: ОТКЛОНИТЬ",
                        callback_data=f"admin_reject_getcourse:{user_info['telegram_id']}"
                    )
                ]
            ]
        )
        
        await bot.send_message(
            chat_id=settings.ADMIN_ID,
            text=admin_message,
            parse_mode="HTML",
            reply_markup=admin_keyboard
        )
        
        logger.info(f"✅ Crypto payment confirmation sent to admin for user {user_info['telegram_id']}")
        
    except Exception as e:
        logger.error(f"❌ Error sending crypto confirmation to admin: {e}", exc_info=True)


@router.callback_query(F.data == "back_to_payment")
async def back_to_payment(callback: types.CallbackQuery, state: FSMContext):
    """Вернуться к выбору способа оплаты"""
    await state.clear()
    
    from app.handlers.onboarding.payment import get_integrated_payment_keyboard
    from app.services.robokassa_handler import robokassa_handler
    
    price = settings.ONBOARDING_COURSE_PRICE
    formatted_amount = f"{price:,.0f}".replace(",", "\u202F") + f" {settings.ONBOARDING_COURSE_CURRENCY}"
    
    payment_text = f"""
📚 <b>Урок «Инструкция партнерской системы»</b>

💡 <b>Бонус:</b>
- Место в команде Мамеда 🧑‍💻
- Поддержка команды 💪

<b>Стоимость: {formatted_amount}</b>

<i>Внимание! Оплата по частям не относится к нашей программе т.к. противоречат нашим религиозным принципам! Мы принимаем оплату только полной стоимости продукта ✅</i>
"""
    
    # Создаем payment_url для Robokassa
    payment_url = None
    if not settings.ONBOARDING_MOCK_PAYMENT:
        try:
            payment_url, invoice_id = await robokassa_handler.create_payment(
                user_id=callback.from_user.id,
                amount=settings.ONBOARDING_COURSE_PRICE,
                description="Онбординг курс партнерской программы"
            )
            logger.info(f"✅ Robokassa payment created for return: {invoice_id}")
        except Exception as e:
            logger.error(f"❌ Error creating Robokassa payment on return: {e}")
    
    keyboard = get_integrated_payment_keyboard(payment_url)
    
    # Удаляем старое сообщение с фото и отправляем новое текстовое
    try:
        await callback.message.delete()
        await callback.message.answer(
            payment_text,
            parse_mode="HTML",
            reply_markup=keyboard
        )
    except:
        # Если не получилось удалить, просто отправляем новое
        await callback.message.answer(
            payment_text,
            parse_mode="HTML",
            reply_markup=keyboard
        )
    
    await callback.answer()