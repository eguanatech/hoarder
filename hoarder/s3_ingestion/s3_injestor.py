import os
import sys
import django


PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
WORKSPACE_ROOT = os.path.abspath(os.path.join(PROJECT_ROOT, '..'))

for path in (PROJECT_ROOT, WORKSPACE_ROOT):
    if path not in sys.path:
        sys.path.insert(0, path)


os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hoarder.settings')

django.setup()

from s3_ingestion.models import RawS3