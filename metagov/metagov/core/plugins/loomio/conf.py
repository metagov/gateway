from django.conf import settings

LOOMIO_API_KEY = getattr(settings, 'LOOMIO_API_KEY', None)