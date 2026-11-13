from aiobotocore.config import AioConfig
from aiobotocore.session import AioSession, ClientCreatorContext
from types_aiobotocore_s3.client import S3Client


def create_s3_client(
    *, endpoint_url: str, region: str, access_key_id: str, secret_access_key: str
) -> ClientCreatorContext[S3Client]:
    return AioSession().create_client(
        "s3",
        endpoint_url=endpoint_url,
        region_name=region,
        aws_access_key_id=access_key_id,
        aws_secret_access_key=secret_access_key,
        config=AioConfig(
            # otherwise botocore hashes a whole file in the event loop before uploading it
            request_checksum_calculation="when_required",
            # every s3 server serves a bucket on the path, but a virtual host only with dns for it
            s3={"addressing_style": "path", "payload_signing_enabled": False},
        ),
    )
