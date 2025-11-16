import os
from pathlib import Path
from dotenv import load_dotenv
from django.core.management.utils import get_random_secret_key

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.getenv('SECRET_KEY', get_random_secret_key())

DEBUG = os.getenv('DEBUG', 'False') == 'True'

ALLOWED_HOSTS = ['localhost', '127.0.0.1', '.render.com', '0.0.0.0']

# НОВАЯ НАСТРОЙКА: Для продакшена
if not DEBUG:
    ALLOWED_HOSTS = ['your-production-domain.com', 'www.your-production-domain.com']

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.humanize',  # НОВОЕ: Для форматирования чисел

    # Custom apps
    'users.apps.UsersConfig',
    'clients.apps.ClientsConfig',
    'accounts.apps.AccountsConfig',
    'credits.apps.CreditsConfig',
    'deposits.apps.DepositsConfig',
    'cards.apps.CardsConfig',
    'transactions.apps.TransactionsConfig',
    'audit.apps.AuditConfig',
    'reports.apps.ReportsConfig',

    # Third party
    'widget_tweaks',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',  # НОВОЕ: Для статических файлов в продакшене
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'audit.middleware.AuditMiddleware',
]

ROOT_URLCONF = 'banking_project.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                # НОВЫЕ контекстные процессоры
                'banking_project.context_processors.project_context',
            ],
        },
    },
]

WSGI_APPLICATION = 'banking_project.wsgi.application'

# НАСТРОЙКИ БАЗЫ ДАННЫХ
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': os.getenv('DB_NAME', 'banking_db'),
        'USER': os.getenv('DB_USER', 'banking_user'),
        'PASSWORD': os.getenv('DB_PASSWORD', 'password'),
        'HOST': os.getenv('DB_HOST', 'localhost'),
        'PORT': os.getenv('DB_PORT', '5432'),
        # НОВЫЕ НАСТРОЙКИ: Оптимизация для PostgreSQL
        'CONN_MAX_AGE': 60,  # Подключение к базе живет 60 секунд
        'OPTIONS': {
            'connect_timeout': 10,
        }
    }
}

# Резервная база данных SQLite для разработки
if DEBUG and not all([os.getenv('DB_NAME'), os.getenv('DB_USER'), os.getenv('DB_PASSWORD')]):
    DATABASES['default'] = {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# НАСТРОЙКИ ЯЗЫКА И ВРЕМЕНИ
LANGUAGE_CODE = 'ru-ru'
TIME_ZONE = 'Europe/Moscow'
USE_I18N = True
USE_L10N = True
USE_TZ = True

# НАСТРОЙКИ СТАТИЧЕСКИХ ФАЙЛОВ
STATIC_URL = '/static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = BASE_DIR / 'staticfiles'

# НОВАЯ НАСТРОЙКА: Сжатие статических файлов
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# НАСТРОЙКИ ПОЛЬЗОВАТЕЛЯ
AUTH_USER_MODEL = 'users.User'

LOGIN_REDIRECT_URL = 'dashboard'
LOGOUT_REDIRECT_URL = 'login'
LOGIN_URL = 'login'

# НОВЫЕ НАСТРОЙКИ: Безопасность
if not DEBUG:
    SECURE_SSL_REDIRECT = True
    SECURE_HSTS_SECONDS = 31536000  # 1 year
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True

# НОВЫЕ НАСТРОЙКИ: Сессии
SESSION_COOKIE_AGE = 1209600  # 2 weeks
SESSION_SAVE_EVERY_REQUEST = True

# НОВЫЕ НАСТРОЙКИ: Логирование
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {process:d} {thread:d} {message}',
            'style': '{',
        },
        'simple': {
            'format': '{levelname} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'file': {
            'level': 'INFO',
            'class': 'logging.FileHandler',
            'filename': BASE_DIR / 'logs' / 'banking.log',
            'formatter': 'verbose',
        },
        'console': {
            'level': 'DEBUG',
            'class': 'logging.StreamHandler',
            'formatter': 'simple',
        },
        'error_file': {
            'level': 'ERROR',
            'class': 'logging.FileHandler',
            'filename': BASE_DIR / 'logs' / 'errors.log',
            'formatter': 'verbose',
        },
    },
    'loggers': {
        'django': {
            'handlers': ['file', 'console'],
            'level': 'INFO',
            'propagate': True,
        },
        'banking': {
            'handlers': ['file', 'console', 'error_file'],
            'level': 'DEBUG',
            'propagate': False,
        },
        'deposits': {
            'handlers': ['file', 'console', 'error_file'],
            'level': 'DEBUG',
            'propagate': False,
        },
        'transactions': {
            'handlers': ['file', 'console', 'error_file'],
            'level': 'DEBUG',
            'propagate': False,
        },
        'audit': {
            'handlers': ['file', 'console'],
            'level': 'INFO',
            'propagate': False,
        },
    },
}

# НОВЫЕ НАСТРОЙКИ: Email (для уведомлений)
EMAIL_BACKEND = os.getenv('EMAIL_BACKEND', 'django.core.mail.backends.console.EmailBackend')
EMAIL_HOST = os.getenv('EMAIL_HOST', 'smtp.gmail.com')
EMAIL_PORT = int(os.getenv('EMAIL_PORT', 587))
EMAIL_USE_TLS = os.getenv('EMAIL_USE_TLS', 'True') == 'True'
EMAIL_HOST_USER = os.getenv('EMAIL_HOST_USER', '')
EMAIL_HOST_PASSWORD = os.getenv('EMAIL_HOST_PASSWORD', '')
DEFAULT_FROM_EMAIL = os.getenv('DEFAULT_FROM_EMAIL', 'noreply@banking-project.com')

# НОВЫЕ НАСТРОЙКИ: Кэширование
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.redis.RedisCache',
        'LOCATION': os.getenv('REDIS_URL', 'redis://127.0.0.1:6379/1'),
        'OPTIONS': {
            'CLIENT_CLASS': 'django_redis.client.DefaultClient',
        }
    }
}

# Резервное кэширование для разработки
if DEBUG and not os.getenv('REDIS_URL'):
    CACHES['default'] = {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'unique-snowflake',
    }

# НОВЫЕ НАСТРОЙКИ: Настройки приложения
BANKING_SETTINGS = {
    'APP_NAME': 'Банковская система',
    'APP_VERSION': '1.0.0',
    'SUPPORT_EMAIL': 'support@banking-project.com',
    'MAX_DEPOSIT_AMOUNT': 100000000,  # 100 миллионов
    'MIN_DEPOSIT_AMOUNT': 1000,  # 1 тысяча
    'MAX_CREDIT_AMOUNT': 50000000,  # 50 миллионов
    'DEFAULT_CURRENCY': 'RUB',
    'INTEREST_ACCRUAL_TIME': '06:00',  # Время автоматического начисления процентов
    'DAILY_TASK_TIME': '05:00',  # Время выполнения ежедневных задач
    'REPORT_RETENTION_DAYS': 90,  # Хранение отчетов (дней)
    'BACKUP_RETENTION_DAYS': 30,  # Хранение бэкапов (дней)
}

# НОВАЯ НАСТРОЙКА: Celery (для асинхронных задач)
CELERY_BROKER_URL = os.getenv('CELERY_BROKER_URL', 'redis://localhost:6379/0')
CELERY_RESULT_BACKEND = os.getenv('CELERY_RESULT_BACKEND', 'redis://localhost:6379/0')
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = TIME_ZONE

# Создаем папку для логов, если её нет
os.makedirs(BASE_DIR / 'logs', exist_ok=True)