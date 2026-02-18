
"""
utils/gcp_storage.py — Utility for uploading artifacts to Google Cloud Storage.
"""

from typing import Optional, Union
import io
import os
import uuid
from pathlib import Path
from google.cloud import storage
import logging

from config import get_settings

logger = logging.getLogger(__name__)

class GCPStorageManager:
    """Handles upload of artifacts (images, PPTX) to GCP Storage."""

    def __init__(self):
        settings = get_settings()
        self.enabled = False
        self.bucket_name = None
        self.client = None

        if settings.gcp_bucket_name:
            try:
                # If path to credentials is provided, use it
                if settings.gcp_credentials_json:
                    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = settings.gcp_credentials_json
                
                # If project ID is provided, use it, otherwise rely on default
                if settings.gcp_project_id:
                    self.client = storage.Client(project=settings.gcp_project_id)
                else:
                    self.client = storage.Client()
                
                self.bucket_name = settings.gcp_bucket_name
                self.bucket = self.client.bucket(self.bucket_name)
                self.enabled = True
                logger.info(f"GCP Storage enabled. Bucket: {self.bucket_name}")
            except Exception as e:
                logger.error(f"Failed to initialize GCP Storage: {e}")
                self.enabled = False
        else:
            logger.info("GCP Storage disabled (no bucket name configured).")

    def upload_file(self, content: Union[bytes, io.BytesIO, str, Path], destination_blob_name: str, content_type: str = "application/octet-stream") -> Optional[str]:
        """Uploads content to GCS and returns the public URL or gs:// URI."""
        if not self.enabled:
            return None

        try:
            blob = self.bucket.blob(destination_blob_name)
            
            if isinstance(content, (str, Path)):
                # Upload from filename
                blob.upload_from_filename(str(content), content_type=content_type)
            elif isinstance(content, io.BytesIO):
                # Upload from file-like object
                content.seek(0)
                blob.upload_from_file(content, content_type=content_type)
            elif isinstance(content, bytes):
                # Upload from string
                blob.upload_from_string(content, content_type=content_type)
            else:
                logger.error(f"Unsupported content type for upload: {type(content)}")
                return None

            logger.info(f"Uploaded {destination_blob_name} to gs://{self.bucket_name}/{destination_blob_name}")
            return f"gs://{self.bucket_name}/{destination_blob_name}"
            # Ideally return public URL if bucket is public, or signed URL
            # return blob.public_url 
        except Exception as e:
            logger.error(f"Failed to upload to GCS: {e}")
            return None

    def download_file(self, blob_name: str) -> Optional[bytes]:
        """Download a file from GCS and return its contents as bytes."""
        if not self.enabled:
            return None

        try:
            blob = self.bucket.blob(blob_name)
            data = blob.download_as_bytes()
            logger.info(f"Downloaded {blob_name} from GCS ({len(data)} bytes)")
            return data
        except Exception as e:
            logger.error(f"Failed to download {blob_name} from GCS: {e}")
            return None

    def download_to_bytesio(self, blob_name: str) -> Optional[io.BytesIO]:
        """Download a file from GCS into a BytesIO buffer."""
        data = self.download_file(blob_name)
        if data is None:
            return None
        buf = io.BytesIO(data)
        buf.seek(0)
        return buf

    def exists(self, blob_name: str) -> bool:
        """Check if a blob exists in the bucket."""
        if not self.enabled:
            return False

        try:
            blob = self.bucket.blob(blob_name)
            return blob.exists()
        except Exception as e:
            logger.error(f"Failed to check existence of {blob_name}: {e}")
            return False

    def generate_unique_filename(self, prefix: str, extension: str) -> str:
        """Generates a unique timestamped filename."""
        from datetime import datetime
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        unique_id = uuid.uuid4().hex[:8]
        return f"{prefix}/{timestamp}_{unique_id}{extension}"

# Global instance
_storage_manager = None

def get_storage_manager() -> GCPStorageManager:
    global _storage_manager
    if _storage_manager is None:
        _storage_manager = GCPStorageManager()
    return _storage_manager
