"""
Storage abstraction: Supabase Storage in production, local disk fallback
in development (so the app runs with zero cloud setup out of the box).
"""
import os
import uuid
from abc import ABC, abstractmethod

from app.core.config import Settings, get_settings
from app.core.exceptions import UpstreamServiceError

settings = get_settings()


class StorageBackend(ABC):
    @abstractmethod
    def upload(self, bucket: str, data: bytes, extension: str) -> str:
        """Stores bytes, returns a retrievable URL/path."""
        raise NotImplementedError


class LocalStorageBackend(StorageBackend):
    def __init__(self, cfg: Settings):
        self.root = cfg.LOCAL_STORAGE_FALLBACK_DIR
        os.makedirs(self.root, exist_ok=True)

    def upload(self, bucket: str, data: bytes, extension: str) -> str:
        bucket_dir = os.path.join(self.root, bucket)
        os.makedirs(bucket_dir, exist_ok=True)
        filename = f"{uuid.uuid4().hex}.{extension}"
        path = os.path.join(bucket_dir, filename)
        with open(path, "wb") as f:
            f.write(data)
        return f"file://{path}"


class SupabaseStorageBackend(StorageBackend):
    def __init__(self, cfg: Settings):
        try:
            from supabase import create_client
        except ImportError as exc:  # pragma: no cover
            raise UpstreamServiceError("supabase-py is not installed.") from exc
        self.client = create_client(cfg.SUPABASE_URL, cfg.SUPABASE_SERVICE_KEY)

    def upload(self, bucket: str, data: bytes, extension: str) -> str:
        filename = f"{uuid.uuid4().hex}.{extension}"
        try:
            self.client.storage.from_(bucket).upload(filename, data)
            return self.client.storage.from_(bucket).get_public_url(filename)
        except Exception as exc:
            raise UpstreamServiceError(f"Supabase upload failed: {exc}") from exc


def get_storage_backend() -> StorageBackend:
    if settings.SUPABASE_URL and settings.SUPABASE_SERVICE_KEY:
        return SupabaseStorageBackend(settings)
    return LocalStorageBackend(settings)
