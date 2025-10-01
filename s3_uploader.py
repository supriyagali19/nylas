import os
import boto3
from botocore.exceptions import NoCredentialsError

# Load AWS credentials and region from environment variables
AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID")
AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")
AWS_S3_BUCKET_NAME = os.getenv("AWS_S3_BUCKET_NAME")
AWS_REGION = os.getenv("AWS_REGION")

s3_client = boto3.client(
    's3',
    aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
    aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
    region_name=AWS_REGION
)

async def upload_file_to_s3(file_content: bytes, object_name: str, content_type: str) -> str:
    """
    Uploads file content to a specific path in an S3 bucket.

    Args:
        file_content: The binary content of the file.
        object_name: The full path for the object in S3 (e.g., 'folder/file.mp3').
        content_type: The MIME type of the file.

    Returns:
        The S3 URL of the uploaded object.
    """
    AWS_S3_BUCKET_NAME = os.getenv("AWS_S3_BUCKET_NAME")
    if not all([s3_client, AWS_S3_BUCKET_NAME]):
        raise ValueError("AWS client, bucket name, and region must be configured.")

    try:
        s3_client.put_object(
            Bucket=AWS_S3_BUCKET_NAME,
            Key=object_name,
            Body=file_content,
            ContentType=content_type
        )
        s3_location = f"https://{AWS_S3_BUCKET_NAME}.s3.{AWS_REGION}.amazonaws.com/{object_name}"
        print(f"✅ Uploaded to S3: {s3_location}")
        return s3_location
    except NoCredentialsError:
        print("❌ AWS credentials not available.")
        raise
    except Exception as e:
        print(f"❌ Failed to upload to S3: {e}")
        raise


async def delete_folder_from_s3(notetaker_id: str):
    """
    Deletes all objects within a folder corresponding to the notetaker_id.

    Args:
        notetaker_id: The unique ID of the recording session.
    """
    AWS_S3_BUCKET_NAME = os.getenv("AWS_S3_BUCKET_NAME")
    if not all([s3_client, AWS_S3_BUCKET_NAME]):
        raise ValueError("AWS client and bucket name must be configured.")

    folder_prefix = f"recordings/{notetaker_id}/"
    
    try:
        # List all objects within the folder
        objects_to_delete = s3_client.list_objects_v2(
            Bucket=AWS_S3_BUCKET_NAME,
            Prefix=folder_prefix
        )

        if 'Contents' not in objects_to_delete:
            print(f"No objects found in S3 for notetaker_id: {notetaker_id}")
            return # Nothing to delete

        # Prepare the list of keys to delete
        delete_keys = {'Objects': [{'Key': obj['Key']} for obj in objects_to_delete.get('Contents', [])]}

        # Execute the delete operation
        s3_client.delete_objects(Bucket=AWS_S3_BUCKET_NAME, Delete=delete_keys)
        print(f"✅ Successfully deleted folder '{folder_prefix}' from S3.")

    except Exception as e:
        print(f"❌ Failed to delete from S3: {e}")
        raise