"""
Django settings for ShadowPixel Resume Upload System.

This module contains comprehensive settings configuration with environment-based
configuration, security best practices, and production-ready defaults.

For more information on this file, see:
https://docs.djangoproject.com/en/5.0/topics/settings/

For the full list of settings and their values, see:
https://docs.djangoproject.com/en/5.0/ref/settings/
"""

import os
import sys
import logging 
from pathlib import Path
from typing import List, Dict, Any, Optional

try:
    from dotenv import load_dotenv
    load_dotenv()
    DOTENV_AVAILABLE = True
except ImportError:
    DOTENV_AVAILABLE = False
    print("Warning: python-dotenv not installed. Environment variables will be loaded from system only.")

try:
    import dj_database_url
    DJ_DATABASE_URL_AVAILABLE = True
except ImportError:
    DJ_DATABASE_URL_AVAILABLE = False
    if os.getenv("DATABASE_URL"):
        print("Warning: dj-database-url not installed but DATABASE_URL is set. Install with: pip install dj-database-url")


BASE_DIR = Path(__file__).resolve().parent.parent


DJANGO_ENV = os.getenv("DJANGO_ENV", "development").lower()
VALID_ENVIRONMENTS = {"development", "staging", "production", "testing"}

if DJANGO_ENV not in VALID_ENVIRONMENTS:
    raise ValueError(f"Invalid DJANGO_ENV '{DJANGO_ENV}'. Must be one of: {', '.join(VALID_ENVIRONMENTS)}")


IS_PRODUCTION = DJANGO_ENV == "production"
IS_STAGING = DJANGO_ENV == "staging" 
IS_DEVELOPMENT = DJANGO_ENV == "development"
IS_TESTING = DJANGO_ENV == "testing" or "test" in sys.argv or "pytest" in sys.modules


SECRET_KEY = os.getenv("DJANGO_SECRET_KEY")
if not SECRET_KEY:
    if IS_PRODUCTION:
        raise ValueError("DJANGO_SECRET_KEY environment variable is required in production")
    elif IS_STAGING:
        print("Warning: DJANGO_SECRET_KEY not set in staging environment")
        SECRET_KEY = "staging-key-change-before-production"
    else:
        SECRET_KEY = "dev-key-django-insecure-change-in-production"


DEBUG = os.getenv("DEBUG", "True" if IS_DEVELOPMENT else "False").lower() == "true"

if IS_PRODUCTION and DEBUG:
    raise ValueError("DEBUG cannot be True in production environment")

if IS_STAGING and DEBUG:
    print("Warning: DEBUG is True in staging environment")

# ALLOWED_HOSTS configuration
ALLOWED_HOSTS = [
    "127.0.0.1",
    "localhost", 
    "0.0.0.0",
    "testserver",
    "shadowpixel-3.onrender.com",
    ".onrender.com",
]

# Application definition
DJANGO_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.sitemaps',
    'django.contrib.humanize',
]

THIRD_PARTY_APPS = [
    'corsheaders',
    'rest_framework',
]

if not IS_TESTING:
    try:
        import django_extensions
        THIRD_PARTY_APPS.append('django_extensions')
    except ImportError:
        pass

LOCAL_APPS = [
    'backend',
]


if DEBUG and not IS_TESTING:
    try:
        import debug_toolbar
        THIRD_PARTY_APPS.append('debug_toolbar')
        DEBUG_TOOLBAR_AVAILABLE = True
    except ImportError:
        DEBUG_TOOLBAR_AVAILABLE = False

INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS


MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware', 
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

if DEBUG and not IS_TESTING and 'debug_toolbar' in INSTALLED_APPS:
    MIDDLEWARE.insert(-1, 'debug_toolbar.middleware.DebugToolbarMiddleware')
    INTERNAL_IPS = [
        "127.0.0.1",
        "localhost",
        "0.0.0.0",
    ]

ROOT_URLCONF = 'shadowpixel.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / "templates"],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.template.context_processors.media',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
            'debug': DEBUG,
        },
    },
]


WSGI_APPLICATION = 'shadowpixel.wsgi.application'


DATABASE_URL = os.getenv("DATABASE_URL")

if DATABASE_URL and DJ_DATABASE_URL_AVAILABLE:
   
    DATABASES = {
        'default': dj_database_url.parse(
            DATABASE_URL, 
            conn_max_age=600, 
            ssl_require=IS_PRODUCTION
        )
    }
elif IS_PRODUCTION:
    db_config = {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': os.getenv('DB_NAME', 'shadowpixel_prod'),
        'USER': os.getenv('DB_USER', 'shadowpixel'),
        'PASSWORD': os.getenv('DB_PASSWORD'),
        'HOST': os.getenv('DB_HOST', 'localhost'),
        'PORT': os.getenv('DB_PORT', '5432'),
        'CONN_MAX_AGE': 600,
        'OPTIONS': {
            'sslmode': 'require',
        },
    }

    required_db_vars = ['DB_PASSWORD']
    missing_vars = [var for var in required_db_vars if not os.getenv(var)]
    if missing_vars:
        raise ValueError(f"Missing required database environment variables: {', '.join(missing_vars)}")
    
    DATABASES = {'default': db_config}
    
elif IS_STAGING:
   
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.postgresql',
            'NAME': os.getenv('DB_NAME', 'shadowpixel_staging'),
            'USER': os.getenv('DB_USER', 'shadowpixel'),
            'PASSWORD': os.getenv('DB_PASSWORD', 'staging_password'),
            'HOST': os.getenv('DB_HOST', 'localhost'),
            'PORT': os.getenv('DB_PORT', '5432'),
            'CONN_MAX_AGE': 300,
        }
    }
else:
  
    db_name = ':memory:' if IS_TESTING else 'db.sqlite3'
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / db_name,
        }
    }

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
        'OPTIONS': {
            'min_length': 8,
        }
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

LANGUAGE_CODE = os.getenv('LANGUAGE_CODE', 'en-us')
TIME_ZONE = os.getenv('TIME_ZONE', 'UTC')
USE_I18N = True
USE_TZ = True

STATIC_URL = '/static/'
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / 'staticfiles'

STATICFILES_FINDERS = [
    'django.contrib.staticfiles.finders.FileSystemFinder',
    'django.contrib.staticfiles.finders.AppDirectoriesFinder',
]

if IS_PRODUCTION:
    STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'
elif IS_STAGING:
    STATICFILES_STORAGE = 'whitenoise.storage.CompressedStaticFilesStorage'

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'
MEDIA_ROOT.mkdir(exist_ok=True)

try:
    FILE_UPLOAD_MAX_MEMORY_SIZE = int(os.getenv('FILE_UPLOAD_MAX_MEMORY_SIZE', '2621440')) 
    DATA_UPLOAD_MAX_MEMORY_SIZE = int(os.getenv('DATA_UPLOAD_MAX_MEMORY_SIZE', '5242880')) 
except ValueError:
    print("Warning: Invalid file upload size settings, using defaults")
    FILE_UPLOAD_MAX_MEMORY_SIZE = 2621440
    DATA_UPLOAD_MAX_MEMORY_SIZE = 5242880

FILE_UPLOAD_MAX_MEMORY_SIZE = min(FILE_UPLOAD_MAX_MEMORY_SIZE, 10 * 1024 * 1024)  # Max 10MB
DATA_UPLOAD_MAX_MEMORY_SIZE = min(DATA_UPLOAD_MAX_MEMORY_SIZE, 20 * 1024 * 1024)  # Max 20MB

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
CORS_ALLOW_ALL_ORIGINS = os.getenv("CORS_ALLOW_ALL_ORIGINS", "False" if IS_PRODUCTION else "True").lower() == "true"

if not CORS_ALLOW_ALL_ORIGINS:
    CORS_ALLOWED_ORIGINS = []
    cors_origins_env = os.getenv("CORS_ALLOWED_ORIGINS", "")
    if cors_origins_env:
        CORS_ALLOWED_ORIGINS = [origin.strip() for origin in cors_origins_env.split(",") if origin.strip()]
    elif IS_DEVELOPMENT:
        CORS_ALLOWED_ORIGINS = [
            "http://127.0.0.1:3000",
            "http://localhost:3000",
            "http://127.0.0.1:8080",
            "http://localhost:8080",
        ]

CORS_ALLOW_CREDENTIALS = True
CORS_ALLOWED_HEADERS = [
    'accept',
    'accept-encoding',
    'authorization',
    'content-type',
    'dnt',
    'origin',
    'user-agent',
    'x-csrftoken',
    'x-requested-with',
]

# CORS methods
CORS_ALLOWED_METHODS = [
    'DELETE',
    'GET',
    'OPTIONS',
    'PATCH',
    'POST',
    'PUT',
]

# CSRF settings
CSRF_TRUSTED_ORIGINS = []
csrf_origins_env = os.getenv("CSRF_TRUSTED_ORIGINS", "")
if csrf_origins_env:
    CSRF_TRUSTED_ORIGINS = [origin.strip() for origin in csrf_origins_env.split(",") if origin.strip()]
elif IS_DEVELOPMENT:
    CSRF_TRUSTED_ORIGINS = [
        "http://127.0.0.1:8000",
        "http://localhost:8000",
        "http://0.0.0.0:8000",
    ]
elif IS_PRODUCTION and not CSRF_TRUSTED_ORIGINS:
    print("Warning: CSRF_TRUSTED_ORIGINS not configured for production")

# Security settings - Base configuration
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = 'DENY'

# Environment-specific security settings
if IS_PRODUCTION:
    # Production security settings (strict)
    SECURE_HSTS_SECONDS = 31536000  # 1 year
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    SECURE_SSL_REDIRECT = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    CSRF_COOKIE_HTTPONLY = True
    SESSION_COOKIE_HTTPONLY = True
    SECURE_REFERRER_POLICY = 'strict-origin-when-cross-origin'
    
    # Additional production security
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
    USE_TZ = True
    
elif IS_STAGING:
    # Staging security settings (relaxed for testing)
    SECURE_SSL_REDIRECT = os.getenv('SECURE_SSL_REDIRECT', 'False').lower() == 'true'
    SESSION_COOKIE_SECURE = SECURE_SSL_REDIRECT
    CSRF_COOKIE_SECURE = SECURE_SSL_REDIRECT
    CSRF_COOKIE_HTTPONLY = True
    SESSION_COOKIE_HTTPONLY = True
    
else:
    # Development settings (insecure for convenience)
    CSRF_COOKIE_SECURE = False
    SESSION_COOKIE_SECURE = False
    SECURE_SSL_REDIRECT = False

# Session configuration
try:
    SESSION_COOKIE_AGE = int(os.getenv('SESSION_COOKIE_AGE', '1209600'))  # 2 weeks
except ValueError:
    SESSION_COOKIE_AGE = 1209600

SESSION_SAVE_EVERY_REQUEST = True
SESSION_EXPIRE_AT_BROWSER_CLOSE = False
SESSION_COOKIE_NAME = 'shadowpixel_sessionid'

# Email configuration
EMAIL_BACKEND = os.getenv('EMAIL_BACKEND', 'django.core.mail.backends.console.EmailBackend')

if EMAIL_BACKEND == 'django.core.mail.backends.smtp.EmailBackend':
    EMAIL_HOST = os.getenv('EMAIL_HOST')
    EMAIL_PORT = int(os.getenv('EMAIL_PORT', '587'))
    EMAIL_USE_TLS = os.getenv('EMAIL_USE_TLS', 'True').lower() == 'true'
    EMAIL_USE_SSL = os.getenv('EMAIL_USE_SSL', 'False').lower() == 'true'
    EMAIL_HOST_USER = os.getenv('EMAIL_HOST_USER')
    EMAIL_HOST_PASSWORD = os.getenv('EMAIL_HOST_PASSWORD')
    DEFAULT_FROM_EMAIL = os.getenv('DEFAULT_FROM_EMAIL', 'noreply@shadowpixel.com')
    SERVER_EMAIL = os.getenv('SERVER_EMAIL', DEFAULT_FROM_EMAIL)
    
    # Validate SMTP settings in production
    if IS_PRODUCTION:
        required_email_vars = ['EMAIL_HOST', 'EMAIL_HOST_USER', 'EMAIL_HOST_PASSWORD']
        missing_email_vars = [var for var in required_email_vars if not os.getenv(var)]
        if missing_email_vars:
            print(f"Warning: Missing email configuration: {', '.join(missing_email_vars)}")

# Logging configuration
LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO' if IS_PRODUCTION else 'DEBUG')
LOG_DIR = BASE_DIR / 'logs'
LOG_DIR.mkdir(exist_ok=True)

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {process:d} {thread:d} {message}',
            'style': '{',
        },
        'simple': {
            'format': '{levelname} {asctime} {message}',
            'style': '{',
        },
        'detailed': {
            'format': '[{asctime}] {levelname} {name}: {message}',
            'style': '{',
        },
    },
    'filters': {
        'require_debug_false': {
            '()': 'django.utils.log.RequireDebugFalse',
        },
        'require_debug_true': {
            '()': 'django.utils.log.RequireDebugTrue',
        },
    },
    'handlers': {
        'console': {
            'level': 'DEBUG',
            'class': 'logging.StreamHandler',
            'formatter': 'simple' if DEBUG else 'detailed',
        },
        'file': {
            'level': 'INFO',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': LOG_DIR / 'django.log',
            'formatter': 'verbose',
            'maxBytes': 1024*1024*15,  # 15MB
            'backupCount': 10,
        },
        'mail_admins': {
            'level': 'ERROR',
            'filters': ['require_debug_false'],
            'class': 'django.utils.log.AdminEmailHandler',
            'include_html': True,
        }
    },
    'root': {
        'handlers': ['console'],
        'level': LOG_LEVEL,
    },
    'loggers': {
        'django': {
            'handlers': ['console', 'file'] if IS_PRODUCTION else ['console'],
            'level': 'INFO',
            'propagate': False,
        },
        'django.request': {
            'handlers': ['console', 'file', 'mail_admins'] if IS_PRODUCTION else ['console'],
            'level': 'ERROR',
            'propagate': False,
        },
        'backend': {
            'handlers': ['console', 'file'] if IS_PRODUCTION else ['console'],
            'level': LOG_LEVEL,
            'propagate': False,
        },
    },
}

# Cache configuration
CACHE_BACKEND = os.getenv('CACHE_BACKEND', 'locmem')

if CACHE_BACKEND == 'redis' and not IS_TESTING:
    CACHES = {
        'default': {
            'BACKEND': 'django.core.cache.backends.redis.RedisCache',
            'LOCATION': os.getenv('REDIS_URL', 'redis://127.0.0.1:6379/1'),
            'OPTIONS': {
                'CLIENT_CLASS': 'django_redis.client.DefaultClient',
            },
            'KEY_PREFIX': f'shadowpixel_{DJANGO_ENV}',
            'TIMEOUT': 300,
        }
    }
elif CACHE_BACKEND == 'memcached' and not IS_TESTING:
    CACHES = {
        'default': {
            'BACKEND': 'django.core.cache.backends.memcached.PyMemcacheCache',
            'LOCATION': os.getenv('MEMCACHED_URL', '127.0.0.1:11211'),
            'KEY_PREFIX': f'shadowpixel_{DJANGO_ENV}',
            'TIMEOUT': 300,
        }
    }
else:
    # Local memory cache (default for development/testing)
    CACHES = {
        'default': {
            'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
            'LOCATION': f'shadowpixel-{DJANGO_ENV}',
            'TIMEOUT': 300,
        }
    }

# Django REST Framework settings
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework.authentication.SessionAuthentication',
        'rest_framework.authentication.TokenAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 20,
    'DEFAULT_RENDERER_CLASSES': [
        'rest_framework.renderers.JSONRenderer',
    ] + (['rest_framework.renderers.BrowsableAPIRenderer'] if DEBUG else []),
    'DEFAULT_THROTTLE_CLASSES': [
        'rest_framework.throttling.AnonRateThrottle',
        'rest_framework.throttling.UserRateThrottle',
    ],
    'DEFAULT_THROTTLE_RATES': {
        'anon': '100/hour',
        'user': '1000/hour',
    },
}

# OpenAI Configuration with validation
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY','OPENAI_API_KEY=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')
if not OPENAI_API_KEY:
    if IS_PRODUCTION:
        print("Warning: OPENAI_API_KEY not set. AI features will be disabled in production.")
    elif IS_DEVELOPMENT:
        print("Info: OPENAI_API_KEY not set. AI features will be disabled in development.")

# GitHub API Configuration
GITHUB_TOKEN = os.getenv('GITHUB_TOKEN','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')
if not GITHUB_TOKEN and not IS_TESTING:
    print("Info: GITHUB_TOKEN not set. GitHub API will have rate limits.")

# Custom application settings
RESUME_SETTINGS = {
    'MAX_FILE_SIZE': int(os.getenv('RESUME_MAX_FILE_SIZE', '5242880')),  # 5MB
    'ALLOWED_EXTENSIONS': ['.pdf', '.doc', '.docx', '.txt'],
    'PROCESSING_TIMEOUT': int(os.getenv('RESUME_PROCESSING_TIMEOUT', '300')),  # 5 minutes
    'GITHUB_API_TIMEOUT': int(os.getenv('GITHUB_API_TIMEOUT', '15')),  # 15 seconds
    'MAX_REPOS_TO_ANALYZE': int(os.getenv('MAX_REPOS_TO_ANALYZE', '10')),
}

# Validate resume settings
if RESUME_SETTINGS['MAX_FILE_SIZE'] > 50 * 1024 * 1024:  # 50MB max
    print("Warning: RESUME_MAX_FILE_SIZE is very large, consider reducing it")

# Admin configuration
ADMIN_URL = os.getenv('ADMIN_URL', 'admin/')
if IS_PRODUCTION and ADMIN_URL == 'admin/':
    print("Warning: Using default admin URL in production. Consider changing it for security.")

# Sentry configuration for error tracking (production)
SENTRY_DSN = os.getenv('SENTRY_DSN')
if SENTRY_DSN and IS_PRODUCTION:
    try:
        import sentry_sdk
        from sentry_sdk.integrations.django import DjangoIntegration
        from sentry_sdk.integrations.logging import LoggingIntegration
        
        sentry_sdk.init(
            dsn=SENTRY_DSN,
            integrations=[
                DjangoIntegration(),
                LoggingIntegration(level=logging.INFO, event_level=logging.ERROR),
            ],
            traces_sample_rate=0.1,
            send_default_pii=False,
            environment=DJANGO_ENV,
        )
    except ImportError:
        print("Warning: Sentry DSN provided but sentry-sdk not installed")

# Testing configuration overrides
if IS_TESTING:
    # Fast password hashing for tests
    PASSWORD_HASHERS = [
        'django.contrib.auth.hashers.MD5PasswordHasher',
    ]
    
    # In-memory email backend for tests
    EMAIL_BACKEND = 'django.core.mail.backends.locmem.EmailBackend'
    
    # Disable migrations for faster tests
    class DisableMigrations:
        def __contains__(self, item):
            return True
        
        def __getitem__(self, item):
            return None
    
    MIGRATION_MODULES = DisableMigrations()
    
    # Disable cache for tests
    CACHES = {
        'default': {
            'BACKEND': 'django.core.cache.backends.dummy.DummyCache',
        }
    }

# Development tools configuration
if IS_DEVELOPMENT and not IS_TESTING:
    # Django Extensions configuration
    if 'django_extensions' in INSTALLED_APPS:
        SHELL_PLUS_PRINT_SQL = True
        SHELL_PLUS_PRINT_SQL_TRUNCATE = None

# Health check for critical settings
def validate_critical_settings():
    """Validate critical settings and warn about potential issues."""
    issues = []
    
    if not SECRET_KEY or len(SECRET_KEY) < 32:
        issues.append("SECRET_KEY is too short or missing")
    
    if IS_PRODUCTION and not ALLOWED_HOSTS:
        issues.append("ALLOWED_HOSTS must be configured for production")
    
    if IS_PRODUCTION and 'django.middleware.security.SecurityMiddleware' not in MIDDLEWARE:
        issues.append("SecurityMiddleware should be enabled in production")
    
    return issues

# Run validation
if not IS_TESTING:
    validation_issues = validate_critical_settings()
    if validation_issues:
        print("Configuration warnings:")
        for issue in validation_issues:
            print(f"  - {issue}")

# Export commonly used settings for easy access
__all__ = [
    'BASE_DIR',
    'DEBUG',
    'IS_PRODUCTION',
    'IS_DEVELOPMENT', 
    'IS_STAGING',
    'IS_TESTING',
    'DJANGO_ENV',
]
