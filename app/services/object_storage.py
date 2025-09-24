import os
import uuid
import json
from typing import Optional, Dict, Any, Tuple
from datetime import datetime, timedelta
from fastapi import HTTPException
import mimetypes
from azure.storage.blob import BlobServiceClient, generate_blob_sas, BlobSasPermissions
from azure.core.exceptions import ResourceNotFoundError, AzureError

class ObjectStorageService:
    """Service for handling file uploads to Azure Blob Storage"""

    def __init__(self):
        self.connection_string = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
        self.account_name = os.getenv("AZURE_STORAGE_ACCOUNT_NAME")
        self.account_key = os.getenv("AZURE_STORAGE_ACCOUNT_KEY")
        self.container_name = os.getenv("AZURE_STORAGE_CONTAINER_NAME", "promptlibrary")

        # Check if Azure Blob Storage is configured
        self.is_enabled = bool(self.connection_string or (self.account_name and self.account_key))

        if not self.is_enabled:
            print("Azure Blob Storage not configured - file upload features will be disabled")
            return

        try:
            # Initialize the BlobServiceClient
            if self.connection_string:
                self.blob_service_client = BlobServiceClient.from_connection_string(self.connection_string)
            else:
                account_url = f"https://{self.account_name}.blob.core.windows.net"
                from azure.storage.blob import BlobServiceClient
                self.blob_service_client = BlobServiceClient(account_url=account_url, credential=self.account_key)

            # Ensure container exists
            self._ensure_container_exists()

        except Exception as e:
            print(f"Failed to initialize Azure Blob Storage: {e}")
            self.is_enabled = False

    def _ensure_container_exists(self):
        """Ensure the storage container exists"""
        try:
            container_client = self.blob_service_client.get_container_client(self.container_name)
            if not container_client.exists():
                container_client.create_container(public_access='blob')
                print(f"Created container: {self.container_name}")
        except Exception as e:
            print(f"Error ensuring container exists: {e}")

    def generate_presigned_upload_url(
        self, 
        filename: str, 
        content_type: str,
        is_public: bool = False,
        expiry_minutes: int = 15
    ) -> Dict[str, Any]:
        """Generate a presigned URL for direct file upload to Azure Blob Storage

        Args:
            filename: Original filename
            content_type: MIME type of the file
            is_public: Whether file should be publicly accessible
            expiry_minutes: URL expiry time in minutes

        Returns:
            Dict containing upload URL, file path, and metadata
        """
        if not self.is_enabled:
            raise HTTPException(
                status_code=503,
                detail="File upload is not available - Azure Blob Storage not configured"
            )

        # Generate unique filename to avoid conflicts
        file_extension = os.path.splitext(filename)[1]
        unique_filename = f"{uuid.uuid4().hex}{file_extension}"

        # Determine storage path based on visibility
        if is_public:
            file_path = f"public/{unique_filename}"
        else:
            file_path = f"private/uploads/{unique_filename}"

        try:
            # Generate SAS URL for upload
            expiry_time = datetime.utcnow() + timedelta(minutes=expiry_minutes)

            sas_token = generate_blob_sas(
                account_name=self.account_name,
                container_name=self.container_name,
                blob_name=file_path,
                account_key=self.account_key,
                permission=BlobSasPermissions(write=True, create=True),
                expiry=expiry_time
            )

            upload_url = f"https://{self.account_name}.blob.core.windows.net/{self.container_name}/{file_path}?{sas_token}"

            return {
                "upload_url": upload_url,
                "file_path": file_path,
                "unique_filename": unique_filename,
                "original_filename": filename,
                "content_type": content_type,
                "is_public": is_public,
                "expires_at": expiry_time.isoformat()
            }

        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to generate upload URL: {str(e)}"
            )

    def generate_presigned_download_url(
        self, 
        file_path: str, 
        expiry_minutes: int = 60
    ) -> str:
        """Generate a presigned URL for downloading a file

        Args:
            file_path: Path to the file in blob storage
            expiry_minutes: URL expiry time in minutes

        Returns:
            Presigned download URL
        """
        if not self.is_enabled:
            raise HTTPException(
                status_code=503,
                detail="File download is not available - Azure Blob Storage not configured"
            )

        try:
            expiry_time = datetime.utcnow() + timedelta(minutes=expiry_minutes)

            sas_token = generate_blob_sas(
                account_name=self.account_name,
                container_name=self.container_name,
                blob_name=file_path,
                account_key=self.account_key,
                permission=BlobSasPermissions(read=True),
                expiry=expiry_time
            )

            download_url = f"https://{self.account_name}.blob.core.windows.net/{self.container_name}/{file_path}?{sas_token}"
            return download_url

        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to generate download URL: {str(e)}"
            )

    def delete_file(self, file_path: str) -> bool:
        """Delete a file from Azure Blob Storage

        Args:
            file_path: Path to the file in blob storage

        Returns:
            True if file was deleted, False if file didn't exist
        """
        if not self.is_enabled:
            raise HTTPException(
                status_code=503,
                detail="File deletion is not available - Azure Blob Storage not configured"
            )

        try:
            blob_client = self.blob_service_client.get_blob_client(
                container=self.container_name, 
                blob=file_path
            )

            blob_client.delete_blob()
            return True

        except ResourceNotFoundError:
            return False
        except AzureError as e:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to delete file: {str(e)}"
            )

    def get_file_metadata(self, file_path: str) -> Optional[Dict[str, Any]]:
        """Get metadata for a file in Azure Blob Storage

        Args:
            file_path: Path to the file in blob storage

        Returns:
            Dict with file metadata or None if file doesn't exist
        """
        if not self.is_enabled:
            raise HTTPException(
                status_code=503,
                detail="File metadata is not available - Azure Blob Storage not configured"
            )

        try:
            blob_client = self.blob_service_client.get_blob_client(
                container=self.container_name, 
                blob=file_path
            )

            properties = blob_client.get_blob_properties()

            return {
                "name": file_path,
                "size": properties.size,
                "content_type": properties.content_settings.content_type,
                "etag": properties.etag,
                "last_modified": properties.last_modified.isoformat() if properties.last_modified else None,
            }

        except ResourceNotFoundError:
            return None
        except AzureError as e:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to get file metadata: {str(e)}"
            )

    def is_file_public(self, file_path: str) -> bool:
        """Check if a file is in a public directory

        Args:
            file_path: Path to the file in blob storage

        Returns:
            True if file is in public directory, False otherwise
        """
        return file_path.startswith("public/")

    def validate_file_type(self, filename: str, allowed_types: list = None) -> Tuple[bool, str]:
        """Validate file type based on extension and MIME type

        Args:
            filename: Name of the file
            allowed_types: List of allowed MIME types (if None, allows common document types)

        Returns:
            Tuple of (is_valid, mime_type)
        """
        if allowed_types is None:
            # Default allowed types for documents
            allowed_types = [
                'application/pdf',
                'application/msword',
                'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
                'application/vnd.ms-excel',
                'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                'application/vnd.ms-powerpoint',
                'application/vnd.openxmlformats-officedocument.presentationml.presentation',
                'text/plain',
                'text/csv',
                'image/jpeg',
                'image/png',
                'image/gif',
                'image/svg+xml',
                'application/json',
                'application/xml',
                'text/xml'
            ]

        # Guess MIME type from filename
        mime_type, _ = mimetypes.guess_type(filename)

        if not mime_type:
            return False, "unknown"

        is_valid = mime_type in allowed_types
        return is_valid, mime_type

# Global instance
object_storage_service = ObjectStorageService()