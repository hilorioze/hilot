import uuid
from pathlib import Path
from typing import override

from types_aiobotocore_s3.client import S3Client
from types_aiobotocore_s3.type_defs import GetObjectOutputTypeDef

from hilot.domain.interfaces.adapters.file_storage import FileStorage
from hilot.domain.value_objects.media import StorageKey


class S3FileStorage(FileStorage):
    def __init__(self, *, client: S3Client, bucket: str) -> None:
        self._client: S3Client = client
        self._bucket: str = bucket

    @override
    async def upload(self, path: Path) -> StorageKey:
        key: StorageKey = StorageKey(str(uuid.uuid7()))

        with path.open("rb") as file:
            await self._client.put_object(Bucket=self._bucket, Key=key, Body=file)

        return key

    @override
    async def download(self, *, key: StorageKey, path: Path) -> None:
        response: GetObjectOutputTypeDef = await self._client.get_object(
            Bucket=self._bucket, Key=key
        )

        with path.open("wb") as file:
            async for chunk in response["Body"].iter_chunks():
                file.write(chunk)

    @override
    async def delete(self, key: StorageKey) -> None:
        await self._client.delete_object(Bucket=self._bucket, Key=key)
