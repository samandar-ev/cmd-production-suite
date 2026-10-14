import logging
import os
import re
import uuid

from django.conf import settings
from django.db import transaction
from django.db.models import Sum
from django.utils.translation import gettext as _

from . import video_storage
from .models import ChatAttachment, VideoStatus, VideoStorageLock, VideoSubmission

log = logging.getLogger('api.video')

REVIEWED = [VideoStatus.APPROVED, VideoStatus.REJECTED]


class QueueFull(Exception):
    pass


def used_bytes():
    videos = VideoSubmission.objects.filter(deleted=False).aggregate(t=Sum('size_bytes'))['t'] or 0
    chat = ChatAttachment.objects.filter(deleted=False).aggregate(t=Sum('size_bytes'))['t'] or 0
    return videos + chat


def usage():
    limit = settings.VIDEO_STORAGE_LIMIT_BYTES
    live = VideoSubmission.objects.filter(deleted=False)
    reclaimable = live.filter(status__in=REVIEWED).aggregate(t=Sum('size_bytes'))['t'] or 0
    used = used_bytes()
    return {
        'used_bytes': used,
        'limit_bytes': limit,
        'free_bytes': max(0, limit - used),
        'reclaimable_bytes': reclaimable,
        'max_upload_bytes': settings.VIDEO_MAX_UPLOAD_BYTES,
    }


def evict(target_free):
    limit = settings.VIDEO_STORAGE_LIMIT_BYTES
    need = used_bytes() + target_free - limit
    if need <= 0:
        return []
    candidates = list(
        VideoSubmission.objects.filter(deleted=False, status__in=REVIEWED, delivery='upload').order_by(
            'reviewed_at', 'id'
        )
    )
    if sum(c.size_bytes for c in candidates) < need:
        raise QueueFull(_('The review queue is full. Ask the reviewer to clear pending videos.'))
    evicted = []
    for sub in candidates:
        if need <= 0:
            break
        video_storage.delete(sub.object_key)
        VideoSubmission.objects.filter(pk=sub.pk).update(deleted=True)
        need -= sub.size_bytes
        evicted.append(sub.pk)
        log.info('Evicted video submission %s (%s bytes, reviewed %s)', sub.pk, sub.size_bytes, sub.reviewed_at)
    return evicted


def reserve(*, project, content_item, uploader, size, filename, note, content_type, task=None):
    with transaction.atomic():
        VideoStorageLock.objects.select_for_update().get_or_create(id=1)
        evict(size)
        ext = os.path.splitext(filename)[1].lower()
        ext = ext if re.fullmatch(r'\.[a-z0-9]{1,10}', ext) else ''
        return VideoSubmission.objects.create(
            project=project,
            content_item=content_item,
            task=task,
            uploader=uploader,
            content_type=content_type,
            object_key=f'videos/{project.id}/{uuid.uuid4().hex}{ext}',
            size_bytes=size,
            original_filename=filename[:255],
            editor_note=note,
            status=VideoStatus.UPLOADING,
        )


def _safe_ext(filename):
    ext = os.path.splitext(filename)[1].lower()
    return ext if re.fullmatch(r'\.[a-z0-9]{1,10}', ext) else ''


def reserve_attachment(*, task, uploader, size, filename, content_type):
    with transaction.atomic():
        VideoStorageLock.objects.select_for_update().get_or_create(id=1)
        evict(size)
        return ChatAttachment.objects.create(
            task=task,
            uploader=uploader,
            filename=filename[:255],
            content_type=content_type,
            size_bytes=size,
            object_key=f'videos/chat/{task.id}/{uuid.uuid4().hex}{_safe_ext(filename)}',
        )


def assign_version(sub):
    with transaction.atomic():
        VideoStorageLock.objects.select_for_update().get_or_create(id=1)
        last = (
            VideoSubmission.objects.filter(project=sub.project, content_item=sub.content_item, version__isnull=False)
            .order_by('-version')
            .values_list('version', flat=True)
            .first()
        )
        sub.version = (last or 0) + 1
        sub.save(update_fields=['version'])
    return sub.version
