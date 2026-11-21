from .settings import *  # noqa: F403

SECRET_KEY = "test-secret-key-for-unit-tests"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }
}