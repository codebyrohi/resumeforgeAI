"""One thin wrapper around object storage for photos, raw uploads and generated exports.

Key layout inside the single bucket:
  photos/   public   - profile photos
  exports/  public   - generated ATS PDFs and cinematic HTML pages
  uploads/  private  - raw uploaded resumes (audit trail, never publicly served)

The bucket policy (or CloudFront behaviour) should only expose photos/ and exports/.
`STORAGE_BACKEND=local` swaps S3 for a folder on disk so the app runs without AWS in dev.
"""
from functools import lru_cache
from pathlib import Path
from typing import Protocol

from app.config import get_settings

PUBLIC_PREFIXES = ("photos/", "exports/")


class StorageClient(Protocol):
    def put(self, key: str, data: bytes, content_type: str) -> str:
        """Store bytes; return a public URL for public prefixes, else an internal URI."""

    def get(self, key: str) -> bytes | None: ...


class S3Storage:
    def __init__(self) -> None:
        import boto3

        s = get_settings()
        self.bucket = s.s3_bucket
        self.region = s.s3_region
        self.public_base = s.s3_public_base_url.rstrip("/")
        self.s3 = boto3.client(
            "s3",
            region_name=s.s3_region,
            aws_access_key_id=s.s3_access_key or None,
            aws_secret_access_key=s.s3_secret_key or None,
        )

    def put(self, key: str, data: bytes, content_type: str) -> str:
        extra = {"ContentType": content_type}
        if key.startswith("exports/"):
            # Re-published pages overwrite the same key; keep CDN/browsers from serving stale copies.
            extra["CacheControl"] = "no-cache"
        self.s3.put_object(Bucket=self.bucket, Key=key, Body=data, **extra)
        if not key.startswith(PUBLIC_PREFIXES):
            return f"s3://{self.bucket}/{key}"
        if self.public_base:
            return f"{self.public_base}/{key}"
        return f"https://{self.bucket}.s3.{self.region}.amazonaws.com/{key}"

    def get(self, key: str) -> bytes | None:
        try:
            return self.s3.get_object(Bucket=self.bucket, Key=key)["Body"].read()
        except self.s3.exceptions.NoSuchKey:
            return None


class LocalStorage:
    def __init__(self) -> None:
        s = get_settings()
        self.root = Path(s.local_storage_dir).resolve()
        self.base_url = s.public_api_base_url.rstrip("/")

    def _path(self, key: str) -> Path:
        path = (self.root / key).resolve()
        if not path.is_relative_to(self.root):
            raise ValueError("invalid storage key")
        return path

    def put(self, key: str, data: bytes, content_type: str) -> str:
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        if not key.startswith(PUBLIC_PREFIXES):
            return f"local://{key}"
        return f"{self.base_url}/files/{key}"  # served by StaticFiles mounts in main.py

    def get(self, key: str) -> bytes | None:
        path = self._path(key)
        return path.read_bytes() if path.is_file() else None


@lru_cache
def get_storage() -> StorageClient:
    return S3Storage() if get_settings().storage_backend == "s3" else LocalStorage()
