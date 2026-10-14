import logging
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from api import video_storage
from api.models import ChatAttachment, VideoStatus, VideoSubmission
from api.serializers import display_name
from api.video_views import email, label, reviewers_for, video_link
from api.views import notify

log = logging.getLogger('api.video')


class Command(BaseCommand):
    help = 'Clean up abandoned video uploads, flag stale pending reviews, and audit R2 usage.'

    def handle(self, *args, **opts):
        now = timezone.now()
        self.abandoned(now - timedelta(hours=24))
        self.stale(now - timedelta(days=30), now)
        self.audit()

    def abandoned(self, cutoff):
        rows = VideoSubmission.objects.filter(status=VideoStatus.UPLOADING, deleted=False, created_at__lt=cutoff)
        for sub in rows:
            try:
                if sub.upload_id:
                    video_storage.abort_multipart(sub.object_key, sub.upload_id)
                video_storage.delete(sub.object_key)
            except Exception:
                log.exception('Could not clean up abandoned upload %s', sub.pk)
                continue
            VideoSubmission.objects.filter(pk=sub.pk).update(deleted=True)
            self.stdout.write(f'Released abandoned upload {sub.pk} ({sub.size_bytes} bytes reserved)')
        for att in ChatAttachment.objects.filter(ready=False, deleted=False, created_at__lt=cutoff):
            try:
                video_storage.delete(att.object_key)
            except Exception:
                log.exception('Could not clean up chat attachment %s', att.pk)
                continue
            ChatAttachment.objects.filter(pk=att.pk).update(deleted=True)
            self.stdout.write(f'Released unsent chat file {att.pk}')

    def stale(self, cutoff, now):
        rows = VideoSubmission.objects.filter(
            status=VideoStatus.PENDING, deleted=False, created_at__lt=cutoff, stale_flagged_at__isnull=True
        ).select_related('project', 'content_item', 'uploader')
        for sub in rows:
            people = [sub.uploader, *reviewers_for(sub.project)]
            msg = f'{label(sub)} by {display_name(sub.uploader)} has been waiting for review for over 30 days.'
            notify(people, 'Video Waiting Over 30 Days', msg, 'video_stale', 'VideoSubmission', sub.pk)
            email(people, f'[CMD] Review overdue: {label(sub)}', f'{msg}\n\nReview it here: {video_link(sub)}\n')
            VideoSubmission.objects.filter(pk=sub.pk).update(stale_flagged_at=now)
            self.stdout.write(f'Flagged stale pending video {sub.pk}')

    def audit(self):
        live = VideoSubmission.objects.filter(deleted=False).exclude(status=VideoStatus.UPLOADING)
        chat = ChatAttachment.objects.filter(deleted=False, ready=True)
        db_keys = dict(live.values_list('object_key', 'size_bytes'))
        db_keys.update(dict(chat.values_list('object_key', 'size_bytes')))
        db_total = sum(db_keys.values())
        known = set(VideoSubmission.objects.values_list('object_key', flat=True))
        known |= set(ChatAttachment.objects.values_list('object_key', flat=True))
        try:
            r2 = dict(video_storage.list_objects('videos/'))
        except Exception:
            log.exception('Could not list R2 objects for the audit')
            return
        r2_total = sum(r2.values())
        missing = [k for k in db_keys if k not in r2]
        orphans = [k for k in r2 if k not in known]
        resized = [k for k, size in db_keys.items() if k in r2 and r2[k] != size]
        summary = (
            f'R2 audit: database {db_total} bytes in {len(db_keys)} files, R2 {r2_total} bytes in {len(r2)} objects'
        )
        if missing or orphans or resized or db_total != r2_total:
            log.warning(
                '%s. Missing in R2: %s. Not in database: %s. Size differs: %s', summary, missing, orphans, resized
            )
        else:
            log.info('%s. No discrepancies.', summary)
        self.stdout.write(summary)
