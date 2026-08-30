"""Raw file storage abstraction: local filesystem for development, S3-
compatible (MinIO in dev, real S3 in production) behind the same interface.
Selected via STORAGE_USE_LOCAL_FS so switching environments is a config
change, not a code change.
"""
from __future__ import annotations

import uuid
from pathlib import Path

import boto3

from app.core.config import settings


class StorageService:
    def save(self, dataset_id: uuid.UUID, file_name: str, content: bytes) -> str:
        raise NotImplementedError

    def delete(self, dataset_id: uuid.UUID) -> None:
        raise NotImplementedError


class LocalFileStorage(StorageService):
    def save(self, dataset_id: uuid.UUID, file_name: str, content: bytes) -> str:
        base = Path(settings.LOCAL_STORAGE_PATH) / str(dataset_id)
        base.mkdir(parents=True, exist_ok=True)
        target = base / file_name
        target.write_bytes(content)
        return str(target)

    def delete(self, dataset_id: uuid.UUID) -> None:
        import shutil

        base = Path(settings.LOCAL_STORAGE_PATH) / str(dataset_id)
        shutil.rmtree(base, ignore_errors=True)


class S3CompatibleStorage(StorageService):
    def __init__(self) -> None:
        self._client = boto3.client(
            "s3",
            endpoint_url=settings.STORAGE_ENDPOINT,
            aws_access_key_id=settings.STORAGE_ACCESS_KEY,
            aws_secret_access_key=settings.STORAGE_SECRET_KEY,
        )
        self._bucket = settings.STORAGE_BUCKET
        try:
            self._client.create_bucket(Bucket=self._bucket)
        except Exception:  # noqa: BLE001 - bucket may already exist; creation is best-effort
            pass

    def save(self, dataset_id: uuid.UUID, file_name: str, content: bytes) -> str:
        key = f"{dataset_id}/{file_name}"
        self._client.put_object(Bucket=self._bucket, Key=key, Body=content)
        return f"s3://{self._bucket}/{key}"

    def delete(self, dataset_id: uuid.UUID) -> None:
        prefix = f"{dataset_id}/"
        try:
            objects = self._client.list_objects_v2(Bucket=self._bucket, Prefix=prefix)
            for obj in objects.get("Contents", []):
                self._client.delete_object(Bucket=self._bucket, Key=obj["Key"])
        except Exception:  # noqa: BLE001 - best-effort; DB cleanup already committed
            pass


def get_storage_service() -> StorageService:
    return LocalFileStorage() if settings.STORAGE_USE_LOCAL_FS else S3CompatibleStorage()
