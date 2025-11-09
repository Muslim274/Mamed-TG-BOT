"""
Обновленная конфигурация с поддержкой тестовых паролей Robokassa
app/config.py
"""
from pydantic_settings import BaseSettings
from typing import Optional, Dict, List


class Settings(BaseSettings):
    # Telegram
    BOT_TOKEN: str
    BOT_USERNAME: str
    
    # DeepSeek AI
    DEEPSEEK_API_KEY: str
    
    ADMIN_ID: int
    ADMIN_IDS: str = ""  # Строка с ID админов через запятую
    
    # ID админов технической поддержки по полу
    MALE_ADMIN_ID: int 
    FEMALE_ADMIN_ID: int 
    
    # Database
    DATABASE_URL: str
    REDIS_URL: str
    
    # Google Sheets
    GOOGLE_SHEETS_KEY: str
    SPREADSHEET_ID: str
    
    OAuth_client: str
    GOOGLE_TOKEN_FILE: str
    
    
    # App Settings
    DOMAIN: str
    LANDING_URL: str
    SUPPORT_CONTACT: str
    MIN_WITHDRAWAL: str
    CURRENCY: str
    COMMISSION_PERCENT: float = 20.0
    
    # ✅ ROBOKASSA С ПОДДЕРЖКОЙ ТЕСТОВЫХ ПАРОЛЕЙ
    ROBOKASSA_MERCHANT_LOGIN: str
    
    # Продакшн пароли
    ROBOKASSA_PASSWORD_1: str
    ROBOKASSA_PASSWORD_2: str
    
    # ✅ ТЕСТОВЫЕ ПАРОЛИ
    ROBOKASSA_TEST_PASSWORD_1: str
    ROBOKASSA_TEST_PASSWORD_2: str
    
    ROBOKASSA_TEST_MODE: bool = True
    ROBOKASSA_RESULT_URL: str
    ROBOKASSA_SUCCESS_URL: str
    ROBOKASSA_FAIL_URL: str
    
    # Payment (оставляем для совместимости)
    PAYMENT_PROVIDER: str = "Robokassa"
    PAYMENT_API_KEY: str = ""
    PAYMENT_WEBHOOK_SECRET: str = ""
    
    # Security
    SECRET_KEY: str
    ALLOWED_IPS: list[str] = []
    
    # Onboarding Settings
    ONBOARDING_ENABLED: bool = True
    ONBOARDING_COURSE_PRICE: float = 4700.0
    ONBOARDING_COURSE_CURRENCY: str = "руб."
    ONBOARDING_TOTAL_LESSONS: int = 10
    ONBOARDING_MOCK_PAYMENT: bool = False
    
    # Video file IDs
    ONBOARDING_INTRO_VIDEO_ID: str
    KRUG_VIDEO_ID: str
    VIDEO2_ID: str
    VIDEO3_ID: str
    VIDEO7_ID: str
    #VIDEO4_ID: str
    
    lesson_1: str
    lesson_2: str
    lesson_3: str
    lesson_4: str
    lesson_5: str
    
    # КРУГЛЫЕ ВИДЕОДЛЯ ДОЖИМА 
    
    K_VIDEO_ID1: str
    K_VIDEO_ID2: str
    K_VIDEO_ID3: str
    K_VIDEO_ID4: str
    K_VIDEO_ID5: str
    K_VIDEO_ID6: str
    K_VIDEO_ID7: str
    K_VIDEO_ID8: str
    K_VIDEO_ID9: str
    K_VIDEO_ID10: str

    ONBOARDING_COURSE_VIDEO_IDS: Dict[str, str] = {
        "1": "BAACAgIAAxkBAAI...",
        "2": "BAACAgIAAxkBAAI...",
        "3": "BAACAgIAAxkBAAI...",
        "4": "BAACAgIAAxkBAAI...",
        "5": "BAACAgIAAxkBAAI...",
        "6": "BAACAgIAAxkBAAI...",
        "7": "BAACAgIAAxkBAAI...",
        "8": "BAACAgIAAxkBAAI...",
        "9": "BAACAgIAAxkBAAI...",
        "10": "BAACAgIAAxkBAAI..."
    }
    
    # Настройки поддержки для онбординга
    ONBOARDING_SUPPORT_URL: str = "https://t.me/FFarkhadov"
    
    @property
    def admin_ids_list(self) -> List[int]:
        """Возвращает список ID всех админов"""
        admin_ids = []
        
        # Добавляем основного админа
        admin_ids.append(self.ADMIN_ID)
        
        # Добавляем дополнительных админов из ADMIN_IDS
        if self.ADMIN_IDS:
            try:
                additional_ids = [int(id.strip()) for id in self.ADMIN_IDS.split(',') if id.strip()]
                admin_ids.extend(additional_ids)
            except ValueError as e:
                import logging
                logger = logging.getLogger(__name__)
                logger.error(f"❌ Error parsing ADMIN_IDS: {e}")
        
        # Удаляем дубликаты и возвращаем список
        return list(set(admin_ids))
    
    def is_admin(self, user_id: int) -> bool:
        """Проверка является ли пользователь админом"""
        return user_id in self.admin_ids_list
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()


# Функции для работы с админами
def get_admin_ids() -> List[int]:
    """Получение списка всех админов"""
    return settings.admin_ids_list


def is_admin(user_id: int) -> bool:
    """Проверка является ли пользователь админом"""
    return settings.is_admin(user_id)


# Остальные функции остаются без изменений
def get_course_video_id(lesson_number: int) -> str:
    """Получение file_id видео урока"""
    return settings.ONBOARDING_COURSE_VIDEO_IDS.get(str(lesson_number), "")


def is_onboarding_enabled() -> bool:
    """Проверка включен ли онбординг"""
    return settings.ONBOARDING_ENABLED


def get_payment_amount() -> float:
    """Получение стоимости курса"""
    return settings.ONBOARDING_COURSE_PRICE


def get_commission_amount(sale_amount: float = None) -> float:
    """Расчет суммы комиссии"""
    if sale_amount is None:
        sale_amount = settings.ONBOARDING_COURSE_PRICE
    return sale_amount * settings.COMMISSION_PERCENT / 100


def get_monthly_income_example(sales_count: int = 10) -> float:
    """Пример месячного дохода для мотивации"""
    commission = get_commission_amount()
    return commission * sales_count