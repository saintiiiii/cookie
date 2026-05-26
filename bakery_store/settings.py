import os

if os.environ.get("DJANGO_ENV", "development").lower() == "production":
    from config.settings.production import *  # noqa: F401,F403
else:
    from config.settings.development import *  # noqa: F401,F403
