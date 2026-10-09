from django.core.management.base import BaseCommand
from s3_ingestion.models import RawS3
from django.db import transaction
# Add your S3 download logic here

import boto3
import json
import zlib

import datetime
from s3_ingestion import process_s3


class Command(BaseCommand):
    help = 'Download objects from S3 and store in database'
   

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.s3=boto3.client('s3')
        self.paginator=self.s3.get_paginator('list_objects_v2')

        self.limitfiles=1000
        self.newfiles=list()

        self.disable_processing=False

        
        

        pass

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

            filename=self.get_filename(bucket,path)

            print('length of filenames: '+str(len(filename)))

            for x in filename:

                
                filename_nodir=x.split('/')[-1]
                date=datetime.datetime.now(datetime.timezone.utc)

                if self.search_filename_in_raws3(filename_nodir) == False:   #prevent duplicat entries in database
                    
                    s3_dict=self.get_s3_object(bucket,x)      #ONLY DOWNLOAD IF NOT IN DATABASE
                    #print("Downloaded S3 object for filename %r: "%(s3_object))

                    #atomic operation, prevents  crash occurs on and only save in RawS3 table
                    with transaction.atomic():
                        raws3obj=self.put_dict_in_model(s3_dict,bucket,filename_nodir,x, date)
                        self.newfiles.append(filename_nodir)
                        #parse json and populat decoded database
                        if self.disable_processing==False and raws3obj is not None:
                            table = process_s3.parse_raw_json(s3_dict, x, raws3obj.id)
                            created = process_s3.parsedtables_to_models(table)
                            print(created)

                else:
                    print ("file %r already exists in the database" % (filename_nodir))
                    pass

        for n in self.newfiles:
            print('newly downloaded file: %r' % (n))
            


    def search_filename_in_raws3(self,filename:str)->bool:
        objectsfiles=RawS3.objects.filter(filename=filename)

        if len(objectsfiles) > 1:
            print('warning duplicate files?!?')

        if objectsfiles.exists():
            return True
        return False





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



    def get_s3_object(self, bucket, filename):  #return dict,list,from json, empty dict if otherwise
        obj=self.s3.get_object(Bucket=bucket, Key=filename)

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
        



