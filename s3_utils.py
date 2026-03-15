import boto3
from botocore.exceptions import NoCredentialsError, ClientError
from botocore.client import Config
import os
import logging
from dotenv import load_dotenv

# Explicitly load the .env file exactly where s3_utils.py lives
env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env')
load_dotenv(dotenv_path=env_path)

AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID")
AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")
AWS_REGION = os.getenv("AWS_REGION", "us-east-1")
S3_BUCKET_NAME = os.getenv("S3_BUCKET_NAME")

# print(f"DEBUG: Loaded S3 Config. Bucket='{S3_BUCKET_NAME}', Key_Exists={bool(AWS_ACCESS_KEY_ID)}")

# Initialize S3 Client
s3_client = boto3.client(
    's3',
    aws_access_key_id=AWS_ACCESS_KEY_ID,
    aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
    region_name=AWS_REGION,
    endpoint_url=f"https://s3.{AWS_REGION}.amazonaws.com" if AWS_REGION else None,
    config=Config(signature_version='s3v4')
) if AWS_ACCESS_KEY_ID else None

def upload_file_to_s3(file_obj, object_name, content_type=None):
    """
    Upload a file-like object to an S3 bucket
    :param file_obj: File to upload
    :param object_name: S3 object name. If not specified then file_name is used
    :param content_type: MIME type of the file
    :return: URL of the uploaded file if successful, else None
    """
    if not S3_BUCKET_NAME or not AWS_ACCESS_KEY_ID:
        print("S3 credentials missing. Skipping upload.")
        return None

    try:
        extra_args = {}
        if content_type:
            extra_args['ContentType'] = content_type
            
        s3_client.upload_fileobj(file_obj, S3_BUCKET_NAME, object_name, ExtraArgs=extra_args)
        
        # Construct URL
        # For private buckets, we usually need presigned URLs, but for this app 
        # we might assume public-read for covers/profiles or use presigned for all.
        # Let's return the Object Key (path) so we can generate presigned URLs dynamically, 
        # OR return the full URL if it's public.
        # Strategy: Return "s3://key" format or just the key to distinguish from local paths.
        return f"s3://{object_name}"
    
    except ClientError as e:
        logging.error(e)
        return None

def generate_presigned_url(object_name, expiration=3600):
    """Generate a presigned URL to share an S3 object"""
    if not S3_BUCKET_NAME or not AWS_ACCESS_KEY_ID:
        return None

    try:
        # Strip s3:// prefix if present
        if object_name.startswith("s3://"):
            object_name = object_name[5:]
            
        response = s3_client.generate_presigned_url('get_object',
                                                    Params={'Bucket': S3_BUCKET_NAME,
                                                            'Key': object_name},
                                                    ExpiresIn=expiration)
    except ClientError as e:
        logging.error(e)
        return None

    return response

def delete_file_from_s3(object_name):
    if not S3_BUCKET_NAME or not AWS_ACCESS_KEY_ID:
        return False
        
    try:
        if object_name.startswith("s3://"):
             object_name = object_name[5:]
        s3_client.delete_object(Bucket=S3_BUCKET_NAME, Key=object_name)
        return True
    except ClientError as e:
        logging.error(e)
        return False
