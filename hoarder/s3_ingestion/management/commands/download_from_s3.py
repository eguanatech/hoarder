from django.core.management.base import BaseCommand
from s3_ingestion.models import RawS3

import boto3
import json
import zlib
import threading
import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from s3_ingestion import process_s3


_thread_local = threading.local()


def _s3_client():
    """Return a per-thread boto3 S3 client (boto3 clients are not thread-safe)."""
    if not hasattr(_thread_local, 's3'):
        _thread_local.s3 = boto3.client('s3')
    return _thread_local.s3



class Command(BaseCommand):
    help = 'Download objects from S3 and store in database'
   

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.paginator = boto3.client('s3').get_paginator('list_objects_v2')

        self.limitfiles = 1000
        self.newfiles = list()
        self.disable_processing = False


    def add_arguments(self, parser):
        parser.add_argument(
            '--bucket',
            type=str,
            help='S3 bucket name',
        )

        parser.add_argument(
            '--path',
            type=str,
            help='s3 path',
        )

        parser.add_argument(
            '--limitfiles',
            type=int,
            help='Limit the number of files to download from S3 (set to -1 for no limit). Default is 10 files it not specified',
        )

        parser.add_argument(
            '--disableprocess',
            type=bool,
            help='disable processing of json files, and will prevent populating the decoded tables. this is set to false',
        )

    

    def handle(self, *args, **options):
        bucket = options.get('bucket')

        path = options.get('path')

        

        if bucket is None:
            bucket='duracell-private'

        if path is None:
            path='device_jsons'

        limit=options.get('limitfiles')
        if limit is not None:
            self.limitfiles=limit   #if no limit this will take hours about 30 minutes for a million files.

        disablepros=options.get('disableprocess')
        if disablepros is not None:
            self.disable_processing=disablepros

        if bucket is not None and path is not None:

            self.stdout.write(self.style.SUCCESS(f'Downloading from S3 bucket: {bucket}   path: {path}'))

            max_workers = 20
            chunk_size = 2000

            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                for chunk in self._iter_pending_chunks(bucket, path, chunk_size):
                    self._process_chunk(executor, bucket, chunk)

        print(f'Done. {len(self.newfiles)} new files downloaded.')

    def _iter_pending_chunks(self, bucket, path, chunk_size):
        """Stream S3 keys in pages, yielding chunks of keys not already in the DB.

        Never loads all keys into memory at once — each page is checked against
        the DB and discarded before the next page is fetched.
        """
        total_seen = 0
        pending_buffer = []

        for page in self.paginator.paginate(Bucket=bucket, Prefix=path):
            for obj in page.get('Contents', []):
                if self.limitfiles >= 0 and total_seen >= self.limitfiles:
                    if pending_buffer:
                        yield pending_buffer
                    return

                key = obj['Key']
                filename_nodir = key.split('/')[-1]
                total_seen += 1
                pending_buffer.append(key)

            # Check this page's keys against the DB and drop already-stored ones.
            if pending_buffer:
                names = [k.split('/')[-1] for k in pending_buffer]
                existing = set(
                    RawS3.objects.filter(filename__in=names).values_list('filename', flat=True)
                )
                pending_buffer = [k for k in pending_buffer if k.split('/')[-1] not in existing]

            while len(pending_buffer) >= chunk_size:
                yield pending_buffer[:chunk_size]
                pending_buffer = pending_buffer[chunk_size:]

        if pending_buffer:
            yield pending_buffer

    def _process_chunk(self, executor, bucket, chunk):
        """Fetch a chunk of S3 keys concurrently, bulk-insert into RawS3, then parse."""
        futures = {
            executor.submit(self.get_s3_object, bucket, key): key
            for key in chunk
        }

        batch = []
        for future in as_completed(futures):
            key = futures[future]
            filename_nodir = key.split('/')[-1]
            try:
                s3_dict = future.result()
            except Exception as exc:
                print(f'Error downloading {filename_nodir}: {exc}')
                continue

            date = datetime.datetime.now(datetime.timezone.utc)
            batch.append((filename_nodir, key, s3_dict, date))

        if not batch:
            return

        objects_to_create = [
            RawS3(
                filename=fn,
                pathfilename=key,
                s3_bucket=bucket,
                rawjson=json.dumps(s3_dict),
                date=date,
            )
            for fn, key, s3_dict, date in batch
        ]

        created_rows = RawS3.objects.bulk_create(objects_to_create, batch_size=len(batch))
        self.newfiles.extend(row.filename for row in created_rows)
        print(f'Inserted {len(created_rows)} rows (total so far: {len(self.newfiles)})')

        if not self.disable_processing:
            merged = process_s3.ParsedTables(*([] for _ in process_s3.ParsedTables._fields))
            for row, (_, _, s3_dict, _) in zip(created_rows, batch):
                if row is not None:
                    table = process_s3.parse_raw_json(s3_dict, row.pathfilename, row.id)
                    for field in process_s3.ParsedTables._fields:
                        getattr(merged, field).extend(getattr(table, field))
            process_s3.parsedtables_to_models(merged)



    def search_filename_in_raws3(self, filename: str) -> bool:
        objectsfiles = RawS3.objects.filter(filename=filename)

        if len(objectsfiles) > 1:
            print('warning duplicate files?!?')

        return objectsfiles.exists()





    def put_dict_in_model(self, data_dict: dict, bucket: str, filename: str, pathfilename: str, date: datetime.datetime) -> None:
        # Example implementation: store the dictionary in the RawS3 model

        assert isinstance(data_dict, dict), f"data_dict must be a dict, got {type(data_dict).__name__}"
        assert isinstance(bucket, str) and bucket, f"bucket must be a non-empty str, got {bucket!r}"
        assert isinstance(filename, str) and filename, f"filename must be a non-empty str, got {filename!r}"
        assert isinstance(pathfilename, str) and pathfilename, f"pathfilename must be a non-empty str, got {pathfilename!r}"
        assert isinstance(date, datetime.datetime), f"date must be a datetime.datetime, got {type(date).__name__}"


        s3obj=None
        if data_dict:
            s3obj=RawS3.objects.create(
                filename=filename,
                pathfilename=pathfilename,
                s3_bucket=bucket,
                rawjson=json.dumps(data_dict),
                date=date
            )

        return s3obj



    def get_s3_object(self, bucket, filename):
        obj = _s3_client().get_object(Bucket=bucket, Key=filename)

        returndict={}
        try:
            body=obj['Body'].read()
            #if filename.endswith('.bin'):
            if obj['ContentType'] == 'application/zlib':
                body=zlib.decompress(body)
            returndict= json.loads(body.decode('utf-8'))

            if not isinstance(returndict,dict): #only handle json obj, not list of JSON objects (is that a possibility)
                print(f"Warning: S3 object {filename} from bucket {bucket} is not a JSON object")
                returndict={}

        except Exception as e:
            print(f"Error reading S3 object {filename} from bucket {bucket}: {e}")
            returndict={}

        

        return returndict



        



    def get_filename(self,bucket,prefix):
        filenames=[]
        for page in self.paginator.paginate(Bucket=bucket, Prefix=prefix):
            
            for obj in page.get('Contents', []):
                filenames.append(obj['Key'])
                if len(filenames)>self.limitfiles and self.limitfiles>=0: #put this here to make sure I don't fill my hard drive when working locally
                    break

            if len(filenames)>self.limitfiles and self.limitfiles>=0:
                break

        #print (filenames)
        return filenames
        



