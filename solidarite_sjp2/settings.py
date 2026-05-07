from pathlib import Path
import os

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# ==============================
# SECURITY
# ==============================
# Use environment variables for production secrets
SECRET_KEY = os.environ.get("SECRET_KEY", "your-local-dev-key")  # fallback for local testing
DEBUG = os.environ.get("DEBUG", "False") == "True"

ALLOWED_HOSTS = [
    "solidaritesjp2.onrender.com",
    "www.solidaritesjp2.com",
    "solidaritesjp2.com"
]

# ==============================
# Application definition
# ==============================
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'widget_tweaks',
    'django.contrib.humanize',  # ← Add this line
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

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

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
# Database configuration
# ==============================
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.mysql',
        'NAME': os.environ.get("DB_NAME", "ssjp2Database"),
        'USER': os.environ.get("DB_USER", "root"),
        'PASSWORD': os.environ.get("DB_PASSWORD", "Popos@2026"),
        'HOST': os.environ.get("DB_HOST", "localhost"),
        'PORT': os.environ.get("DB_PORT", "3306"),
    }
}

# ==============================
# Password validation
# ==============================
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# ==============================
# Internationalization
# ==============================
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

# ==============================
# Custom user model
# ==============================
AUTH_USER_MODEL = 'accounts.User'

# ==============================
# Static files
# ==============================
STATIC_URL = '/static/'
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"  # for collectstatic

# ==============================
# Login / Logout
# ==============================
LOGIN_URL = '/accounts/login/'
LOGOUT_REDIRECT_URL = '/'

# ==============================
# Default primary key field type
# ==============================
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'