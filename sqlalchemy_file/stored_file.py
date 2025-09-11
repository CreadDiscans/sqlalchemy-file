import io
import json
from typing import Optional

from libcloud.storage.base import Object
from libcloud.storage.types import ObjectDoesNotExistError
from sqlalchemy_file.helpers import LOCAL_STORAGE_DRIVER_NAME


class StoredFile(io.IOBase):
    """Represents a file that has been stored in a database. This class provides
    a file-like interface for reading the file content.

    Attributes:
        name: The name of the file (Same as file_id).
        filename: The original name of the uploaded file.
        content_type: The content type of the uploaded file.
        object: The `Object` representing the file in the storage service.
    """

    def __init__(self, obj: Object) -> None:
        if obj.driver.name == LOCAL_STORAGE_DRIVER_NAME:
            """Retrieve metadata from associated metadata file"""
            try:
                metadata_obj = obj.container.get_object(f"{obj.name}.metadata.json")
                with open(metadata_obj.get_cdn_url()) as metadata_file:
                    obj.meta_data = json.load(metadata_file)
            except ObjectDoesNotExistError:
                pass
        self.name = obj.name
        self.filename = obj.meta_data.get("filename", "unnamed")
        self.content_type = obj.extra.get(
            "content_type",
            obj.meta_data.get("content_type", "application/octet-stream"),
        )
        self.object = obj

    def get_cdn_url(self) -> Optional[str]:
        """Retrieves the CDN URL of the file if available."""
        try:
            if self.object.driver.name == 'MinIO Storage Driver':
                from minio import Minio
                from datetime import timedelta
                client = Minio(
                    self.object.driver.connectionCls.host,
                    access_key=self.object.driver.key,
                    secret_key=self.object.driver.secret,
                )
                bucket_name = self.object.container.name
                object_name = self.object.name
                
                url = client.presigned_get_object(
                    bucket_name,
                    object_name,
                    expires=timedelta(seconds=604800)
                )
                return url
            elif self.object.driver.name == 'Amazon S3 (us-east-1)' or 'Amazon S3' in self.object.driver.name:
                import boto3
                
                s3_client = boto3.client(
                    's3',
                    aws_access_key_id=self.object.driver.key,
                    aws_secret_access_key=self.object.driver.secret,
                    region_name=getattr(self.object.driver, 'region_name', 'us-east-1')
                )
                
                bucket_name = self.object.container.name
                object_name = self.object.name
                expires_seconds = 3600 * 12
                
                url = s3_client.generate_presigned_url(
                    'get_object',
                    Params={'Bucket': bucket_name, 'Key': object_name},
                    ExpiresIn=expires_seconds
                )
                return url
            else:
                return self.object.get_cdn_url()
        except NotImplementedError:
            return None

    def read(self, n: int = -1, chunk_size: Optional[int] = None) -> bytes:
        """Reads the content of the file.

        Arguments:
            n: The number of bytes to read. If not specified or set to -1,
                it reads the entire content of the file. Defaults to -1.
            chunk_size: The size of the chunks to read at a time.
                If not specified, the default chunk size of the storage provider will be used.

        """
        return next(
            self.object.range_as_stream(
                0, end_bytes=n if n > 0 else None, chunk_size=chunk_size
            )
        )

    def close(self) -> None:
        pass  # No need to close;

    def seekable(self) -> bool:
        return False  # Seeking is not supported ; pragma: no cover

    def writable(self) -> bool:
        return False  # Writing is not supported ; pragma: no cover

    def readable(self) -> bool:
        return True  # Reading is supported ; pragma: no cover
