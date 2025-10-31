"""
WSGI config for kopasmen project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/5.2/howto/deployment/wsgi/
"""

import os
import sys

# Tambahkan path project agar semua app bisa ditemukan
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kopasmen.kopasmen.settings')

from django.core.wsgi import get_wsgi_application
application = get_wsgi_application()
