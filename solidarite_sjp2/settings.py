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
##TIS IS THE ONE THAT IS ON GIT,
DEBUG = True
SECURE_SSL_REDIRECT = False
# HTTPS security only in production
#SECURE_SSL_REDIRECT = not DEBUG
SESSION_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SECURE = not DEBUG

# ==============================
# Allowed Hosts
# ==============================
import os
##ALLOWED_HOSTS = ["*"]
ALLOWED_HOSTS = [
    "localhost",
    "127.0.0.1",
    "solidaritesjp2-1.onrender.com"
]
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
     ##
      "crispy_forms",
    "crispy_bootstrap5",
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
'system_monitor',
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
   'system_monitor.middleware.DeviceTrackingMiddleware',
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
CRISPY_ALLOWED_TEMPLATE_PACKS = "bootstrap5"
CRISPY_TEMPLATE_PACK = "bootstrap5"
# ==========================================================SECURITY SETTINGD
#SESSION_COOKIE_AGE = 1800
#SESSION_EXPIRE_AT_BROWSER_CLOSE = True

#CSRF_COOKIE_HTTPONLY = True
#SESSION_COOKIE_HTTPONLY = True
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
####################################################################
###see how to work on local , for modelling.  Those variables exist only temporarily in your local terminal session.
# $env:DB_NAME="ssjp2Database"
#  $env:DB_USER="root"
# $env:DB_PASSWORD="Popos@2026"
# $env:DB_HOST="localhost"
# $env:DB_PORT="3306"
#py manage.py makemigrations
#py manage.py migrate
##py pr manage.py runserver
#git status
#git add .
#git commit -m "Add bank "
#git push origin master
#########################################################
#   SECRET_KEY=your-secret-key
# #  DATABASE_URL=your-database-url
# #cd C:\Users\Admin\PycharmProjects\SolidariteSJP2
# ==========================================================UPDATE GIT
##start migration on git
##git add transact2_loans/migrations/
## git add transact2_loans/views.py
##git commit -m "Fix LoanPaymentView transaction handling"
##git push origin main//for me master
###=============================If it is template
#git add accounts/templates/accounts/member_account_detail.html
#git commit -m "Add member_account_detail template"
#git push origin main
##Get-ChildItem -Recurse -Filter "registration.html"  ##see how to find out a file##
##check problrm git log -1
####################################### Remove-Item .git\index; git reset
##error: bad signature 0x00000000
##fatal: index file corrupt
