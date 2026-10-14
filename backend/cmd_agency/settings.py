import os
from datetime import timedelta
from pathlib import Path
from urllib.parse import urlsplit

import dj_database_url
from django.core.exceptions import ImproperlyConfigured
from django.utils.csp import CSP

BASE_DIR = Path(__file__).resolve().parent.parent
FRONTEND_DIR = BASE_DIR.parent / 'frontend' / 'dist'

DEBUG = os.environ.get('DEBUG', 'True') == 'True'
SECRET_KEY = os.environ.get('SECRET_KEY') or ('django-insecure-local-development-only' if DEBUG else None)
if not SECRET_KEY:
    raise ImproperlyConfigured('Set the SECRET_KEY environment variable.')

ALLOWED_HOSTS = os.environ.get('ALLOWED_HOSTS', '*').split(',')
CSRF_TRUSTED_ORIGINS = [o for o in os.environ.get('CSRF_TRUSTED_ORIGINS', '').split(',') if o]
if not DEBUG:
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
    SESSION_COOKIE_SECURE = CSRF_COOKIE_SECURE = True
    SECURE_SSL_REDIRECT = os.environ.get('SECURE_SSL_REDIRECT', 'True') == 'True'
    SECURE_HSTS_SECONDS = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True


INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'rest_framework',
    'rest_framework_simplejwt',
    'rest_framework_simplejwt.token_blacklist',
    'corsheaders',
    'api',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.locale.LocaleMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'django.middleware.csp.ContentSecurityPolicyMiddleware',
    'api.security.PermissionsPolicyMiddleware',
    'api.telegram.ReminderMiddleware',
]

CORS_ALLOW_ALL_ORIGINS = DEBUG

ROOT_URLCONF = 'cmd_agency.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [FRONTEND_DIR] if FRONTEND_DIR.exists() else [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'cmd_agency.wsgi.application'


DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}

if os.environ.get('DATABASE_URL'):
    DATABASES['default'] = dj_database_url.config(
        default=os.environ.get('DATABASE_URL'),
        conn_max_age=600,
        conn_health_checks=True,
    )
    if DATABASES['default'].get('HOST') not in (None, '', 'localhost', '127.0.0.1'):
        DATABASES['default'].setdefault('OPTIONS', {})['sslmode'] = 'require'
    if '-pooler' in (DATABASES['default'].get('HOST') or ''):
        DATABASES['default']['DISABLE_SERVER_SIDE_CURSORS'] = True

elif os.environ.get('POSTGRES_DB'):
    DATABASES['default'] = {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': os.environ.get('POSTGRES_DB', 'cmd_agency'),
        'USER': os.environ.get('POSTGRES_USER', 'postgres'),
        'PASSWORD': os.environ.get('POSTGRES_PASSWORD', ''),
        'HOST': os.environ.get('POSTGRES_HOST', 'localhost'),
        'PORT': os.environ.get('POSTGRES_PORT', '5432'),
    }


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


LANGUAGE_CODE = 'en'
LANGUAGES = [('en', 'English'), ('ru', 'Русский')]
LOCALE_PATHS = [BASE_DIR / 'locale']

TIME_ZONE = 'UTC'

USE_I18N = True

USE_TZ = True


STATIC_URL = 'static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_STORAGE = 'whitenoise.storage.CompressedStaticFilesStorage'

if FRONTEND_DIR.exists():
    STATICFILES_DIRS = [FRONTEND_DIR]


AUTH_USER_MODEL = 'api.User'

CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.filebased.FileBasedCache',
        'LOCATION': os.environ.get('CACHE_DIR', '/tmp/cmd-agency-cache'),
    }
}

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': ('rest_framework_simplejwt.authentication.JWTAuthentication',),
    'DEFAULT_PERMISSION_CLASSES': ('rest_framework.permissions.IsAuthenticated',),
}

SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=30),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=7),
    'ROTATE_REFRESH_TOKENS': True,
    'BLACKLIST_AFTER_ROTATION': True,
    'UPDATE_LAST_LOGIN': True,
}

R2_ACCOUNT_ID = os.environ.get('R2_ACCOUNT_ID', '')
R2_ACCESS_KEY_ID = os.environ.get('R2_ACCESS_KEY_ID', '')
R2_SECRET_ACCESS_KEY = os.environ.get('R2_SECRET_ACCESS_KEY', '')
R2_BUCKET = os.environ.get('R2_BUCKET', '')
R2_ENDPOINT_URL = os.environ.get('R2_ENDPOINT_URL') or (
    f'https://{R2_ACCOUNT_ID}.r2.cloudflarestorage.com' if R2_ACCOUNT_ID else ''
)
VIDEO_MAX_UPLOAD_BYTES = int(os.environ.get('VIDEO_MAX_UPLOAD_BYTES', 500 * 1000**2))
VIDEO_STORAGE_LIMIT_BYTES = int(os.environ.get('VIDEO_STORAGE_LIMIT_BYTES', 9 * 1000**3))
VIDEO_PLAYBACK_URL_SECONDS = int(os.environ.get('VIDEO_PLAYBACK_URL_SECONDS', 3600))
VIDEO_PART_URL_SECONDS = int(os.environ.get('VIDEO_PART_URL_SECONDS', 3600))
CHAT_MAX_ATTACHMENT_BYTES = int(os.environ.get('CHAT_MAX_ATTACHMENT_BYTES', 100 * 1000**2))

EMAIL_HOST = os.environ.get('EMAIL_HOST', '')
EMAIL_BACKEND = os.environ.get('EMAIL_BACKEND') or (
    'django.core.mail.backends.smtp.EmailBackend' if EMAIL_HOST else 'django.core.mail.backends.console.EmailBackend'
)
EMAIL_PORT = int(os.environ.get('EMAIL_PORT', 587))
EMAIL_HOST_USER = os.environ.get('EMAIL_HOST_USER', '')
EMAIL_HOST_PASSWORD = os.environ.get('EMAIL_HOST_PASSWORD', '')
EMAIL_USE_TLS = os.environ.get('EMAIL_USE_TLS', 'True') == 'True'
DEFAULT_FROM_EMAIL = os.environ.get('DEFAULT_FROM_EMAIL', 'CMD Agency <no-reply@cmd-agency.local>')
APP_BASE_URL = os.environ.get('APP_BASE_URL', 'http://localhost:5173')

TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN', '')
TELEGRAM_BOT_USERNAME = os.environ.get('TELEGRAM_BOT_USERNAME', '').lstrip('@')
TELEGRAM_WEBHOOK_SECRET = os.environ.get('TELEGRAM_WEBHOOK_SECRET', '')
DISPLAY_TIME_ZONE = os.environ.get('DISPLAY_TIME_ZONE', 'Asia/Tashkent')


_r2 = urlsplit(R2_ENDPOINT_URL)
_files = [CSP.SELF, 'https://*.r2.cloudflarestorage.com'] + ([f'{_r2.scheme}://{_r2.netloc}'] if _r2.netloc else [])
SECURE_CSP = {
    'default-src': [CSP.SELF],
    'script-src': [CSP.SELF],
    'style-src': [CSP.SELF, CSP.UNSAFE_INLINE],
    'img-src': [*_files, 'data:', 'blob:', 'https://images.unsplash.com'],
    'media-src': [*_files, 'blob:'],
    'connect-src': _files,
    'font-src': [CSP.SELF, 'data:'],
    'object-src': [CSP.NONE],
    'base-uri': [CSP.SELF],
    'form-action': [CSP.SELF],
    'frame-ancestors': [CSP.NONE],
}

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {'console': {'class': 'logging.StreamHandler'}},
    'loggers': {
        'api.video': {'handlers': ['console'], 'level': 'INFO'},
        'api.telegram': {'handlers': ['console'], 'level': 'INFO'},
        'django.security': {'handlers': ['console'], 'level': 'WARNING'},
        'django.request': {'handlers': ['console'], 'level': 'WARNING'},
    },
}
