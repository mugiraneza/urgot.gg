import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR.parent / ".env")
load_dotenv(BASE_DIR / ".env")

SECRET_KEY =os.environ["DJANGO_SECRET_KEY"]
DEBUG = os.environ.get("DJANGO_DEBUG", "False") == "True"
ALLOWED_HOSTS =  os.environ.get("DJANGO_ALLOWED_HOSTS", "localhost").split(",")

# Build paths inside the project like this: BASE_DIR / 'subdir'.
# Application definition

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    
    'rest_framework',
    'drf_yasg',
    'api',
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

ROOT_URLCONF = 'back.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
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
REST_FRAMEWORK = {
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 25
}

WSGI_APPLICATION = 'back.wsgi.application'


def _resolve_sqlite_path(path_value, fallback):
    if not path_value:
        return fallback
    path = Path(path_value)
    if path.is_absolute():
        return path
    return BASE_DIR / path


def _build_default_database():
    postgres_host = os.environ.get("POSTGRES_HOST")
    postgres_db = os.environ.get("POSTGRES_DB")
    db_engine = os.environ.get("DB_ENGINE", "").strip().lower()

    if db_engine == "postgres" or postgres_host or postgres_db:
        return {
            'ENGINE': 'django.db.backends.postgresql',
            'NAME': postgres_db or 'urgot',
            'USER': os.environ.get("POSTGRES_USER", "urgot"),
            'PASSWORD': os.environ.get("POSTGRES_PASSWORD", "urgot"),
            'HOST': postgres_host or 'postgres',
            'PORT': int(os.environ.get("POSTGRES_PORT", "5432")),
            'CONN_MAX_AGE': int(os.environ.get("POSTGRES_CONN_MAX_AGE", "60")),
        }

    return {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': _resolve_sqlite_path(os.environ.get("SQLITE_PATH"), BASE_DIR / 'import_db.sqlite3'),
    }


DATABASES = {
    'default': _build_default_database(),
    'sqlite_import': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': _resolve_sqlite_path(
            os.environ.get("SQLITE_IMPORT_PATH"),
            BASE_DIR / 'import_db.sqlite3',
        ),
    },
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
#region ai model
ML_MODEL_PATH = BASE_DIR / "ml" / "win_model.pkl"
#end region ai model

LANGUAGE_CODE = 'fr-fr'
TIME_ZONE = os.environ.get("DJANGO_TIME_ZONE", "Europe/Paris")
USE_I18N = True
USE_TZ = True
STATIC_URL = 'static/'
RIOT_IMAGES_ROOT = BASE_DIR / "static/riot_images"
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
