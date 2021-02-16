from django.conf import settings

DISCOURSE_API_KEY = getattr(settings, 'DISCOURSE_API_KEY', None)
DISCOURSE_URL = getattr(settings, 'DISCOURSE_URL', None)
