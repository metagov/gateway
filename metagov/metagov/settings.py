"""
Django settings for metagov project.

Generated by 'django-admin startproject' using Django 3.0.7.

For more information on this file, see
https://docs.djangoproject.com/en/3.0/topics/settings/

For the full list of settings and their values, see
https://docs.djangoproject.com/en/3.0/ref/settings/
"""

import os
import environ
import yaml


BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

env = environ.Env(
    # set casting, default value
    DEBUG=(bool, False),
    ALLOWED_HOSTS=(list, []),
    DATABASE_PATH=(str, os.path.join(BASE_DIR, "db.sqlite3")),
    DRIVER_EVENT_RECEIVER_URL=(str, ""),
    SERVER_URL=(str, "http://127.0.0.1:8000"),
    LOG_FILE=(str, "debug.log"),
)
# reading .env file
environ.Env.read_env()

# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/3.0/howto/deployment/checklist/
SERVER_URL = env("SERVER_URL")
SECRET_KEY = env("DJANGO_SECRET_KEY")

DEBUG = env("DEBUG")

ALLOWED_HOSTS = env.list("ALLOWED_HOSTS")

# URL where the Driver can receive event notifications (optional)
DRIVER_EVENT_RECEIVER_URL = env("DRIVER_EVENT_RECEIVER_URL")

METAGOV_CORE_APP = "metagov.core"

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django_celery_beat",
    "django_celery_results",
    "rest_framework",
    "drf_yasg",
    METAGOV_CORE_APP,
    "django_extensions",
    # 'schema_graph',
]

PLUGIN_APPS = []
PLUGINS_DIR = os.path.join(BASE_DIR, "metagov", "plugins")
for item in os.listdir(PLUGINS_DIR):
    if os.path.isdir(os.path.join(PLUGINS_DIR, item)) and not item.startswith("__"):
        app_name = "metagov.plugins.%s" % item
        if app_name not in INSTALLED_APPS:
            PLUGIN_APPS += (app_name,)

INSTALLED_APPS += PLUGIN_APPS

REST_FRAMEWORK = {
    "DEFAULT_SCHEMA_CLASS": "rest_framework.schemas.coreapi.AutoSchema",
    "EXCEPTION_HANDLER": "metagov.core.middleware.api_500_exception_handler",
}

REDOC_SETTINGS = {
    "LAZY_RENDERING": True,
    "HIDE_HOSTNAME": False,
}

METAGOV_SETTINGS = {
    "SLACK": {
        "CLIENT_ID": env("SLACK_CLIENT_ID"),
        "CLIENT_SECRET": env("SLACK_CLIENT_SECRET"),
        "SIGNING_SECRET": env("SLACK_SIGNING_SECRET"),
        "APP_ID": env("SLACK_APP_ID"),
    },
    "GITHUB": {
        "APP_NAME": env("GITHUB_APP_NAME"),
        "APP_ID": env("GITHUB_APP_ID"),
        "PRIVATE_KEY_PATH": env("GITHUB_PRIVATE_KEY_PATH"),
    },
    "TWITTER": {
        "API_KEY": env("TWITTER_API_KEY"),
        "API_SECRET_KEY": env("TWITTER_API_SECRET_KEY"),
        "ACCESS_TOKEN": env("TWITTER_ACCESS_TOKEN"),
        "ACCESS_TOKEN_SECRET": env("TWITTER_ACCESS_TOKEN_SECRET"),
    }
}

SWAGGER_SETTINGS = {
    "USE_SESSION_AUTH": False,
    "SECURITY_DEFINITIONS": {},
    "DEFAULT_FIELD_INSPECTORS": [
        "drf_yasg.inspectors.CamelCaseJSONFilter",
        "drf_yasg.inspectors.InlineSerializerInspector",
        "drf_yasg.inspectors.RelatedFieldInspector",
        "drf_yasg.inspectors.ChoiceFieldInspector",
        "drf_yasg.inspectors.FileFieldInspector",
        "drf_yasg.inspectors.DictFieldInspector",
        "drf_yasg.inspectors.SimpleFieldInspector",
        "drf_yasg.inspectors.StringDefaultFieldInspector",
    ],
    "DEFAULT_PARSER_CLASSES": [
        "rest_framework.parsers.FormParser",
        "rest_framework.parsers.MultiPartParser",
        "rest_framework.parsers.JSONParser",
    ],
}

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "request_logging.middleware.LoggingMiddleware",
]

AUTHENTICATION_BACKENDS = ["django.contrib.auth.backends.ModelBackend"]

ROOT_URLCONF = "metagov.urls"

### Logging
import sys

# Set default log level for Metagov and Plugins
DEFAULT_LOG_LEVEL_FOR_TESTS = "DEBUG"
DEFAULT_LOG_LEVEL = "DEBUG"

TESTING = sys.argv[1:2] == ["test"]
LOG_LEVEL = DEFAULT_LOG_LEVEL_FOR_TESTS if TESTING else DEFAULT_LOG_LEVEL

# Generate loggers for Metagov and Plugins
loggers = {}
for app in [METAGOV_CORE_APP] + PLUGIN_APPS:
    loggers.update({app: {"handlers": ["console", "file"], "level": LOG_LEVEL, "propagate": False}})

# Set log level to WARN for everything else (imported dependencies)
loggers[""] = {"handlers": ["console", "file"], "level": "WARN"}

# Override for specific apps
# loggers['metagov.plugins.opencollective'] = {'handlers': ['console', 'file'], 'level': "DEBUG"}
# loggers['metagov.plugins.opencollective.models'] = {'handlers': ['console', 'file'], 'level': "WARN"}

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "console": {"format": "%(name)-12s %(levelname)-8s %(message)s"},
        "file": {"format": "%(asctime)s %(name)-12s %(levelname)-8s %(message)s"},
    },
    "handlers": {
        "file": {
            "class": "logging.FileHandler",
            "filename": env("LOG_FILE"),
            "formatter": "file",
        },
        "console": {"class": "logging.StreamHandler", "formatter": "console"},
    },
    "loggers": loggers,
}

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [os.path.join(BASE_DIR, "core", "templates")],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "metagov.wsgi.application"
DEFAULT_AUTO_FIELD = "django.db.models.AutoField"

# Database
# https://docs.djangoproject.com/en/3.0/ref/settings/#databases

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": env("DATABASE_PATH"),
    }
}


# Password validation
# https://docs.djangoproject.com/en/3.0/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]


# Internationalization
# https://docs.djangoproject.com/en/3.0/topics/i18n/

LANGUAGE_CODE = "en-us"

TIME_ZONE = "UTC"

USE_I18N = True

USE_L10N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/3.0/howto/static-files/

STATIC_ROOT = os.path.join(BASE_DIR, "static")
STATIC_URL = "/static/"

# Celery configuration

from celery.schedules import crontab

# In production, replace this "amqp://USERNAME:PASSWORD@localhost:5672/VIRTUALHOST"
CELERY_BROKER_URL = "amqp://"

CELERY_BEAT_FREQUENCY = 60.0 * 3
CELERY_BEAT_SCHEDULE = {
    "plugin-tasks-beat": {
        "task": "metagov.core.tasks.execute_plugin_tasks",
        "schedule": CELERY_BEAT_FREQUENCY,
    }
}
