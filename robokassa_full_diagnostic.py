"""
Скрипт для тестирования webhook Robokassa
"""
import hashlib
import requests

# Ваши настройки
MERCHANT_LOGIN = "Mamedparner"
TEST_PASSWORD_2 = "eU96nuy5LNV21WRgDOtO"  # Password #2 для проверки
WEBHOOK_URL = "https://mpartner.insta-bot.ru/webhook/robokassa/result"

# Тестовые данные
out_sum = 100.00
inv_id = "1753121000"

print("🧪 ТЕСТИРУЕМ WEBHOOK ROBOKASSA")
print("="*50)

# Создаем правильную подпись для проверки
# Формула для Result URL: OutSum:InvId:Password2
amount_str = f"{out_sum:.2f}"
signature_string = f"{amount_str}:{inv_id}:{TEST_PASSWORD_2}"
signature = hashlib.md5(signature_string.encode('utf-8')).hexdigest().upper()

print(f"OutSum: {amount_str}")
print(f"InvId: {inv_id}")
print(f"Строка подписи: {signature_string}")
print(f"Подпись: {signature}")
print()

# Формируем URL с параметрами
test_url = f"{WEBHOOK_URL}?OutSum={amount_str}&InvId={inv_id}&SignatureValue={signature}"

print("🌐 Тестовый URL:")
print(test_url)
print()

# Отправляем запрос
print("📡 Отправляем GET запрос...")
try:
    response = requests.get(test_url, timeout=10)
    
    print(f"Статус: {response.status_code}")
    print(f"Ответ: {response.text}")
    
    if response.status_code == 200:
        print("✅ Webhook работает!")
    else:
        print("❌ Ошибка в webhook")
        
except requests.exceptions.RequestException as e:
    print(f"❌ Ошибка соединения: {e}")

print("\n" + "="*50)
print("📋 ЧТО ПРОВЕРИТЬ:")
print("1. Запущен ли бот (должен быть запущен)")
print("2. Есть ли в БД платеж с InvId =", inv_id)
print("3. Изменился ли статус пользователя в логах бота")
print("4. Появились ли новые записи в логах webhook'а")