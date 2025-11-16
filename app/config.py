"""
================================================================================
ФАЙЛ КОНФИГУРАЦИИ TELEGRAM-БОТА
================================================================================

НАЗНАЧЕНИЕ:
    Этот файл содержит ВСЕ настройки бота - токены, ID админов, цены,
    настройки базы данных и т.д. Все параметры берутся из файла .env

ЧТО МОЖНО МЕНЯТЬ:
    ✅ В файле .env можно менять:
       - BOT_TOKEN - токен бота от @BotFather
       - ADMIN_ID - ID главного администратора
       - ADMIN_IDS - дополнительные админы (через запятую)
       - SUPPORT_ID - ID куда приходят вопросы от пользователей
       - ONBOARDING_COURSE_PRICE - цена курса (в рублях)
       - COMMISSION_PERCENT - процент комиссии партнера
       - ROBOKASSA_TEST_MODE - True/False (тестовый режим оплаты)
       - ONBOARDING_ENABLED - True/False (включить онбординг)
       - MIN_WITHDRAWAL - минимальная сумма вывода

    ❌ НЕ МЕНЯЙТЕ в этом файле:
       - Структуру класса Settings
       - Названия переменных (может сломать код)
       - Методы и функции

ОСНОВНЫЕ ФУНКЦИИ:
    - settings - главный объект с настройками
    - get_admin_ids() - получить список всех админов
    - is_admin(user_id) - проверить админ ли пользователь
    - get_course_video_id(lesson_number) - получить ID видео урока
    - get_payment_amount() - получить стоимость курса
    - get_commission_amount() - рассчитать комиссию

СВЯЗЬ С ДРУГИМИ ФАЙЛАМИ:
    - Использует .env файл (ОБЯЗАТЕЛЬНО должен существовать)
    - Импортируется в bot.py, handlers, services

ВАЖНО:
    После изменения .env файла нужно ПЕРЕЗАПУСТИТЬ бота!

================================================================================
"""

from pydantic_settings import BaseSettings
from typing import Optional, Dict, List


class Settings(BaseSettings):
    """
    Класс настроек бота. Автоматически загружает все переменные из .env файла

    Все параметры ниже берутся из файла .env в корне проекта
    """

    # ============================================================================
    # TELEGRAM НАСТРОЙКИ
    # ============================================================================
    BOT_TOKEN: str              # Токен бота (от @BotFather)
    BOT_USERNAME: str           # Username бота (например: @mybot)

    # ============================================================================
    # AI / DEEPSEEK
    # ============================================================================
    DEEPSEEK_API_KEY: str       # API ключ для DeepSeek AI (автоответы)

    # ============================================================================
    # АДМИНИСТРАТОРЫ
    # ============================================================================
    ADMIN_ID: int               # ID главного администратора (обязательно)
    ADMIN_IDS: str = ""         # Дополнительные админы через запятую (например: 123,456,789)

    # ============================================================================
    # ТЕХПОДДЕРЖКА
    # ============================================================================
    SUPPORT_ID: int             # ID куда приходят сообщения от пользователей
    MALE_ADMIN_ID: int          # ID админа для мужчин
    FEMALE_ADMIN_ID: int        # ID админа для женщин

    # ============================================================================
    # БАЗА ДАННЫХ
    # ============================================================================
    DATABASE_URL: str           # URL подключения к PostgreSQL
    REDIS_URL: str              # URL подключения к Redis

    # ============================================================================
    # SSH ТУННЕЛЬ (для удаленного доступа к БД)
    # ============================================================================
    SSH_TUNNEL_ENABLED: bool = False    # Включить SSH туннель (True/False)
    SSH_HOST: str = ""                  # IP сервера
    SSH_PORT: int = 22                  # Порт SSH
    SSH_USERNAME: str = ""              # Логин SSH
    SSH_PASSWORD: str = ""              # Пароль SSH

    # ============================================================================
    # GOOGLE SHEETS (для экспорта данных)
    # ============================================================================
    GOOGLE_SHEETS_KEY: str      # API ключ Google
    SPREADSHEET_ID: str         # ID таблицы Google Sheets
    OAuth_client: str           # OAuth client для Google
    GOOGLE_TOKEN_FILE: str      # Путь к файлу токена

    # ============================================================================
    # ОСНОВНЫЕ НАСТРОЙКИ ПРИЛОЖЕНИЯ
    # ============================================================================
    DOMAIN: str                 # Домен сайта (например: https://mybot.ru)
    LANDING_URL: str            # URL лендинга
    SUPPORT_CONTACT: str        # Контакт поддержки (например: @support)
    MIN_WITHDRAWAL: str         # Минимальная сумма вывода (например: "1000")
    CURRENCY: str               # Валюта (RUB, USD и т.д.)
    COMMISSION_PERCENT: float = 20.0  # Процент комиссии партнера (по умолчанию 20%)

    # ============================================================================
    # ROBOKASSA - ПЛАТЕЖНАЯ СИСТЕМА
    # ============================================================================
    ROBOKASSA_MERCHANT_LOGIN: str       # Логин магазина в Robokassa

    # Продакшн пароли (реальные платежи)
    ROBOKASSA_PASSWORD_1: str           # Пароль #1
    ROBOKASSA_PASSWORD_2: str           # Пароль #2

    # Тестовые пароли (для тестирования)
    ROBOKASSA_TEST_PASSWORD_1: str      # Тестовый пароль #1
    ROBOKASSA_TEST_PASSWORD_2: str      # Тестовый пароль #2

    ROBOKASSA_TEST_MODE: bool = True    # Тестовый режим (True - тест, False - продакшн)
    ROBOKASSA_RESULT_URL: str           # URL для результата оплаты
    ROBOKASSA_SUCCESS_URL: str          # URL успешной оплаты
    ROBOKASSA_FAIL_URL: str             # URL неудачной оплаты

    # Legacy настройки (для совместимости)
    PAYMENT_PROVIDER: str = "Robokassa"
    PAYMENT_API_KEY: str = ""
    PAYMENT_WEBHOOK_SECRET: str = ""

    # ============================================================================
    # БЕЗОПАСНОСТЬ
    # ============================================================================
    SECRET_KEY: str             # Секретный ключ приложения
    ALLOWED_IPS: list[str] = [] # Разрешенные IP адреса

    # ============================================================================
    # ОНБОРДИНГ (обучение новых пользователей)
    # ============================================================================
    ONBOARDING_ENABLED: bool = True             # Включить онбординг (True/False)
    ONBOARDING_COURSE_PRICE: float = 4700.0     # Цена курса в рублях
    ONBOARDING_COURSE_CURRENCY: str = "руб."    # Валюта курса
    ONBOARDING_TOTAL_LESSONS: int = 10          # Количество уроков
    ONBOARDING_MOCK_PAYMENT: bool = False       # Фейковая оплата для теста

    # ============================================================================
    # FILE ID ВИДЕО (берутся из Telegram после загрузки)
    # ============================================================================
    # Основные видео
    ONBOARDING_INTRO_VIDEO_ID: str      # Вступительное видео
    KRUG_VIDEO_ID: str                  # Круглое видео
    VIDEO2_ID: str
    VIDEO3_ID: str
    VIDEO7_ID: str

    # Уроки курса (lesson_1, lesson_2 и т.д.)
    lesson_1: str
    lesson_2: str
    lesson_3: str
    lesson_4: str
    lesson_5: str

    # Круглые видео для дожима (мотивация к покупке)
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

    # Словарь видео уроков (используется в коде)
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

    # ============================================================================
    # НАСТРОЙКИ ПОДДЕРЖКИ
    # ============================================================================
    ONBOARDING_SUPPORT_URL: str = "https://t.me/FFarkhadov"  # Ссылка на поддержку

    # ============================================================================
    # FILE ID ДОКУМЕНТОВ (оферта, политика и т.д.)
    # ============================================================================
    DOC_OFERTA_FILE_ID: str             # Договор оферты
    DOC_PRIVACY_FILE_ID: str            # Политика конфиденциальности
    DOC_USER_AGREEMENT_FILE_ID: str     # Пользовательское соглашение
    DOC_PERSONAL_DATA_FILE_ID: str      # Согласие на обработку данных

    # ============================================================================
    # FILE ID СКРИНШОТОВ (для кнопки "Что я приобретаю")
    # ============================================================================
    SCREENSHOT_1_FILE_ID: str
    SCREENSHOT_2_FILE_ID: str
    SCREENSHOT_3_FILE_ID: str
    SCREENSHOT_4_FILE_ID: str

    # ============================================================================
    # ВСПОМОГАТЕЛЬНЫЕ МЕТОДЫ
    # ============================================================================

    @property
    def admin_ids_list(self) -> List[int]:
        """
        Возвращает список ID ВСЕХ админов (главный + дополнительные)

        Returns:
            List[int]: Список ID администраторов
        """
        admin_ids = []

        # Добавляем главного админа
        admin_ids.append(self.ADMIN_ID)

        # Парсим дополнительных админов из строки ADMIN_IDS
        if self.ADMIN_IDS:
            try:
                additional_ids = [int(id.strip()) for id in self.ADMIN_IDS.split(',') if id.strip()]
                admin_ids.extend(additional_ids)
            except ValueError as e:
                import logging
                logger = logging.getLogger(__name__)
                logger.error(f"❌ Error parsing ADMIN_IDS: {e}")

        # Удаляем дубликаты и возвращаем
        return list(set(admin_ids))

    def is_admin(self, user_id: int) -> bool:
        """
        Проверяет является ли пользователь администратором

        Args:
            user_id: Telegram ID пользователя

        Returns:
            bool: True если админ, False если нет
        """
        return user_id in self.admin_ids_list

    class Config:
        """Настройки Pydantic для загрузки из .env"""
        env_file = ".env"
        env_file_encoding = "utf-8"


# ============================================================================
# СОЗДАНИЕ ГЛОБАЛЬНОГО ОБЪЕКТА НАСТРОЕК
# ============================================================================
settings = Settings()


# ============================================================================
# ПУБЛИЧНЫЕ ФУНКЦИИ ДЛЯ РАБОТЫ С НАСТРОЙКАМИ
# ============================================================================

def get_admin_ids() -> List[int]:
    """
    Получить список всех администраторов

    Returns:
        List[int]: Список Telegram ID админов
    """
    return settings.admin_ids_list


def is_admin(user_id: int) -> bool:
    """
    Проверить является ли пользователь администратором

    Args:
        user_id: Telegram ID пользователя

    Returns:
        bool: True если пользователь админ
    """
    return settings.is_admin(user_id)


def get_course_video_id(lesson_number: int) -> str:
    """
    Получить file_id видео урока по номеру

    Args:
        lesson_number: Номер урока (1-10)

    Returns:
        str: File ID видео из Telegram
    """
    return settings.ONBOARDING_COURSE_VIDEO_IDS.get(str(lesson_number), "")


def is_onboarding_enabled() -> bool:
    """
    Проверить включен ли онбординг (обучение новых пользователей)

    Returns:
        bool: True если онбординг включен
    """
    return settings.ONBOARDING_ENABLED


def get_payment_amount() -> float:
    """
    Получить стоимость курса

    Returns:
        float: Цена курса в рублях
    """
    return settings.ONBOARDING_COURSE_PRICE


def get_commission_amount(sale_amount: float = None) -> float:
    """
    Рассчитать сумму комиссии партнера

    Args:
        sale_amount: Сумма продажи (если None - берется цена курса)

    Returns:
        float: Сумма комиссии в рублях
    """
    if sale_amount is None:
        sale_amount = settings.ONBOARDING_COURSE_PRICE
    return sale_amount * settings.COMMISSION_PERCENT / 100


def get_monthly_income_example(sales_count: int = 10) -> float:
    """
    Рассчитать примерный месячный доход для мотивации

    Args:
        sales_count: Количество продаж в месяц

    Returns:
        float: Примерный доход в рублях
    """
    commission = get_commission_amount()
    return commission * sales_count
