from pathlib import Path
import os
import dj_database_url

# ==============================
# Base Directory
# ==============================
BASE_DIR = Path(__file__).resolve().parent.parent

# ==============================
# Security
# ==============================
SECRET_KEY = os.environ.get("SECRET_KEY", "your-local-dev-key")

# DEBUG:
# Local Windows development:
#   PowerShell -> $env:DEBUG="True"
# Production (Render):
# ##  For development
##DEBUG = True
###SECURE_SSL_REDIRECT = False
#for deployement
DEBUG = True
SECURE_SSL_REDIRECT = False
# HTTPS security only in production
#SECURE_SSL_REDIRECT = not DEBUG
SESSION_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SECURE = not DEBUG

# ==============================
# Allowed Hosts
# ==============================
ALLOWED_HOSTS = os.environ.get(
    "ALLOWED_HOSTS",
    "localhost,127.0.0.1,  solidaritesjp2-1.onrender.com"
).split(",")

# ==============================
# Installed Apps
# ==============================
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    # Third-party apps
    'widget_tweaks',
    'django.contrib.humanize',

    # Local apps
    'accounts',
    'transact1_regular_deposit',
    'transact2_loans',
    'transact3_lending',
    'transact4_share_mngt',
    'transact5_share_distrib',
    'reports_analysis',
    'notifications',
    'mobile_apps',
    'audit_logs',
    'meeting_Mngt',
    'ledger',
    'governance',
]

# ==============================
# Middleware
# ==============================
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',

    # WhiteNoise for production static files
    # (enabled only when DEBUG=False)
]

if not DEBUG:
    MIDDLEWARE.append('whitenoise.middleware.WhiteNoiseMiddleware')

MIDDLEWARE += [
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

# ==============================
# URLs / Templates / WSGI
# ==============================
ROOT_URLCONF = 'solidarite_sjp2.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / "templates"],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'accounts.context_processors.user_roles',
            ],
        },
    },
]

WSGI_APPLICATION = 'solidarite_sjp2.wsgi.application'

# ==============================
# Database
# ==============================
DATABASE_URL = os.environ.get("DATABASE_URL")

if DATABASE_URL:
    DATABASES = {
        "default": dj_database_url.parse(DATABASE_URL)
    }
else:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.mysql',
            'NAME': os.environ.get("DB_NAME", "ssjp2Database"),
            'USER': os.environ.get("DB_USER", "root"),
            'PASSWORD': os.environ.get("DB_PASSWORD", ""),
            'HOST': os.environ.get("DB_HOST", "localhost"),
            'PORT': os.environ.get("DB_PORT", "3306"),
        }
    }

# ==============================
# Password Validation
# ==============================
AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'
    },
]

# ==============================
# Internationalization
# ==============================
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'

USE_I18N = True
USE_TZ = True

# ==============================
# Custom User Model
# ==============================
AUTH_USER_MODEL = 'accounts.User'

# ==============================
# Static Files
# ==============================
STATIC_URL = '/static/'

STATICFILES_DIRS = [
    BASE_DIR / "static"
]

STATIC_ROOT = BASE_DIR / "staticfiles"

# WhiteNoise production storage
if not DEBUG:
    STATICFILES_STORAGE = (
        'whitenoise.storage.CompressedManifestStaticFilesStorage'
    )

# ==============================
# Logging
# ==============================
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler'
        }
    },
    'root': {
        'handlers': ['console'],
        'level': 'INFO',
    },
}

# ==============================
# Login / Logout
# ==============================
LOGIN_URL = '/accounts/login/'
LOGOUT_REDIRECT_URL = '/'

# ==============================
# Default primary key field type
# ==============================
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# ==========================================================
# LOCAL DEVELOPMENT (Windows)
# ==========================================================
# Use:
#   python manage.py runserver 9000
#
# Open browser manually:
#   http://localhost:9000
#
# IMPORTANT:
#   Use HTTP locally, not HTTPS.
#
# If browser forces HTTPS:
#   Use Incognito mode
#   OR clear browser HSTS cache
#
# ==========================================================
# OPTIONAL WAITRESS TESTING (Windows)
# ==========================================================
# waitress-serve --host=127.0.0.1 --port=9000 solidarite_sjp2.wsgi:application
#
# ==========================================================
# PRODUCTION (Render/Linux)
# ==========================================================
# Procfile:
#   web: gunicorn solidarite_sjp2.wsgi:application
#
# Environment variables:
#

#   SECRET_KEY=your-secret-key
# #  DATABASE_URL=your-database-url
# #cd C:\Users\Admin\PycharmProjects\SolidariteSJP2
# ==========================================================