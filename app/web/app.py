"""
FastAPI приложение для обработки webhooks с поддержкой Robokassa
"""
from fastapi import FastAPI, Request, HTTPException, Form, Query
from fastapi.responses import RedirectResponse, HTMLResponse, PlainTextResponse
import hashlib
import hmac
import logging
from typing import Optional
from datetime import datetime

from app.config import settings
from app.database.connection import AsyncSessionLocal
from app.database.crud import ClickCRUD, SaleCRUD
from app.services.robokassa_handler import robokassa_handler
from app.services.google_sheets import init_google_sheets

logger = logging.getLogger(__name__)

app = FastAPI(title="Referral Bot Webhooks", version="1.0.0")


@app.on_event("startup")
async def startup_event():
    """Инициализация при запуске FastAPI"""
    logger.info("🚀 Starting FastAPI webhook server...")
    
    # Инициализируем Google Sheets
    try:
        await init_google_sheets()
        logger.info("✅ Google Sheets initialized in FastAPI")
    except Exception as e:
        logger.error(f"❌ Failed to initialize Google Sheets: {e}")


@app.get("/")
async def root():
    """Корневой маршрут"""
    return {
        "status": "Referral Bot webhook server is running",
        "version": "1.0.0",
        "robokassa_enabled": not settings.ONBOARDING_MOCK_PAYMENT,
        "test_mode": settings.ROBOKASSA_TEST_MODE
    }


@app.get("/health")
async def health_check():
    """Проверка состояния сервиса"""
    return {
        "status": "healthy",
        "service": "referral-bot-webhooks",
        "timestamp": datetime.now().isoformat(),
        "robokassa_enabled": not settings.ONBOARDING_MOCK_PAYMENT,
        "test_mode": settings.ROBOKASSA_TEST_MODE if not settings.ONBOARDING_MOCK_PAYMENT else None
    }


# ========================================
# ИСПРАВЛЕННЫЙ RESULT ENDPOINT
# ========================================

@app.get("/webhook/robokassa/result")  # ✅ ИЗМЕНИЛИ POST на GET
@app.post("/webhook/robokassa/result") # ✅ ДОБАВИЛИ поддержку обоих методов
async def robokassa_result(request: Request):
    print("=== WEBHOOK CALLED ===")  # ← ДОБАВЬТЕ ЭТУ СТРОКУ
    logger.info("=== WEBHOOK CALLED ===")  # ← И ЭТУ
    """
    Result URL - основной webhook от Robokassa
    Поддерживает как GET так и POST запросы
    """
    
    # ✅ ПОЛУЧАЕМ ПАРАМЕТРЫ В ЗАВИСИМОСТИ ОТ МЕТОДА
    if request.method == "GET":
        # Для GET запросов параметры в query string
        OutSum = float(request.query_params.get("OutSum", 0))
        InvId = str(request.query_params.get("InvId", ""))
        SignatureValue = str(request.query_params.get("SignatureValue", ""))
    else:
        # Для POST запросов используем Form
        form = await request.form()
        OutSum = float(form.get("OutSum", 0))
        InvId = str(form.get("InvId", ""))
        SignatureValue = str(form.get("SignatureValue", ""))
    
    # ✅ ОТЛАДКА
    logger.info(f"🔥 WEBHOOK DEBUG:")
    logger.info(f"   Method: {request.method}")
    logger.info(f"   OutSum: {OutSum}")
    logger.info(f"   InvId: {InvId}")
    logger.info(f"   SignatureValue: {SignatureValue}")
    logger.info(f"   Test mode: {settings.ROBOKASSA_TEST_MODE}")
    logger.info(f"   Test Password2: {settings.ROBOKASSA_TEST_PASSWORD_2}")
    
    # Вычисляем подпись вручную
    import hashlib
    test_password2 = settings.ROBOKASSA_TEST_PASSWORD_2
    signature_string = f"{OutSum:.2f}:{InvId}:{test_password2}"
    expected = hashlib.md5(signature_string.encode('utf-8')).hexdigest().upper()
    
    logger.info(f"   Manual calculation:")
    logger.info(f"   Signature string: {signature_string}")
    logger.info(f"   Expected: {expected}")
    logger.info(f"   Received: {SignatureValue}")
    logger.info(f"   Match: {expected == SignatureValue}")
    
    logger.info(f"🔥 Robokassa result: InvId={InvId}, OutSum={OutSum}")
    
    try:
        # Проверяем подпись
        if not robokassa_handler.verify_payment(str(OutSum), InvId, SignatureValue):
            logger.warning(f"❌ Invalid signature for payment {InvId}")
            return {"error": "Invalid signature"}, 400
        
        # Обрабатываем платеж
        success = await robokassa_handler.process_successful_payment(OutSum, InvId)
        
        if success:
            logger.info(f"✅ Payment {InvId} processed successfully")
            return PlainTextResponse(f"OK{InvId}")
        else:
            logger.error(f"❌ Failed to process payment {InvId}")
            return {"error": "Processing failed"}, 500
            
    except Exception as e:
        logger.error(f"💥 Error in robokassa webhook: {e}", exc_info=True)
        return {"error": "Internal error"}, 500


# ========================================
# ОБНОВЛЕННЫЙ SUCCESS ENDPOINT  
# ========================================

@app.get("/webhook/robokassa/success")
async def robokassa_success(
    request: Request,
    OutSum: Optional[str] = Query(None),
    InvId: Optional[str] = Query(None)
):
    """Success URL - красивая страница успеха (GET метод)"""
    logger.info(f"🎉 Robokassa success (GET): InvId={InvId}")
    
    success_html = f"""<!DOCTYPE html>
<html>
<head>
    <title>Оплата успешна!</title>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            text-align: center;
            padding: 50px 20px;
            margin: 0;
            min-height: 100vh;
            display: flex;
            justify-content: center;
            align-items: center;
        }}
        .container {{
            background: rgba(255,255,255,0.1);
            backdrop-filter: blur(10px);
            border-radius: 20px;
            padding: 40px;
            max-width: 500px;
            box-shadow: 0 8px 32px rgba(0,0,0,0.3);
        }}
        .success {{ font-size: 48px; margin-bottom: 20px; }}
        .title {{ font-size: 28px; margin-bottom: 20px; font-weight: 600; }}
        .info {{ font-size: 18px; margin-bottom: 30px; line-height: 1.6; }}
        .button {{
            background: linear-gradient(45deg, #4CAF50, #45a049);
            color: white;
            padding: 15px 30px;
            text-decoration: none;
            border-radius: 50px;
            font-size: 18px;
            font-weight: 600;
            display: inline-block;
            transition: transform 0.2s;
        }}
        .button:hover {{ transform: translateY(-2px); }}
    </style>
</head>
<body>
    <div class="container">
        <div class="success">✅</div>
        <div class="title">Оплата прошла успешно!</div>
        <div class="info">
            Спасибо за покупку курса!<br>
            Вернитесь в Telegram бот для продолжения обучения.
        </div>
        <a href="https://t.me/{settings.BOT_USERNAME}" class="button">
            🤖 Вернуться в бот
        </a>
    </div>
</body>
</html>"""
    
    return HTMLResponse(content=success_html)


# ========================================
# ОБНОВЛЕННЫЙ FAIL ENDPOINT
# ========================================

@app.get("/webhook/robokassa/fail")
async def robokassa_fail(
    request: Request,
    OutSum: Optional[str] = Query(None),
    InvId: Optional[str] = Query(None)
):
    """Fail URL - страница ошибки (GET метод)"""
    logger.warning(f"❌ Robokassa fail (GET): InvId={InvId}")
    
    fail_html = f"""<!DOCTYPE html>
<html>
<head>
    <title>Ошибка оплаты</title>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
            background: linear-gradient(135deg, #ff6b6b 0%, #ee5a24 100%);
            color: white;
            text-align: center;
            padding: 50px 20px;
            margin: 0;
            min-height: 100vh;
            display: flex;
            justify-content: center;
            align-items: center;
        }}
        .container {{
            background: rgba(255,255,255,0.1);
            backdrop-filter: blur(10px);
            border-radius: 20px;
            padding: 40px;
            max-width: 500px;
            box-shadow: 0 8px 32px rgba(0,0,0,0.3);
        }}
        .error {{ font-size: 48px; margin-bottom: 20px; }}
        .title {{ font-size: 28px; margin-bottom: 20px; font-weight: 600; }}
        .info {{ font-size: 16px; margin-bottom: 30px; line-height: 1.6; }}
        .button {{
            color: white;
            padding: 12px 24px;
            text-decoration: none;
            border-radius: 25px;
            display: inline-block;
            margin: 5px;
            font-weight: 600;
        }}
        .retry {{ background: linear-gradient(45deg, #4CAF50, #45a049); }}
        .support {{ background: linear-gradient(45deg, #2196F3, #1976D2); }}
    </style>
</head>
<body>
    <div class="container">
        <div class="error">❌</div>
        <div class="title">Оплата не прошла</div>
        <div class="info">К сожалению, платеж не был завершен.</div>
        <div class="info">Попробуйте еще раз или обратитесь в поддержку.</div>
        
        <a href="https://t.me/{settings.BOT_USERNAME}" class="button retry">
            🔄 Попробовать снова
        </a>
        <a href="https://t.me/{settings.SUPPORT_CONTACT}" class="button support">
            💬 Поддержка
        </a>
    </div>
</body>
</html>"""
    
    return HTMLResponse(content=fail_html)


# Обновляем app.py - эндпоинт отслеживания

@app.get("/track/{ref_code}")
async def track_click(ref_code: str, request: Request):
    """Отслеживание переходов по реферальной ссылке с поддержкой user_telegram_id"""
    client_ip = request.client.host
    user_agent = request.headers.get("user-agent", "Unknown")
    
    async with AsyncSessionLocal() as session:
        from app.database.crud import ClickCRUD, ReferralHistoryCRUD, UserCRUD
        
        # Пытаемся определить пользователя по IP и user-agent
        # (это приблизительный метод, можно улучшить)
        user_telegram_id = None
        
        # TODO: Здесь можно добавить более сложную логику определения пользователя
        # Например, через cookies, fingerprinting и т.д.
        # Пока оставляем None для веб-кликов
        
        try:
            # Записываем клик
            await ClickCRUD.create_click(
                session=session,
                ref_code=ref_code,
                ip_address=client_ip,
                user_agent=user_agent,
                source=request.query_params.get("utm_source", "web"),
                user_telegram_id=user_telegram_id  # Пока None для веб-трафика
            )
            
            # Если удалось определить пользователя - логируем в историю
            if user_telegram_id:
                await ReferralHistoryCRUD.log_action(
                    session=session,
                    user_telegram_id=user_telegram_id,
                    ref_code=ref_code,
                    action_type="click",
                    ip_address=client_ip,
                    user_agent=user_agent
                )
                logger.info(f"✅ Web click with user_id {user_telegram_id} tracked for {ref_code}")
            else:
                logger.info(f"✅ Anonymous web click tracked for {ref_code}")
                
        except Exception as e:
            logger.error(f"❌ Error tracking click: {e}")
    
    # Редирект на лендинг
    landing_url = f"{settings.LANDING_URL}?ref={ref_code}"
    return RedirectResponse(url=landing_url, status_code=302)


# Дополнительный эндпоинт для связывания веб-кликов с пользователем
@app.post("/api/link-user-click")
async def link_user_click(request: Request):
    """
    Эндпоинт для связывания анонимного веб-клика с пользователем
    Вызывается из веб-интерфейса когда пользователь переходит в бот
    """
    try:
        data = await request.json()
        user_telegram_id = data.get("user_telegram_id")
        ref_code = data.get("ref_code")
        session_id = data.get("session_id")  # Уникальный ID сессии из браузера
        
        if not all([user_telegram_id, ref_code]):
            return {"error": "Missing required fields"}
        
        async with AsyncSessionLocal() as session:
            # Ищем последний анонимный клик с этим ref_code
            # и обновляем его user_telegram_id
            result = await session.execute(
                select(Click)
                .where(
                    Click.ref_code == ref_code,
                    Click.user_telegram_id.is_(None),
                    Click.created_at >= datetime.now() - timedelta(hours=1)  # Последний час
                )
                .order_by(Click.created_at.desc())
                .limit(1)
            )
            
            click = result.scalar_one_or_none()
            if click:
                # Обновляем клик
                await session.execute(
                    update(Click)
                    .where(Click.id == click.id)
                    .values(user_telegram_id=user_telegram_id)
                )
                
                # Логируем в историю
                await ReferralHistoryCRUD.log_action(
                    session=session,
                    user_telegram_id=user_telegram_id,
                    ref_code=ref_code,
                    action_type="click",
                    ip_address=click.ip_address,
                    user_agent=click.user_agent
                )
                
                await session.commit()
                logger.info(f"✅ Linked web click to user {user_telegram_id}")
                return {"status": "success"}
        
        return {"error": "Click not found"}
        
    except Exception as e:
        logger.error(f"❌ Error linking user click: {e}")
        return {"error": "Internal error"}


@app.get("/landing")
async def landing_page():
    """Простая лендинг страница"""
    return {"message": "Landing page - здесь будет ваша рекламная страница"}
    
    
# Добавьте в app/web/app.py простой тестовый эндпоинт:

@app.get("/test")
async def test_endpoint():
    """Простой тест"""
    print("TEST ENDPOINT CALLED")
    logger.info("TEST ENDPOINT CALLED")
    
    # Записываем в файл
    with open("/tmp/test_debug.log", "w") as f:
        f.write("Test endpoint called successfully\n")
    
    return {"status": "test works"}

@app.get("/webhook/test-robokassa")
async def test_robokassa_webhook(request: Request):
    """Тестовый webhook для диагностики"""
    print("TEST ROBOKASSA WEBHOOK CALLED")
    
    # Записываем все параметры
    with open("/tmp/test_robokassa.log", "w") as f:
        f.write(f"Method: {request.method}\n")
        f.write(f"URL: {request.url}\n")
        f.write(f"Query params: {dict(request.query_params)}\n")
        f.write(f"Headers: {dict(request.headers)}\n")
    
    return {"status": "robokassa test works"}

# И исправьте основной webhook (упростим):
@app.get("/webhook/robokassa/result")
@app.post("/webhook/robokassa/result") 
async def robokassa_result(request: Request):
    """Result URL webhook"""
    
    # ОБЯЗАТЕЛЬНО записываем в файл что функция вызвана
    with open("/tmp/webhook_called.log", "a") as f:
        f.write(f"WEBHOOK CALLED: {request.method} {request.url}\n")
    
    print("ROBOKASSA WEBHOOK CALLED")
    logger.info("ROBOKASSA WEBHOOK CALLED")
    
    return PlainTextResponse("OK")