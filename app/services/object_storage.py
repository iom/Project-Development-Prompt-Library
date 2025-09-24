import os
import uuid
import json
import requests
from typing import Optional, Dict, Any, Tuple
from datetime import datetime, timedelta
from fastapi import HTTPException
import mimetypes

# Replit sidecar endpoint for authentication
REPLIT_SIDECAR_ENDPOINT = "http://127.0.0.1:1106"

class ObjectStorageService:
    """Service for handling file uploads to Replit's object storage using Replit sidecar endpoint"""
    
    def __init__(self):
        self.bucket_id = os.getenv("DEFAULT_OBJECT_STORAGE_BUCKET_ID")
        self.private_dir = os.getenv("PRIVATE_OBJECT_DIR", "").strip("/")
        public_paths_str = os.getenv("PUBLIC_OBJECT_SEARCH_PATHS", "")
        self.public_paths = [path.strip() for path in public_paths_str.split(",") if path.strip()]
        
        # For Azure deployment, object storage is optional
        self.is_enabled = bool(self.bucket_id)
        if not self.is_enabled:
            print("Object storage not configured - file upload features will be disabled")
        
        # We'll use the Replit sidecar endpoint directly instead of GCS client
    
    def _sign_object_url(self, bucket_name: str, object_name: str, method: str, ttl_sec: int) -> str:
        """Sign an object URL using Replit sidecar endpoint"""
        if not bucket_name:
            raise HTTPException(status_code=500, detail="Object storage bucket not configured")
        try:
            expires_at = datetime.utcnow() + timedelta(seconds=ttl_sec)
            request_data = {
                "bucket_name": bucket_name,
                "object_name": object_name,
                "method": method,
                "expires_at": expires_at.isoformat() + "Z"  # Ensure proper ISO format with Z
            }
            
            # First get credentials from the sidecar
            credential_response = requests.get(
                f"{REPLIT_SIDECAR_ENDPOINT}/credential",
                timeout=10
            )
            
            if not credential_response.ok:
                raise HTTPException(
                    status_code=500,
                    detail=f"Failed to get credentials: {credential_response.status_code}"
                )
            
            # Now sign the URL with proper headers
            response = requests.post(
                f"{REPLIT_SIDECAR_ENDPOINT}/object-storage/signed-object-url",
                json=request_data,
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {credential_response.json().get('access_token', '')}"
                },
                timeout=30
            )
            
            if not response.ok:
                error_detail = f"Failed to sign object URL: {response.status_code}"
                try:
                    error_content = response.text
                    if error_content:
                        error_detail += f" - {error_content}"
                except:
                    pass
                raise HTTPException(status_code=500, detail=error_detail)
            
            result = response.json()
            signed_url = result.get("signed_url")
            if not signed_url:
                raise HTTPException(
                    status_code=500, 
                    detail="No signed URL returned from object storage service"
                )
            return signed_url
            
        except HTTPException:
            raise
        except requests.RequestException as e:
            raise HTTPException(
                status_code=500,
                detail=f"Error communicating with object storage service: {str(e)}"
            )
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Unexpected error signing object URL: {str(e)}"
            )
    
    def generate_presigned_upload_url(
        self, 
        filename: str, 
        content_type: str,
        is_public: bool = False,
        expiry_minutes: int = 15
    ) -> Dict[str, Any]:
        """Generate a presigned URL for direct file upload to object storage
        
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
                detail="File upload is not available - object storage not configured"
            )
        # Generate unique filename to avoid conflicts
        file_extension = os.path.splitext(filename)[1]
        unique_filename = f"{uuid.uuid4().hex}{file_extension}"
        
        # Determine storage path based on visibility
        if is_public:
            # Use public directory - extract just the directory name from the full path
            if self.public_paths:
                # Extract directory name from full path like "/bucket/public"
                public_path_parts = self.public_paths[0].strip("/").split("/")
                public_dir = public_path_parts[-1] if len(public_path_parts) > 1 else "public"
            else:
                public_dir = "public"
            file_path = f"{public_dir}/{unique_filename}"
        else:
            # Use private directory - extract just the directory name
            private_path_parts = self.private_dir.strip("/").split("/")
            private_dir = private_path_parts[-1] if len(private_path_parts) > 1 else ".private"
            file_path = f"{private_dir}/uploads/{unique_filename}"
        
        # Generate presigned upload URL using Replit sidecar
        try:
            expiry_time = datetime.utcnow() + timedelta(minutes=expiry_minutes)
            upload_url = self._sign_object_url(
                bucket_name=self.bucket_id,
                object_name=file_path,
                method="PUT",
                ttl_sec=expiry_minutes * 60
            )
            
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
            file_path: Path to the file in object storage
            expiry_minutes: URL expiry time in minutes
            
        Returns:
            Presigned download URL
        """
        if not self.is_enabled:
            raise HTTPException(
                status_code=503,
                detail="File download is not available - object storage not configured"
            )
        try:
            # Generate presigned download URL using Replit sidecar
            download_url = self._sign_object_url(
                bucket_name=self.bucket_id,
                object_name=file_path,
                method="GET",
                ttl_sec=expiry_minutes * 60
            )
            
            return download_url
            
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to generate download URL: {str(e)}"
            )
    
    def delete_file(self, file_path: str) -> bool:
        """Delete a file from object storage
        
        Args:
            file_path: Path to the file in object storage
            
        Returns:
            True if file was deleted, False if file didn't exist
        """
        try:
            # Generate presigned delete URL and make the request
            delete_url = self._sign_object_url(
                bucket_name=self.bucket_id,
                object_name=file_path,
                method="DELETE",
                ttl_sec=300  # 5 minutes is enough for delete operation
            )
            
            response = requests.delete(delete_url, timeout=30)
            
            # 204 means successful deletion, 404 means file didn't exist
            if response.status_code == 204:
                return True
            elif response.status_code == 404:
                return False
            else:
                raise HTTPException(
                    status_code=500,
                    detail=f"Failed to delete file: HTTP {response.status_code}"
                )
                
        except requests.RequestException as e:
            raise HTTPException(
                status_code=500, 
                detail=f"Failed to delete file: {str(e)}"
            )
    
    def get_file_metadata(self, file_path: str) -> Optional[Dict[str, Any]]:
        """Get metadata for a file in object storage
        
        Args:
            file_path: Path to the file in object storage
            
        Returns:
            Dict with file metadata or None if file doesn't exist
        """
        try:
            # Generate presigned HEAD URL and make the request to get metadata
            head_url = self._sign_object_url(
                bucket_name=self.bucket_id,
                object_name=file_path,
                method="HEAD",
                ttl_sec=300
            )
            
            response = requests.head(head_url, timeout=30)
            
            if response.status_code == 404:
                return None
            elif response.status_code != 200:
                raise HTTPException(
                    status_code=500,
                    detail=f"Failed to get file metadata: HTTP {response.status_code}"
                )
            
            # Extract metadata from headers
            return {
                "name": file_path,
                "size": int(response.headers.get("content-length", 0)),
                "content_type": response.headers.get("content-type"),
                "etag": response.headers.get("etag"),
                "last_modified": response.headers.get("last-modified"),
            }
            
        except requests.RequestException as e:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to get file metadata: {str(e)}"
            )
    
    def is_file_public(self, file_path: str) -> bool:
        """Check if a file is in a public directory
        
        Args:
            file_path: Path to the file in object storage
            
        Returns:
            True if file is in public directory, False otherwise
        """
        for public_path in self.public_paths:
            public_dir = public_path.strip("/")
            if file_path.startswith(f"{public_dir}/"):
                return True
        return False
    
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