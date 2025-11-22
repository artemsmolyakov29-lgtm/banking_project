"""
Django settings for banking_project project.
"""
import os
from pathlib import Path
from django.core.management.utils import get_random_secret_key
from dotenv import load_dotenv

load_dotenv()

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.getenv('SECRET_KEY', get_random_secret_key())

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = os.getenv('DEBUG', 'True').lower() == 'true'

ALLOWED_HOSTS = ['localhost', '127.0.0.1', '.render.com', '0.0.0.0']

# Application definition
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.humanize',

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
    'whitenoise.middleware.WhiteNoiseMiddleware',
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
                'banking_project.context_processors.project_context',
            ],
        },
    },
]

WSGI_APPLICATION = 'banking_project.wsgi.application'

# Database
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': os.getenv('DB_NAME', 'banking_db'),
        'USER': os.getenv('DB_USER', 'postgres'),
        'PASSWORD': os.getenv('DB_PASSWORD', ''),
        'HOST': os.getenv('DB_HOST', 'localhost'),
        'PORT': os.getenv('DB_PORT', '5432'),
        'OPTIONS': {
            'connect_timeout': 10,
        }
    }
}

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

# Internationalization
LANGUAGE_CODE = 'ru-ru'
TIME_ZONE = 'Europe/Moscow'
USE_I18N = True
USE_L10N = True
USE_TZ = True

# Static files (CSS, JavaScript, Images)
STATIC_URL = '/static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = BASE_DIR / 'staticfiles'

# Media files
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# Default primary key field type
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Custom user model
AUTH_USER_MODEL = 'users.User'

# Login URLs
LOGIN_REDIRECT_URL = 'dashboard'
LOGIN_URL = 'login'
LOGOUT_REDIRECT_URL = 'login'

# Email settings (for development)
EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'
if not DEBUG:
    EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'

DEFAULT_FROM_EMAIL = os.getenv('DEFAULT_FROM_EMAIL', 'noreply@banking-project.com')
EMAIL_HOST = os.getenv('EMAIL_HOST', 'smtp.gmail.com')
EMAIL_PORT = int(os.getenv('EMAIL_PORT', '587'))
EMAIL_USE_TLS = os.getenv('EMAIL_USE_TLS', 'True').lower() == 'true'
EMAIL_HOST_USER = os.getenv('EMAIL_HOST_USER', '')
EMAIL_HOST_PASSWORD = os.getenv('EMAIL_HOST_PASSWORD', '')

# Banking project settings
BANKING_SETTINGS = {
    'APP_NAME': 'Банковская система',
    'APP_VERSION': '1.0.0',
    'SUPPORT_EMAIL': 'support@banking-project.com',
    'DEFAULT_CURRENCY': 'RUB',
    'MIN_TRANSACTION_AMOUNT': 1,
    'MAX_TRANSACTION_AMOUNT': 10000000,
    'MIN_DEPOSIT_AMOUNT': 1000,
    'MAX_DEPOSIT_AMOUNT': 100000000,
    'MAX_CREDIT_AMOUNT': 50000000,
    'INTEREST_ACCRUAL_TIME': '06:00',
    'DAILY_TASK_TIME': '05:00',
    'REPORT_RETENTION_DAYS': 90,
    'BACKUP_RETENTION_DAYS': 30,
}

# Celery Configuration (опционально - для будущего использования)
CELERY_BROKER_URL = os.getenv('CELERY_BROKER_URL', 'redis://localhost:6379/0')
CELERY_RESULT_BACKEND = os.getenv('CELERY_RESULT_BACKEND', 'redis://localhost:6379/0')
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = 'Europe/Moscow'
CELERY_TASK_TIME_LIMIT = 1800
CELERY_TASK_TRACK_STARTED = True

# Security settings
CSRF_TRUSTED_ORIGINS = [
    'http://localhost:8000',
    'http://127.0.0.1:8000',
    'http://0.0.0.0:8000',
    'https://*.render.com'
]

# Security enhancements
if not DEBUG:
    SECURE_BROWSER_XSS_FILTER = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    SECURE_SSL_REDIRECT = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True

# НОВЫЕ НАСТРОЙКИ: Система отчетности
REPORT_SETTINGS = {
    'STORAGE_PATH': os.path.join(BASE_DIR, 'reports_storage'),
    'MAX_FILE_SIZE': 100 * 1024 * 1024,  # 100MB
    'ALLOWED_FORMATS': ['pdf', 'xlsx', 'csv', 'json', 'html'],
    'DEFAULT_FORMAT': 'html',
    'COMPRESSION_ENABLED': True,
    'AUTO_CLEANUP_DAYS': 30,
    'BATCH_SIZE': 1000,
    'ENABLE_SCHEDULING': True,
    'SCHEDULE_RETENTION_DAYS': 365,
}

# НОВЫЕ НАСТРОЙКИ: Аудит и мониторинг
AUDIT_SETTINGS = {
    'ENABLE_AUDIT_LOG': True,
    'LOG_RETENTION_DAYS': 365,
    'LOG_LEVEL': 'INFO',  # DEBUG, INFO, WARNING, ERROR
    'ENABLE_PERFORMANCE_LOGGING': True,
    'PERFORMANCE_THRESHOLD_MS': 1000,  # Логировать операции дольше 1 секунды
    'ENABLE_SECURITY_AUDIT': True,
    'AUTO_CLEANUP_ENABLED': True,
}

# НОВЫЕ НАСТРОЙКИ: Резервное копирование
BACKUP_SETTINGS = {
    'ENABLE_AUTO_BACKUP': False,
    'BACKUP_SCHEDULE': '0 2 * * *',  # Ежедневно в 2:00
    'BACKUP_RETENTION_DAYS': 30,
    'BACKUP_STORAGE_PATH': os.path.join(BASE_DIR, 'backups'),
    'ENABLE_CLOUD_BACKUP': False,
    'CLOUD_STORAGE_PROVIDER': 'aws',  # aws, google, azure
    'ENCRYPT_BACKUPS': True,
}

# НОВЫЕ НАСТРОЙКИ: Экспорт данных
EXPORT_SETTINGS = {
    'MAX_RECORDS_PER_EXPORT': 10000,
    'ENABLE_BATCH_EXPORT': True,
    'BATCH_SIZE': 1000,
    'COMPRESSION_ENABLED': True,
    'ALLOWED_FORMATS': ['json', 'csv', 'xlsx'],
    'DEFAULT_FORMAT': 'csv',
}

# Logging
LOGS_DIR = BASE_DIR / 'logs'
LOGS_DIR.mkdir(exist_ok=True)

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
        'django.server': {
            '()': 'django.utils.log.ServerFormatter',
            'format': '[{server_time}] {message}',
            'style': '{',
        },
        'audit': {
            'format': '{asctime} | {levelname} | {module} | {user} | {action} | {message}',
            'style': '{',
        }
    },
    'handlers': {
        'file': {
            'level': 'INFO',
            'class': 'logging.FileHandler',
            'filename': LOGS_DIR / 'banking.log',
            'formatter': 'verbose',
        },
        'error_file': {
            'level': 'ERROR',
            'class': 'logging.FileHandler',
            'filename': LOGS_DIR / 'errors.log',
            'formatter': 'verbose',
        },
        'audit_file': {
            'level': 'INFO',
            'class': 'logging.FileHandler',
            'filename': LOGS_DIR / 'audit.log',
            'formatter': 'audit',
        },
        'console': {
            'level': 'DEBUG' if DEBUG else 'INFO',
            'class': 'logging.StreamHandler',
            'formatter': 'simple',
        },
        'django.server': {
            'level': 'INFO',
            'class': 'logging.StreamHandler',
            'formatter': 'django.server',
        },
    },
    'loggers': {
        'django': {
            'handlers': ['file', 'console'],
            'level': 'INFO',
            'propagate': True,
        },
        'django.server': {
            'handlers': ['django.server'],
            'level': 'INFO',
            'propagate': False,
        },
        'banking': {
            'handlers': ['file', 'console', 'error_file'],
            'level': 'DEBUG',
            'propagate': False,
        },
        'users': {
            'handlers': ['file', 'console'],
            'level': 'INFO',
            'propagate': False,
        },
        'transactions': {
            'handlers': ['file', 'console', 'error_file'],
            'level': 'DEBUG',
            'propagate': False,
        },
        'deposits': {
            'handlers': ['file', 'console', 'error_file'],
            'level': 'DEBUG',
            'propagate': False,
        },
        'audit': {
            'handlers': ['audit_file', 'console'],
            'level': 'INFO',
            'propagate': False,
        },
        'reports': {
            'handlers': ['file', 'console', 'error_file'],
            'level': 'DEBUG',
            'propagate': False,
        },
    },
}

# НОВЫЕ НАСТРОЙКИ: Кэширование
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.redis.RedisCache',
        'LOCATION': os.getenv('REDIS_URL', 'redis://127.0.0.1:6379'),
        'OPTIONS': {
            'CLIENT_CLASS': 'django_redis.client.DefaultClient',
        }
    }
}

# НОВЫЕ НАСТРОЙКИ: Сессии
SESSION_ENGINE = 'django.contrib.sessions.backends.cached_db'
SESSION_COOKIE_AGE = 1209600  # 2 недели в секундах
SESSION_EXPIRE_AT_BROWSER_CLOSE = False

# НОВЫЕ НАСТРОЙКИ: Internationalization
FORMAT_MODULE_PATH = [
    'banking_project.formats',
]

# НОВЫЕ НАСТРОЙКИ: File uploads
FILE_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024  # 10MB
DATA_UPLOAD_MAX_MEMORY_SIZE = 50 * 1024 * 1024  # 50MB
DATA_UPLOAD_MAX_NUMBER_FIELDS = 1000

# НОВЫЕ НАСТРОЙКИ: Testing
TEST_RUNNER = 'django.test.runner.DiscoverRunner'

# НОВЫЕ НАСТРОЙКИ: Django Admin
ADMIN_SITE_HEADER = 'Администрирование Банковской системы'
ADMIN_SITE_TITLE = 'Банковская система'
ADMIN_INDEX_TITLE = 'Панель управления'

# НАСТРОЙКИ ДЛЯ РАЗРАБОТКИ
if DEBUG:
    # Отладочные инструменты
    INSTALLED_APPS += [
        'debug_toolbar',
    ]
    MIDDLEWARE.insert(0, 'debug_toolbar.middleware.DebugToolbarMiddleware')

    INTERNAL_IPS = [
        '127.0.0.1',
        'localhost',
    ]

    # Упрощенные настройки для разработки
    CACHES['default'] = {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
    }