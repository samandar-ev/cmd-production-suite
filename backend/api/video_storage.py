from functools import lru_cache
from urllib.parse import quote

import boto3
from botocore.client import Config
from botocore.exceptions import ClientError
from django.conf import settings


class StorageNotConfigured(Exception):
    pass


@lru_cache(maxsize=1)
def _client():
    if not (settings.R2_ENDPOINT_URL and settings.R2_BUCKET and settings.R2_ACCESS_KEY_ID):
        raise StorageNotConfigured('Video storage is not configured. Set the R2_* environment variables.')
    return boto3.client(
        's3',
        endpoint_url=settings.R2_ENDPOINT_URL,
        aws_access_key_id=settings.R2_ACCESS_KEY_ID,
        aws_secret_access_key=settings.R2_SECRET_ACCESS_KEY,
        region_name='auto',
        config=Config(
            signature_version='s3v4',
            s3={'addressing_style': 'path'},
            request_checksum_calculation='when_required',
            response_checksum_validation='when_required',
            retries={'max_attempts': 3, 'mode': 'standard'},
        ),
    )


def reset_client():
    _client.cache_clear()


def _bucket():
    return settings.R2_BUCKET


def create_multipart(key, content_type):
    res = _client().create_multipart_upload(Bucket=_bucket(), Key=key, ContentType=content_type)
    return res['UploadId']


def presign_put(key, content_type):
    return _client().generate_presigned_url(
        'put_object',
        Params={'Bucket': _bucket(), 'Key': key, 'ContentType': content_type},
        ExpiresIn=settings.VIDEO_PART_URL_SECONDS,
    )


def sign_part(key, upload_id, part_number):
    return _client().generate_presigned_url(
        'upload_part',
        Params={'Bucket': _bucket(), 'Key': key, 'UploadId': upload_id, 'PartNumber': part_number},
        ExpiresIn=settings.VIDEO_PART_URL_SECONDS,
    )


def list_parts(key, upload_id):
    parts, marker = [], None
    while True:
        kwargs = {'Bucket': _bucket(), 'Key': key, 'UploadId': upload_id}
        if marker:
            kwargs['PartNumberMarker'] = marker
        res = _client().list_parts(**kwargs)
        parts += [{'PartNumber': p['PartNumber'], 'ETag': p['ETag'], 'Size': p['Size']} for p in res.get('Parts', [])]
        if not res.get('IsTruncated'):
            return parts
        marker = res['NextPartNumberMarker']


def complete_multipart(key, upload_id, parts):
    _client().complete_multipart_upload(
        Bucket=_bucket(),
        Key=key,
        UploadId=upload_id,
        MultipartUpload={
            'Parts': sorted(
                [{'PartNumber': int(p['PartNumber']), 'ETag': p['ETag']} for p in parts], key=lambda p: p['PartNumber']
            )
        },
    )


def abort_multipart(key, upload_id):
    try:
        _client().abort_multipart_upload(Bucket=_bucket(), Key=key, UploadId=upload_id)
    except ClientError as e:
        if e.response['Error']['Code'] not in ('NoSuchUpload', '404', 'NoSuchKey'):
            raise


def head(key):
    try:
        res = _client().head_object(Bucket=_bucket(), Key=key)
    except ClientError as e:
        if e.response['Error']['Code'] in ('404', 'NoSuchKey', 'NotFound'):
            return None
        raise
    return {'size': res['ContentLength'], 'content_type': res.get('ContentType', '')}


def delete(key):
    _client().delete_object(Bucket=_bucket(), Key=key)


def file_url(key, content_type, filename, download=False):
    disposition = 'attachment' if download else 'inline'
    return _client().generate_presigned_url(
        'get_object',
        Params={
            'Bucket': _bucket(),
            'Key': key,
            'ResponseContentType': content_type,
            'ResponseContentDisposition': f"{disposition}; filename*=UTF-8''{quote(filename)}",
        },
        ExpiresIn=settings.VIDEO_PLAYBACK_URL_SECONDS,
    )


def list_objects(prefix):
    paginator = _client().get_paginator('list_objects_v2')
    for page in paginator.paginate(Bucket=_bucket(), Prefix=prefix):
        for obj in page.get('Contents', []):
            yield obj['Key'], obj['Size']
