"""
Обновленный robokassa_handler.py с поддержкой тестовых паролей и логики последнего реферала
"""
import asyncio
import hashlib
import logging
from typing import Optional
from urllib.parse import urlencode
from datetime import datetime

from app.config import settings
from app.database.connection import AsyncSessionLocal
from app.database.crud import PaymentCRUD, UserCRUD, SaleCRUD
from app.database.models import User, OnboardingStage

logger = logging.getLogger(__name__)


class RobokassaHandler:
    """Обработчик Robokassa платежей"""
    
    def __init__(self):
        self.merchant_login = settings.ROBOKASSA_MERCHANT_LOGIN
        self.test_mode = settings.ROBOKASSA_TEST_MODE
        
        # ✅ АВТОМАТИЧЕСКИЙ ВЫБОР ПАРОЛЕЙ В ЗАВИСИМОСТИ ОТ РЕЖИМА
        if self.test_mode:
            self.password_1 = settings.ROBOKASSA_TEST_PASSWORD_1 or settings.ROBOKASSA_PASSWORD_1
            self.password_2 = settings.ROBOKASSA_TEST_PASSWORD_2 or settings.ROBOKASSA_PASSWORD_2
            logger.info("🧪 Using TEST mode passwords")
        else:
            self.password_1 = settings.ROBOKASSA_PASSWORD_1
            self.password_2 = settings.ROBOKASSA_PASSWORD_2
            logger.info("🏭 Using PRODUCTION mode passwords")
        
        # URL для платежей
        self.payment_url = "https://auth.robokassa.ru/Merchant/Index.aspx"
        
        # Логируем настройки для отладки
        logger.info(f"🔧 Robokassa initialized:")
        logger.info(f"   Merchant: {self.merchant_login}")
        logger.info(f"   Test mode: {self.test_mode}")
        logger.info(f"   Password1 ends with: ...{self.password_1[-4:]}")
        logger.info(f"   Password2 ends with: ...{self.password_2[-4:]}")
    
    async def create_payment(self, user_id: int, amount: float, description: str) -> tuple[str, str]:
        """Создание платежа в Robokassa"""
        try:
            # ✅ ИСПРАВЛЕНИЕ: InvId должен быть ТОЛЬКО ЧИСЛОВЫМ
            # Используем timestamp как уникальный числовой ID
            invoice_id = str(int(datetime.now().timestamp()))
            
            # Сохраняем платеж в БД
            async with AsyncSessionLocal() as session:
                user = await UserCRUD.get_user_by_telegram_id(session, user_id)
                if not user:
                    logger.error(f"❌ User with telegram_id {user_id} not found")
                    raise ValueError(f"User with telegram_id {user_id} not found")
                
                await PaymentCRUD.create_payment(
                    session=session,
                    user_id=user.id,
                    invoice_id=invoice_id,
                    amount=amount,
                    description=description
                )
                
                logger.info(f"💾 Payment record saved: invoice_id={invoice_id}")
            
            # Создаем URL для оплаты
            payment_url = self._build_payment_url(
                amount=amount,
                invoice_id=invoice_id,
                description=description
            )
            
            logger.info(f"✅ Created Robokassa payment: {invoice_id} for telegram_user {user_id}")
            
            return payment_url, invoice_id
            
        except Exception as e:
            logger.error(f"❌ Error creating Robokassa payment: {e}")
            raise
    
    def _build_payment_url(self, amount: float, invoice_id: str, description: str) -> str:
        """Формирование URL для оплаты с правильными паролями"""
        
        amount_str = f"{amount:.2f}"
        
        # Параметры для Robokassa
        params = {
            'MerchantLogin': self.merchant_login,
            'OutSum': amount_str,
            'InvId': invoice_id,
            'Description': description,
            'Culture': 'ru',
            'Encoding': 'utf-8'
        }
        
        # URL для уведомлений
        params['ResultURL'] = settings.ROBOKASSA_RESULT_URL
        params['SuccessURL'] = settings.ROBOKASSA_SUCCESS_URL
        params['FailURL'] = settings.ROBOKASSA_FAIL_URL
        
        # Тестовый режим
        if self.test_mode:
            params['IsTest'] = '1'
        
        # ✅ СОЗДАЕМ ПОДПИСЬ С ПРАВИЛЬНЫМ ПАРОЛЕМ
        signature_string = f"{self.merchant_login}:{amount_str}:{invoice_id}:{self.password_1}"
        signature = hashlib.md5(signature_string.encode('utf-8')).hexdigest().upper()
        
        # Логируем для отладки
        password_type = "TEST" if self.test_mode else "PROD"
        logger.info(f"🔐 [{password_type}] Signature string: {signature_string}")
        logger.info(f"🔐 [{password_type}] Calculated signature: {signature}")
        
        params['SignatureValue'] = signature
        
        # Формируем полный URL
        full_url = f"{self.payment_url}?{urlencode(params)}"
        
        logger.info(f"🌐 Payment URL created: {full_url[:100]}...")
        
        return full_url
    
    def verify_payment(self, out_sum: str, inv_id: str, signature: str) -> bool:
        """Проверка подписи с отладкой"""
        try:
            # Записываем ВСЕ в файл для отладки
            with open("/tmp/verify_debug.log", "a") as f:
                f.write(f"\n=== VERIFY PAYMENT DEBUG ===\n")
                f.write(f"Raw out_sum: '{out_sum}'\n")
                f.write(f"Raw inv_id: '{inv_id}'\n")
                f.write(f"Raw signature: '{signature}'\n")
                f.write(f"Test mode: {self.test_mode}\n")
                f.write(f"Password2: {self.password_2}\n")
            
            # Форматирование суммы
            amount_float = float(out_sum)
            
            # Пробуем разные форматы
            formats = [
                out_sum,                      # как есть от Робокассы
                f"{amount_float:.6f}",        # 4700.000000 (ПРОДАКШН)  ← ДЛЯ ПРОДА!
                f"{amount_float:.2f}",        # 4700.00
                f"{amount_float:.1f}",        # 4700.0 
                f"{amount_float:.0f}",        # 4700 (ТЕСТ работает)     ← ДЛЯ ТЕСТА!
                f"{int(amount_float)}"        # 4700
            ]
                        
            with open("/tmp/verify_debug.log", "a") as f:
                f.write(f"Testing formats:\n")
                
                for i, amount_str in enumerate(formats):
                    signature_string = f"{amount_str}:{inv_id}:{self.password_2}"
                    expected_signature = hashlib.md5(signature_string.encode('utf-8')).hexdigest().upper()
                    is_match = expected_signature == signature.upper()
                    
                    f.write(f"  Format {i+1}: '{amount_str}'\n")
                    f.write(f"    String: '{signature_string}'\n")
                    f.write(f"    Expected: {expected_signature}\n")
                    f.write(f"    Match: {is_match}\n")
                    
                    if is_match:
                        f.write(f"  ✅ FOUND CORRECT FORMAT!\n")
                        return True
            
            with open("/tmp/verify_debug.log", "a") as f:
                f.write(f"❌ NO FORMAT MATCHED\n")
                f.write(f"=== END ===\n\n")
            
            return False
            
        except Exception as e:
            with open("/tmp/verify_debug.log", "a") as f:
                f.write(f"ERROR in verify_payment: {e}\n")
            logger.error(f"❌ Error verifying signature: {e}")
            return False
    
    async def process_successful_payment(self, out_sum: float, inv_id: str) -> bool:
        """Обработка успешного платежа с новой логикой реферала"""
        logger.info(f"🔥🔥🔥 PROCESS_SUCCESSFUL_PAYMENT CALLED: {inv_id}")
        try:
            async with AsyncSessionLocal() as session:
                # Найти платеж в БД
                payment = await PaymentCRUD.get_payment_by_invoice_id(session, inv_id)
                if not payment:
                    logger.error(f"❌ Payment not found: {inv_id}")
                    return False
                
                # Проверить что еще не обработан
                if payment.status == "paid":
                    logger.info(f"⚠️ Payment already processed: {inv_id}")
                    return True
                
                # Обновить статус платежа
                await PaymentCRUD.update_payment_status(
                    session=session,
                    payment_id=payment.id,
                    status="paid",
                    robokassa_out_sum=out_sum
                )
                
                # Получить пользователя
                user = await session.get(User, payment.user_id)
                if not user:
                    logger.error(f"❌ User not found for payment: {payment.user_id}")
                    return False
                
                # Завершить оплату в онбординге
                await UserCRUD.complete_payment(session, user.telegram_id)
                
                # НОВАЯ ЛОГИКА: Получаем последнего реферала
                last_referrer_code = await UserCRUD.get_last_referrer(session, user.telegram_id)
                
                # Создать продажу для реферера (если есть)
                if last_referrer_code:
                    await self._create_referral_sale_new_logic(session, user, out_sum, last_referrer_code)
                
                # Отправить автоматическое уведомление
                await self.send_auto_payment_notification(user.telegram_id, out_sum)
                
                logger.info(f"✅ Payment processed successfully: {inv_id}")
                return True
                
        except Exception as e:
            logger.error(f"❌ Error processing payment {inv_id}: {e}", exc_info=True)
            return False
    
    async def _create_referral_sale_new_logic(self, session, user, amount: float, last_referrer_code: str):
        """Создание продажи для последнего реферера"""
        try:
            referrer = await UserCRUD.get_user_by_ref_code(session, last_referrer_code)
            if referrer:
                sale = await SaleCRUD.create_sale(
                    session=session,
                    ref_code=last_referrer_code,
                    amount=amount,
                    commission_percent=settings.COMMISSION_PERCENT,
                    customer_email=user.username or f"user_{user.telegram_id}",
                    product="Onboarding Course (Robokassa Auto)"
                )
                
                logger.info(f"🎉 Created referral sale with new logic: {sale.id}, commission: {sale.commission_amount}")
                
                # ВАЖНО: Логируем в историю реферальных действий
                from app.database.crud import ReferralHistoryCRUD
                await ReferralHistoryCRUD.log_action(
                    session=session,
                    user_telegram_id=user.telegram_id,
                    ref_code=last_referrer_code,
                    action_type="payment",
                    amount=sale.amount,
                    commission_amount=sale.commission_amount
                )
                
                # Отправить уведомление реферу
                await self._send_referral_notification(referrer.telegram_id, sale.amount, sale.commission_amount)
                        
        except Exception as e:
            logger.error(f"❌ Error creating referral sale with new logic: {e}")
    
    async def _record_to_sheets_new_logic(self, user, invited_by_telegram_id: int):
        """Запись в Google Sheets с новой логикой"""
        try:
            from app.services.google_sheets import add_payment_to_sheets, init_google_sheets
            
            logger.info(f"🔥 Initializing Google Sheets...")
            await init_google_sheets()
            
            logger.info(f"🔥 Recording to Google Sheets...")
            await add_payment_to_sheets(
                telegram_id=user.telegram_id,
                username=user.username,
                user_ref_code=user.ref_code,
                invited_by_telegram_id=invited_by_telegram_id
            )
            logger.info(f"✅ Google Sheets recorded successfully with referrer: {invited_by_telegram_id}")
            
        except Exception as e:
            logger.error(f"❌ Error recording to Google Sheets: {e}")
    
    async def send_auto_payment_notification(self, user_id: int, amount: float):
        """АВТОМАТИЧЕСКОЕ уведомление сразу после оплаты с новой логикой"""
        logger.info(f"🔥🔥🔥 SEND_AUTO_PAYMENT_NOTIFICATION CALLED for user {user_id}")
        try:
            from aiogram import Bot
            from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
            
            bot = Bot(token=settings.BOT_TOKEN)
            
            # Отправляем правильное сообщение
            success_text = """
🎉 <b>Поздравляю! Оплата прошла успешно!</b>
Смотреть урок ⤵️
"""
            
            await bot.send_message(
                chat_id=user_id,
                text=success_text,
                parse_mode="HTML"
            )
            
            # Обновляем стадию сразу здесь
            async with AsyncSessionLocal() as session:
                await UserCRUD.update_onboarding_stage(session, user_id, OnboardingStage.WANT_JOIN)
            
            # Отправляем видео БЕЗ кнопок
            video_file_id = settings.VIDEO3_ID
                        
            if video_file_id and video_file_id != "BAACAgIAAxkBAAI...":
                await bot.send_video(
                    chat_id=user_id,
                    video=video_file_id,
                    parse_mode="HTML",
                    supports_streaming=True
                )
            else:
                await bot.send_message(
                    chat_id=user_id,
                    text="📹 <b>Обучающее видео</b>",
                    parse_mode="HTML"
                )
            
            # Отправляем инструкцию PDF с кнопкой
            from app.handlers.onboarding.payment import send_instruction_pdf
            await send_instruction_pdf(bot, user_id)
            
            await bot.session.close()
            logger.info(f"✅ Auto payment notification sent to user {user_id}")
            
            # ✅ ИСПРАВЛЕННАЯ ЗАПИСЬ В GOOGLE SHEETS ДЛЯ ПОЛЬЗОВАТЕЛЕЙ БЕЗ РЕФЕРАЛА
            try:
                logger.info(f"🔥 STARTING Google Sheets recording from auto notification for user {user_id}")
                
                async with AsyncSessionLocal() as session:
                    user = await UserCRUD.get_user_by_telegram_id(session, user_id)
                    if user:
                        # НОВАЯ ЛОГИКА: Получаем последнего реферала
                        last_referrer_code = await UserCRUD.get_last_referrer(session, user_id)
                        
                        invited_by_telegram_id = None
                        if last_referrer_code:
                            referrer = await UserCRUD.get_user_by_ref_code(session, last_referrer_code)
                            if referrer:
                                invited_by_telegram_id = referrer.telegram_id
                                logger.info(f"🔗 Last referrer found: {invited_by_telegram_id}")
                            else:
                                logger.warning(f"⚠️ Referrer with code {last_referrer_code} not found")
                        else:
                            logger.info(f"ℹ️ User {user_id} has no referrer")
                        
                        from app.services.google_sheets import add_payment_to_sheets, init_google_sheets
                        
                        logger.info(f"🔥 Initializing Google Sheets...")
                        await init_google_sheets()
                        
                        logger.info(f"🔥 Recording to Google Sheets...")
                        await add_payment_to_sheets(
                            telegram_id=user.telegram_id,
                            username=user.username,
                            user_ref_code=user.ref_code,
                            invited_by_telegram_id=invited_by_telegram_id
                        )
                        logger.info(f"✅ Google Sheets recorded successfully with referrer: {invited_by_telegram_id}")
                        
            except Exception as sheets_error:
                logger.error(f"❌ Error recording to Google Sheets in auto notification: {sheets_error}")
                # НЕ останавливаем процесс из-за ошибки Sheets
            
        except Exception as e:
            logger.error(f"❌ Error sending auto notification: {e}")
    
    async def _send_referral_notification(self, referrer_id: int, sale_amount: float, commission: float):
        """Отправка уведомления о комиссии"""
        logger.info(f"🔥🔥🔥 _SEND_REFERRAL_NOTIFICATION CALLED for referrer {referrer_id}")
        try:
            from aiogram import Bot
            
            bot = Bot(token=settings.BOT_TOKEN)
            
            # Получаем актуальный баланс реферера
            async with AsyncSessionLocal() as session:
                referrer = await UserCRUD.get_user_by_telegram_id(session, referrer_id)
                if referrer:
                    total_commission = await SaleCRUD.get_total_commission(session, referrer.ref_code)
                    formatted_balance = f"{total_commission:,.0f} руб.".replace(",", " ")
                else:
                    formatted_balance = "0 руб."
            
            # Форматируем комиссию
            formatted_commission = f"{commission:,.0f} руб.".replace(",", " ")
            
            notification_text = f"""
🎉 <b>Новая продажа по вашей ссылке!</b>

💵 <b>Ваша комиссия:</b> {formatted_commission}
💰 <b>Мой баланс:</b> {formatted_balance}
"""
            
            await bot.send_message(
                chat_id=referrer_id,
                text=notification_text,
                parse_mode="HTML"
            )
            
            await bot.session.close()
            logger.info(f"✅ Referral notification sent to {referrer_id}")
            
        except Exception as e:
            logger.error(f"❌ Error sending referral notification: {e}")


# Глобальный экземпляр
robokassa_handler = RobokassaHandler()