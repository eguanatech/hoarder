from django.apps import apps
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from s3_ingestion.models import RawS3


class Command(BaseCommand):
    help = 'Delete all rows from the s3_ingestion app tables.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--force',
            action='store_true',
            help='Skip the confirmation prompt and delete immediately.',
        )

    def handle(self, *args, **options):
        if not options['force']:
            confirm = input("This will delete every row in the s3_ingestion tables. Type 'DELETE ALL' to continue: ")
            if confirm != 'DELETE ALL':
                raise CommandError('Aborted: confirmation text did not match.')

        app_models = [
            model for model in apps.get_app_config('s3_ingestion').get_models()
            if model._meta.model_name != 'raws3'
        ]

        with transaction.atomic():
            for model in app_models:
                count = model.objects.count()
                if count:
                    model.objects.all().delete()
                    self.stdout.write(
                        self.style.WARNING(f'Cleared {count} rows from {model._meta.label}.')
                    )

            raw_count = RawS3.objects.count()
            if raw_count:
                RawS3.objects.all().delete()
                self.stdout.write(self.style.WARNING(f'Cleared {raw_count} rows from s3_ingestion.RawS3.'))

        if not any(model.objects.count() for model in apps.get_app_config('s3_ingestion').get_models()):
            self.stdout.write(self.style.SUCCESS('All s3_ingestion table rows are cleared.'))
        else:
            self.stdout.write(self.style.ERROR('Some rows remain. Check database constraints or foreign keys.'))
