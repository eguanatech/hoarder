from django.urls import path
from . import views

app_name = 's3_ingestion'

urlpatterns = [
    path('',                    views.trends,          name='trends'),
    path('uid-autocomplete/',   views.uid_autocomplete, name='uid_autocomplete'),
]
