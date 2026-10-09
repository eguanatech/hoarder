import os
import sys
import django




# Add project directory to Python path
sys.path.insert(0, '/home/philip/eguana/hoarder')


# Set Django settings
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hoarder.settings')

# Initialize Django
django.setup()

# Now import models
from s3_ingestion.models import RawS3