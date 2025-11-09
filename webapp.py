"""
FastAPI приложение для обработки webhooks
Создайте этот файл как: app.py (в корне проекта, рядом с bot.py)
"""
import logging
from fastapi import FastAPI, Request, HTTPException, Form
from fastapi.responses import RedirectResponse, PlainTextResponse, HTMLResponse
from typing import Optional

from app.config import settings
from app.database.connection import AsyncSessionLocal
from app.database.crud import ClickCRUD, SaleCRUD, PaymentCRUD, UserCRUD
from app.database.models import User, Payment

# Импорт Robokassa и функций обработки
try:
    from app.services.robokassa import robokassa_service
    ROBOKASSA_AVAILABLE = True
except ImportError:
    ROBOKASSA_AVAILABLE = False
    robokassa_service = None

try:
    from app.handlers.onboarding.payment import process_onboarding_payment_webhook
    ONBOARDING_AVAILABLE = True
except ImportError:
    ONBOARDING_AVAILABLE = False

from app.services.notifications import send_sale_notification, send_payment_notification

logger = logging.getLogger(__name__)
app = FastAPI(title="Referral Bot API", version="1.0.0")


@app.get("/")
async def root():
    """Корневой маршрут"""
    return {
        "status": "Bot webhook server is running",
        "robokassa_enabled": ROBOKASSA_AVAILABLE,
        "onboarding_enabled": ONBOARDING_AVAILABLE
    }


@app.get("/track/{ref_code}")
async def track_click(ref_code: str, request: Request):
    """Отслеживание переходов по реферальной ссылке"""
    # Получаем данные о клике
    client_ip = request.client.host
    user_agent = request.headers.get("user-agent", "Unknown")
    
    # Сохраняем клик
    async with AsyncSessionLocal() as session:
        await ClickCRUD.create_click(
            session=session,
            ref_code=ref_code,
            ip_address=client_ip,
            user_agent=user_agent,
            source=request.query_params.get("utm_source", "direct")
        )
    
    # Перенаправляем на лендинг с сохранением ref_code
    landing_url = f"{settings.LANDING_URL}?ref={ref_code}"
    return RedirectResponse(url=landing_url, status_code=302)


@app.post("/webhook/telegram")
async def telegram_webhook(request: Request):
    """Webhook для Telegram обновлений"""
    # Этот эндпоинт будет использоваться aiogram
    return {"ok": True}


@app.post("/webhook/robokassa/result")
async def robokassa_result_webhook(
    OutSum: float = Form(...),
    InvId: str = Form(...),
    SignatureValue: str = Form(...),
    shp_email: Optional[str] = Form(None),
    shp_phone: Optional[str] = Form(None)
):
    """
    Result URL webhook от Robokassa
    Вызывается при успешной оплате для уведомления сервера
    """
    logger.info(f"Robokassa result webhook: InvId={InvId}, OutSum={OutSum}")
    
    if not ROBOKASSA_AVAILABLE:
        logger.error("Robokassa service not available")
        raise HTTPException(status_code=500, detail="Robokassa not configured")
    
    try:
        # Проверяем подпись
        is_valid = robokassa_service.verify_payment(
            out_sum=str(OutSum),
            inv_id=InvId,
            signature=SignatureValue,
            shp_email=shp_email,
            shp_phone=shp_phone
        )
        
        if not is_valid:
            logger.warning(f"Invalid signature for payment {InvId}")
            raise HTTPException(status_code=400, detail="Invalid signature")
        
        # Сначала пытаемся обработать как платеж онбординга
        if ONBOARDING_AVAILABLE and InvId.startswith("onboard_"):
            processed = await process_onboarding_payment_webhook(InvId, OutSum, SignatureValue)
            if processed:
                return PlainTextResponse("OK")
        
        # Если это не онбординг или обработка не удалась, обрабатываем как обычный платеж
        await process_regular_payment_webhook(InvId, OutSum, SignatureValue, shp_email)
        
        return PlainTextResponse("OK")
        
    except Exception as e:
        logger.error(f"Error processing Robokassa result: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


async def process_regular_payment_webhook(invoice_id: str, amount: float, signature: str, customer_email: str = None):
    """Обработка обычных платежей (не онбординг)"""
    async with AsyncSessionLocal() as session:
        payment = await PaymentCRUD.get_payment_by_invoice_id(session, invoice_id)
        
        if not payment:
            logger.warning(f"Payment not found: {invoice_id}")
            return
        
        if payment.status == "paid":
            logger.info(f"Payment {invoice_id} already processed")
            return
        
        # Обновляем статус
        await PaymentCRUD.update_payment_status(
            session=session,
            payment_id=payment.id,
            status="paid",
            robokassa_signature=signature,
            robokassa_out_sum=amount
        )
        
        # Получаем пользователя
        user = await session.get(User, payment.user_id)
        if user and user.ref_code:
            # Создаем продажу для реферала (если есть реферер)
            if user.referred_by:
                await SaleCRUD.create_sale(
                    session=session,
                    ref_code=user.referred_by,
                    amount=amount,
                    commission_percent=settings.COMMISSION_PERCENT,
                    customer_email=customer_email or user.email or "",
                    product=payment.description,
                    payment_id=payment.id
                )
                
                # Отправляем уведомление рефереру
                await send_sale_notification(
                    ref_code=user.referred_by,
                    amount=amount,
                    commission=amount * settings.COMMISSION_PERCENT / 100
                )
        
        # Отправляем уведомление плательщику
        if user:
            await send_payment_notification(
                user_id=user.telegram_id,
                amount=amount,
                status="paid",
                description=payment.description
            )
        
        logger.info(f"Payment {invoice_id} processed successfully")


@app.get("/webhook/robokassa/success")
async def robokassa_success_page(
    OutSum: Optional[float] = None,
    InvId: Optional[str] = None,
    SignatureValue: Optional[str] = None
):
    """
    Success URL - страница успешной оплаты
    Пользователь попадает сюда после успешной оплаты
    """
    if InvId:
        logger.info(f"User redirected to success page for payment {InvId}")
    
    success_html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Оплата успешна</title>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <style>
            body {{ 
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Arial, sans-serif;
                text-align: center; 
                padding: 50px 20px; 
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
                margin: 0;
                min-height: 100vh;
                display: flex;
                flex-direction: column;
                justify-content: center;
            }}
            .container {{
                background: rgba(255, 255, 255, 0.1);
                backdrop-filter: blur(10px);
                border-radius: 20px;
                padding: 40px;
                max-width: 500px;
                margin: 0 auto;
                box-shadow: 0 8px 32px rgba(0, 0, 0, 0.1);
            }}
            .success {{ 
                color: #4CAF50; 
                font-size: 28px; 
                margin-bottom: 20px;
                text-shadow: 2px 2px 4px rgba(0,0,0,0.3);
            }}
            .info {{ 
                color: rgba(255, 255, 255, 0.9); 
                margin: 15px 0; 
                font-size: 16px;
            }}
            .btn {{
                display: inline-block;
                background: #4CAF50;
                color: white;
                padding: 12px 30px;
                text-decoration: none;
                border-radius: 25px;
                margin-top: 20px;
                font-weight: bold;
                transition: all 0.3s ease;
            }}
            .btn:hover {{
                background: #45a049;
                transform: translateY(-2px);
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1 class="success">✅ Оплата прошла успешно!</h1>
            {f'<p class="info">💰 Сумма: {OutSum} руб.</p>' if OutSum else ''}
            {f'<p class="info">🆔 Номер заказа: {InvId}</p>' if InvId else ''}
            <p class="info">Спасибо за покупку!</p>
            <p class="info">Вернитесь в Telegram бот для продолжения.</p>
            <a href="https://t.me/{settings.BOT_USERNAME}" class="btn">🔙 Перейти в бот</a>
        </div>
    </body>
    </html>
    """
    
    return HTMLResponse(content=success_html)


@app.get("/webhook/robokassa/fail")
async def robokassa_fail_page(
    OutSum: Optional[float] = None,
    InvId: Optional[str] = None,
    SignatureValue: Optional[str] = None
):
    """
    Fail URL - страница неуспешной оплаты
    """
    if InvId:
        logger.info(f"User redirected to fail page for payment {InvId}")
        
        # Обновляем статус платежа на failed
        try:
            async with AsyncSessionLocal() as session:
                payment = await PaymentCRUD.get_payment_by_invoice_id(session, InvId)
                if payment and payment.status != "failed":
                    await PaymentCRUD.update_payment_status(
                        session=session,
                        payment_id=payment.id,
                        status="failed"
                    )
        except Exception as e:
            logger.error(f"Error updating failed payment status: {e}")
    
    fail_html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Ошибка оплаты</title>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <style>
            body {{ 
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Arial, sans-serif;
                text-align: center; 
                padding: 50px 20px; 
                background: linear-gradient(135deg, #ff6b6b 0%, #ee5a24 100%);
                color: white;
                margin: 0;
                min-height: 100vh;
                display: flex;
                flex-direction: column;
                justify-content: center;
            }}
            .container {{
                background: rgba(255, 255, 255, 0.1);
                backdrop-filter: blur(10px);
                border-radius: 20px;
                padding: 40px;
                max-width: 500px;
                margin: 0 auto;
                box-shadow: 0 8px 32px rgba(0, 0, 0, 0.1);
            }}
            .error {{ 
                color: #ff4757; 
                font-size: 28px; 
                margin-bottom: 20px;
                text-shadow: 2px 2px 4px rgba(0,0,0,0.3);
            }}
            .info {{ 
                color: rgba(255, 255, 255, 0.9); 
                margin: 15px 0; 
                font-size: 16px;
            }}
            .btn {{
                display: inline-block;
                background: #ff4757;
                color: white;
                padding: 12px 30px;
                text-decoration: none;
                border-radius: 25px;
                margin-top: 20px;
                font-weight: bold;
                transition: all 0.3s ease;
            }}
            .btn:hover {{
                background: #ff3838;
                transform: translateY(-2px);
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1 class="error">❌ Оплата не прошла</h1>
            {f'<p class="info">🆔 Номер заказа: {InvId}</p>' if InvId else ''}
            <p class="info">Проверьте данные карты и попробуйте еще раз.</p>
            <p class="info">💡 Возможные причины:</p>
            <p class="info">• Недостаточно средств<br>• Карта заблокирована<br>• Технические проблемы</p>
            <a href="https://t.me/{settings.BOT_USERNAME}" class="btn">🔙 Вернуться в бот</a>
        </div>
    </body>
    </html>
    """
    
    return HTMLResponse(content=fail_html)


@app.get("/health")
async def health_check():
    """Проверка состояния сервиса"""
    return {
        "status": "healthy",
        "service": "referral-bot-webhooks",
        "robokassa_enabled": ROBOKASSA_AVAILABLE,
        "onboarding_enabled": ONBOARDING_AVAILABLE,
        "test_mode": getattr(settings, 'ROBOKASSA_TEST_MODE', True)
    }


@app.get("/admin/payments")
async def admin_payments(status: Optional[str] = None, limit: int = 50):
    """Админ панель для просмотра платежей"""
    # TODO: Добавить авторизацию админа
    try:
        async with AsyncSessionLocal() as session:
            if status:
                payments = await PaymentCRUD.get_payments_by_status(session, status)
            else:
                # Получаем последние платежи
                from sqlalchemy import select
                result = await session.execute(
                    select(Payment).order_by(Payment.created_at.desc()).limit(limit)
                )
                payments = result.scalars().all()
            
            payments_data = []
            for payment in payments:
                payments_data.append({
                    "id": payment.id,
                    "invoice_id": payment.invoice_id,
                    "amount": payment.amount,
                    "status": payment.status,
                    "description": payment.description,
                    "created_at": payment.created_at.isoformat() if payment.created_at else None,
                    "paid_at": payment.paid_at.isoformat() if payment.paid_at else None,
                    "user_id": payment.user_id
                })
            
            return {
                "payments": payments_data,
                "count": len(payments_data),
                "filter": status,
                "limit": limit
            }
            
    except Exception as e:
        logger.error(f"Error in admin payments: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


# Запуск: uvicorn app:app --host 0.0.0.0 --port 8000 --reload