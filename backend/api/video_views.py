import logging
import os
import re
import uuid
from datetime import timedelta

from botocore.exceptions import BotoCoreError, ClientError
from django.conf import settings
from django.core.mail import send_mail
from django.db import models
from django.db.models import Q
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy
from rest_framework import mixins, serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import NotFound, PermissionDenied
from rest_framework.response import Response

from . import video_quota, video_storage
from .i18n import render
from .models import (
    HANDOVER_MEDIA,
    ContentItem,
    ContentItemStatus,
    Project,
    Task,
    TaskStatus,
    User,
    UserRole,
    VideoComment,
    VideoStatus,
    VideoSubmission,
)
from .serializers import display_name
from .views import MANAGERS, log_activity, managed_projects, notify

log = logging.getLogger('api.video')

UPLOADER_ROLES = [UserRole.EDITOR, UserRole.VIDEOGRAPHER]
OCTET = 'application/octet-stream'
MIME_RE = re.compile(r'^[\w.+-]+/[\w.+-]+$')


def file_kind(content_type):
    major = content_type.split('/')[0]
    return major if major in ('video', 'image', 'audio') else 'file'


def is_reviewer(user, project):
    return user.role in MANAGERS and managed_projects(user).filter(pk=project.pk).exists()


def is_assigned(user, project, content_item=None):
    if content_item is not None:
        return (
            content_item.assigned_editor_id == user.id
            or content_item.assigned_videographer_id == user.id
            or Task.objects.filter(content_item=content_item, assigned_to=user).exists()
        )
    return (
        ContentItem.objects.filter(Q(assigned_editor=user) | Q(assigned_videographer=user), project=project).exists()
        or Task.objects.filter(project=project, assigned_to=user).exists()
    )


def visible_submissions(user):
    if user.role in MANAGERS:
        return VideoSubmission.objects.filter(project__in=managed_projects(user))
    return VideoSubmission.objects.filter(
        Q(uploader=user) | Q(status=VideoStatus.APPROVED, task__dependents__assigned_to=user)
    ).distinct()


def reviewers_for(project):
    if project.project_manager and project.project_manager.is_active:
        return [project.project_manager]
    return list(User.objects.filter(role=UserRole.OWNER, is_active=True))


def email(users, subject, body, params=None, footer=None):
    for u in {u for u in users if u and u.email}:
        text = render(body, params, u.language) + ('\n\n' + render(footer, params, u.language) if footer else '')
        try:
            send_mail(render(subject, params, u.language), text, settings.DEFAULT_FROM_EMAIL, [u.email])
        except Exception:
            log.exception('Failed to send email to user %s', u.pk)


def video_link(sub):
    return f'{settings.APP_BASE_URL}/videos/{sub.pk}'


def label(sub):
    what = sub.content_item.title if sub.content_item else sub.project.name
    return f'{what} (v{sub.version})'


class VideoCommentSerializer(serializers.ModelSerializer):
    author_name = serializers.SerializerMethodField()

    class Meta:
        model = VideoComment
        fields = ['id', 'submission', 'author', 'author_name', 'timestamp_seconds', 'body', 'created_at']
        read_only_fields = ['submission', 'author']

    def get_author_name(self, obj):
        return display_name(obj.author)


class VideoSubmissionSerializer(serializers.ModelSerializer):
    uploader_name = serializers.SerializerMethodField()
    reviewer_name = serializers.SerializerMethodField()
    project_name = serializers.CharField(source='project.name', read_only=True)
    content_item_title = serializers.CharField(source='content_item.title', read_only=True, default=None)
    kind = serializers.SerializerMethodField()
    handover_to_name = serializers.SerializerMethodField()

    class Meta:
        model = VideoSubmission
        fields = [
            'id',
            'project',
            'project_name',
            'content_item',
            'content_item_title',
            'version',
            'uploader',
            'uploader_name',
            'reviewer',
            'reviewer_name',
            'size_bytes',
            'original_filename',
            'content_type',
            'kind',
            'task',
            'editor_note',
            'status',
            'review_comment',
            'deleted',
            'stale_flagged_at',
            'created_at',
            'reviewed_at',
            'delivery',
            'handover_media',
            'handover_to',
            'handover_to_name',
            'handover_at',
        ]
        read_only_fields = fields

    def get_uploader_name(self, obj):
        return display_name(obj.uploader)

    def get_kind(self, obj):
        return file_kind(obj.content_type)

    def get_reviewer_name(self, obj):
        return display_name(obj.reviewer)

    def get_handover_to_name(self, obj):
        return display_name(obj.handover_to) if obj.handover_to_id else None


def error(message, code, http=status.HTTP_400_BAD_REQUEST):
    return Response({'error': message, 'code': code}, status=http)


def storage_unavailable(exc):
    log.exception('R2 request failed')
    if isinstance(exc, video_storage.StorageNotConfigured):
        return error(str(exc), 'storage_not_configured', status.HTTP_503_SERVICE_UNAVAILABLE)
    return error(
        _('Video storage is temporarily unavailable. Please try again.'), 'storage_error', status.HTTP_502_BAD_GATEWAY
    )


STORAGE_ERRORS = (video_storage.StorageNotConfigured, ClientError, BotoCoreError)


def submission_tasks(sub):
    if sub.task_id:
        return Task.objects.filter(pk=sub.task_id)
    if sub.content_item_id:
        return Task.objects.filter(content_item_id=sub.content_item_id, assigned_to_id=sub.uploader_id)
    return Task.objects.none()


def update_item_after(sub, fallback_status):
    if sub.task_id:
        from .workflow import refresh_item_status

        refresh_item_status(sub.content_item)
    else:
        sync_content_item(sub, fallback_status)


def sync_content_item(sub, new_status, count_revision=False):
    if not sub.content_item_id:
        return
    item = ContentItem.objects.get(pk=sub.content_item_id)
    item.status = new_status
    if count_revision:
        item.revision_count += 1
    item.save(update_fields=['status', 'revision_count', 'updated_at'])


class VideoSubmissionViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    serializer_class = VideoSubmissionSerializer

    def get_queryset(self):
        qs = visible_submissions(self.request.user).select_related('project', 'content_item', 'uploader', 'reviewer')
        if self.action == 'list':
            qs = qs.exclude(status=VideoStatus.UPLOADING)
            for param in ('project', 'content_item', 'status', 'task'):
                value = self.request.query_params.get(param)
                if value:
                    qs = qs.filter(**{param: value})
        return qs.order_by('-created_at')

    def own_upload(self):
        sub = self.get_object()
        if sub.uploader_id != self.request.user.id:
            raise PermissionDenied(_('Only the uploader can continue this upload.'))
        if sub.status != VideoStatus.UPLOADING or sub.deleted:
            raise NotFound(_('This upload is no longer in progress.'))
        return sub

    def fail_upload(self, sub, message, code):
        try:
            video_storage.abort_multipart(sub.object_key, sub.upload_id)
            video_storage.delete(sub.object_key)
        except STORAGE_ERRORS:
            log.exception('Cleanup of failed upload %s failed; daily cleanup will retry', sub.pk)
        VideoSubmission.objects.filter(pk=sub.pk).update(deleted=True)
        log.warning('Rejected upload %s: %s', sub.pk, message)
        return error(message, code)

    def target(self, request):
        user = request.user
        if user.role not in UPLOADER_ROLES:
            raise PermissionDenied(_('Only editors and videographers can submit work.'))
        data = request.data
        task = None
        if data.get('task'):
            task = (
                Task.objects.filter(pk=data['task'], assigned_to=user).select_related('project', 'content_item').first()
            )
            if task is None:
                raise NotFound(_('Task not found.'))
            project, content_item = task.project, task.content_item
            from .workflow import is_blocked

            if is_blocked(task):
                return error(
                    _('This order starts after the previous step is approved.'), 'blocked', status.HTTP_409_CONFLICT
                )
        else:
            try:
                project = Project.objects.get(pk=data.get('project'))
            except (Project.DoesNotExist, ValueError, TypeError):
                raise NotFound(_('Project not found.')) from None
            content_item = None
            if data.get('content_item'):
                content_item = ContentItem.objects.filter(pk=data['content_item'], project=project).first()
                if content_item is None:
                    return error(_('That content item does not belong to this project.'), 'invalid_content_item')
            if not is_assigned(user, project, content_item):
                raise PermissionDenied(_('You are not assigned to this project.'))
        waiting = VideoSubmission.objects.filter(
            project=project, content_item=content_item, status=VideoStatus.PENDING, deleted=False
        ).first()
        if waiting:
            return error(
                _('Version %(v)s is still waiting for review.') % {'v': waiting.version},
                'pending_exists',
                status.HTTP_409_CONFLICT,
            )
        return project, content_item, task

    def create(self, request):
        target = self.target(request)
        if isinstance(target, Response):
            return target
        project, content_item, task = target
        user, data = request.user, request.data
        filename = os.path.basename(str(data.get('filename') or '').replace('\\', '/')).strip()[:255]
        if not filename:
            return error(_('File name is required.'), 'invalid_name')
        content_type = str(data.get('content_type') or '').strip().lower()
        if not MIME_RE.match(content_type):
            content_type = OCTET
        try:
            size = int(data.get('size'))
        except (TypeError, ValueError):
            return error(_('File size is required.'), 'invalid_size')
        max_bytes = settings.VIDEO_MAX_UPLOAD_BYTES
        if size <= 0:
            return error(_('The file is empty.'), 'invalid_size')
        if size > max_bytes:
            return error(
                _('The file is too large (%(size)s MB). The maximum is %(max)s MB.')
                % {'size': f'{size / 1e6:.0f}', 'max': f'{max_bytes / 1e6:.0f}'},
                'too_large',
            )

        try:
            sub = video_quota.reserve(
                project=project,
                content_item=content_item,
                uploader=user,
                size=size,
                filename=filename,
                note=str(data.get('note') or ''),
                content_type=content_type,
                task=task,
            )
        except video_quota.QueueFull as e:
            return error(str(e), 'queue_full', status.HTTP_507_INSUFFICIENT_STORAGE)
        except STORAGE_ERRORS as e:
            return storage_unavailable(e)

        try:
            sub.upload_id = video_storage.create_multipart(sub.object_key, content_type)
        except STORAGE_ERRORS as e:
            VideoSubmission.objects.filter(pk=sub.pk).update(deleted=True)
            return storage_unavailable(e)
        sub.save(update_fields=['upload_id'])
        return Response(
            {'id': sub.id, 'key': sub.object_key, 'uploadId': sub.upload_id}, status=status.HTTP_201_CREATED
        )

    @action(detail=False, methods=['post'])
    def handover(self, request):
        """Record work handed over in person (hard drive, SSD, memory card…); the manager confirms receipt."""
        target = self.target(request)
        if isinstance(target, Response):
            return target
        project, content_item, task = target
        data = request.data
        media = data.get('media')
        if media not in dict(HANDOVER_MEDIA):
            return error(_('Choose what the footage was handed over on.'), 'invalid_media')
        receiver = None
        if data.get('handed_to'):
            receiver = User.objects.filter(pk=data['handed_to'], is_active=True, role__in=MANAGERS).first()
            if receiver is None:
                return error(_('Choose the manager who received it.'), 'invalid_receiver')
        when = parse_datetime(str(data.get('handed_over_at') or '')) or timezone.now()
        if timezone.is_naive(when):
            when = timezone.make_aware(when)
        if when > timezone.now() + timedelta(days=1):
            return error(_('The handover time can’t be in the future.'), 'invalid_time')
        sub = VideoSubmission.objects.create(
            project=project,
            content_item=content_item,
            task=task,
            uploader=request.user,
            delivery='in_person',
            object_key=f'in-person/{uuid.uuid4().hex}',
            size_bytes=0,
            content_type='application/x-handover',
            original_filename=str(dict(HANDOVER_MEDIA)[media]),
            editor_note=str(data.get('note') or '')[:2000],
            handover_media=media,
            handover_to=receiver,
            handover_at=when,
            status=VideoStatus.PENDING,
        )
        video_quota.assign_version(sub)
        submission_tasks(sub).exclude(status__in=[TaskStatus.COMPLETED, TaskStatus.CANCELLED]).update(
            status=TaskStatus.WAITING_FOR_REVIEW
        )
        update_item_after(sub, ContentItemStatus.UNDER_REVIEW)
        p = {
            'name': display_name(request.user),
            'what': label(sub),
            'media': dict(HANDOVER_MEDIA)[media],
            'link': video_link(sub),
        }
        notify(
            reviewers_for(sub.project),
            gettext_lazy('Work handed over in person'),
            gettext_lazy('%(name)s handed over %(what)s in person (%(media)s). Confirm once you have it.'),
            'video_submitted',
            'VideoSubmission',
            sub.pk,
            params=p,
        )
        log_activity(
            request.user, 'HANDOVER_RECORDED', 'VideoSubmission', sub.pk, {'version': sub.version, 'media': media}
        )
        return Response(self.get_serializer(sub).data, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=['get'])
    def receivers(self, request):
        task = (
            Task.objects.filter(pk=request.query_params.get('task')).select_related('project').first()
            if request.query_params.get('task')
            else None
        )
        project = task.project if task else Project.objects.filter(pk=request.query_params.get('project')).first()
        if project is None or not (is_assigned(request.user, project) or is_reviewer(request.user, project)):
            raise NotFound(_('Project not found.'))
        return Response([{'id': u.id, 'name': display_name(u)} for u in reviewers_for(project)])

    @action(detail=True, methods=['post'], url_path='sign-part')
    def sign_part(self, request, pk=None):
        sub = self.own_upload()
        try:
            part = int(request.data.get('part_number'))
        except (TypeError, ValueError):
            return error(_('part_number is required.'), 'invalid_part')
        if not 1 <= part <= 10000:
            return error(_('part_number must be between 1 and 10000.'), 'invalid_part')
        try:
            return Response({'url': video_storage.sign_part(sub.object_key, sub.upload_id, part)})
        except STORAGE_ERRORS as e:
            return storage_unavailable(e)

    @action(detail=True, methods=['get'])
    def parts(self, request, pk=None):
        """Parts already in R2, so an interrupted upload can resume."""
        sub = self.own_upload()
        try:
            return Response(video_storage.list_parts(sub.object_key, sub.upload_id))
        except STORAGE_ERRORS as e:
            return storage_unavailable(e)

    @action(detail=True, methods=['post'])
    def complete(self, request, pk=None):
        sub = self.own_upload()
        parts = request.data.get('parts')
        if not isinstance(parts, list) or not parts:
            return error(_('parts are required.'), 'invalid_parts')
        try:
            video_storage.complete_multipart(sub.object_key, sub.upload_id, parts)
        except (KeyError, TypeError, ValueError):
            return error(_('Malformed parts list.'), 'invalid_parts')
        except ClientError:
            return self.fail_upload(
                sub, _('The upload could not be completed. Please upload the file again.'), 'complete_failed'
            )
        except STORAGE_ERRORS as e:
            return storage_unavailable(e)

        try:
            meta = video_storage.head(sub.object_key)
            if meta is None:
                return self.fail_upload(sub, 'The uploaded file was not found. Please upload it again.', 'missing')
            if meta['size'] > sub.size_bytes or meta['size'] > settings.VIDEO_MAX_UPLOAD_BYTES:
                return self.fail_upload(
                    sub, 'The uploaded file is larger than declared and was removed.', 'size_mismatch'
                )
        except STORAGE_ERRORS as e:
            return storage_unavailable(e)

        updated = VideoSubmission.objects.filter(pk=sub.pk, status=VideoStatus.UPLOADING).update(
            status=VideoStatus.PENDING, size_bytes=meta['size']
        )
        if not updated:
            return error(_('This upload was already completed.'), 'already_completed', status.HTTP_409_CONFLICT)
        sub.refresh_from_db()
        video_quota.assign_version(sub)
        submission_tasks(sub).exclude(status__in=[TaskStatus.COMPLETED, TaskStatus.CANCELLED]).update(
            status=TaskStatus.WAITING_FOR_REVIEW
        )
        update_item_after(sub, ContentItemStatus.UNDER_REVIEW)

        reviewers = reviewers_for(sub.project)
        p = {
            'name': display_name(request.user),
            'what': label(sub),
            'file': sub.original_filename,
            'note': sub.editor_note or '—',
            'link': video_link(sub),
        }
        notify(
            reviewers,
            gettext_lazy('New submission to review'),
            gettext_lazy('%(name)s submitted %(what)s for review.'),
            'video_submitted',
            'VideoSubmission',
            sub.pk,
            params=p,
        )
        email(
            reviewers,
            gettext_lazy('[CMD] %(name)s submitted %(what)s for review'),
            gettext_lazy(
                '%(name)s submitted %(what)s for review.\n\nFile: %(file)s\nNote: %(note)s\n\nOpen and review: %(link)s\n'
            ),
            p,
        )
        log_activity(request.user, 'VIDEO_SUBMITTED', 'VideoSubmission', sub.pk, {'version': sub.version})
        return Response(self.get_serializer(sub).data)

    @action(detail=True, methods=['post'])
    def abort(self, request, pk=None):
        sub = self.own_upload()
        try:
            video_storage.abort_multipart(sub.object_key, sub.upload_id)
            video_storage.delete(sub.object_key)
        except STORAGE_ERRORS as e:
            return storage_unavailable(e)
        VideoSubmission.objects.filter(pk=sub.pk).update(deleted=True)
        return Response({'status': 'aborted'})

    def retrieve(self, request, pk=None):
        sub = self.get_object()
        user = request.user
        data = self.get_serializer(sub).data
        history = (
            visible_submissions(user)
            .filter(project=sub.project, content_item=sub.content_item)
            .exclude(status=VideoStatus.UPLOADING)
            .order_by('-version')
        )
        data['history'] = VideoSubmissionSerializer(history, many=True).data
        data['comments'] = VideoCommentSerializer(sub.comments.select_related('author'), many=True).data
        data['can_review'] = sub.status == VideoStatus.PENDING and is_reviewer(user, sub.project)
        latest = history.first()
        data['can_upload_new_version'] = (
            user.role in UPLOADER_ROLES
            and latest is not None
            and latest.pk == sub.pk
            and sub.status == VideoStatus.REJECTED
            and is_assigned(user, sub.project, sub.content_item)
        )
        data['view_url'] = data['download_url'] = None
        if not sub.deleted and sub.status != VideoStatus.UPLOADING and sub.delivery == 'upload':
            try:
                data['view_url'] = video_storage.file_url(sub.object_key, sub.content_type, sub.original_filename)
                data['download_url'] = video_storage.file_url(
                    sub.object_key, sub.content_type, sub.original_filename, download=True
                )
                data['url_expires_in'] = settings.VIDEO_PLAYBACK_URL_SECONDS
            except STORAGE_ERRORS as e:
                return storage_unavailable(e)
        return Response(data)

    @action(detail=True, methods=['post'])
    def review(self, request, pk=None):
        sub = self.get_object()
        if not is_reviewer(request.user, sub.project):
            raise PermissionDenied(_('Only the project manager or an owner can review this submission.'))
        decision = request.data.get('decision')
        comment = str(request.data.get('comment') or '').strip()
        if decision not in (VideoStatus.APPROVED, VideoStatus.REJECTED):
            return error(_('The decision must be “approved” or “rejected”.'), 'invalid_decision')
        if decision == VideoStatus.REJECTED and not comment:
            return error(_('A comment is required when requesting changes.'), 'comment_required')

        updated = VideoSubmission.objects.filter(pk=sub.pk, status=VideoStatus.PENDING).update(
            status=decision, review_comment=comment, reviewer=request.user, reviewed_at=timezone.now()
        )
        if not updated:
            return error(_('This submission has already been reviewed.'), 'already_reviewed', status.HTTP_409_CONFLICT)
        sub.refresh_from_db()

        approved = decision == VideoStatus.APPROVED
        submission_tasks(sub).filter(status=TaskStatus.WAITING_FOR_REVIEW).update(
            status=TaskStatus.COMPLETED if approved else TaskStatus.IN_PROGRESS,
            completed_at=timezone.now() if approved else None,
        )
        if not approved and sub.content_item_id:
            ContentItem.objects.filter(pk=sub.content_item_id).update(revision_count=models.F('revision_count') + 1)
        update_item_after(sub, ContentItemStatus.APPROVED if approved else ContentItemStatus.REVISION_REQUESTED)
        if approved and sub.task_id:
            from .workflow import unlocked_by

            for nxt in unlocked_by(Task.objects.get(pk=sub.task_id)):
                p = {'title': nxt.title, 'link': f'{settings.APP_BASE_URL}/orders/{nxt.id}'}
                notify(
                    [nxt.assigned_to],
                    gettext_lazy('Order ready to start'),
                    gettext_lazy('The previous step was approved. You can start “%(title)s” now.'),
                    'task_assignment',
                    'Task',
                    nxt.id,
                    params=p,
                )
                email(
                    [nxt.assigned_to],
                    gettext_lazy('[CMD] Ready to start: %(title)s'),
                    gettext_lazy('The previous step was approved. You can start “%(title)s” now.\n\n%(link)s\n'),
                    p,
                )
        p = {'what': label(sub), 'name': display_name(request.user), 'comment': comment, 'link': video_link(sub)}
        if approved and sub.delivery == 'in_person':
            title, message = (
                gettext_lazy('Handover confirmed'),
                (
                    gettext_lazy('%(name)s confirmed receiving %(what)s. Comment: %(comment)s')
                    if comment
                    else gettext_lazy('%(name)s confirmed receiving %(what)s.')
                ),
            )
            subject, body = gettext_lazy('[CMD] %(what)s received'), gettext_lazy('View it: %(link)s\n')
        elif approved:
            title, message = (
                gettext_lazy('Submission approved'),
                (
                    gettext_lazy('%(what)s was approved by %(name)s. Comment: %(comment)s')
                    if comment
                    else gettext_lazy('%(what)s was approved by %(name)s.')
                ),
            )
            subject, body = gettext_lazy('[CMD] %(what)s approved'), gettext_lazy('View it: %(link)s\n')
        else:
            title, message = (
                gettext_lazy('Submission needs revision'),
                (
                    gettext_lazy('%(what)s was sent back for revision by %(name)s. Comment: %(comment)s')
                    if comment
                    else gettext_lazy('%(what)s was sent back for revision by %(name)s.')
                ),
            )
            subject, body = (
                gettext_lazy('[CMD] %(what)s sent back for revision'),
                gettext_lazy('Upload a new version: %(link)s\n'),
            )
        notify([sub.uploader], title, message, 'video_reviewed', 'VideoSubmission', sub.pk, params=p)
        email([sub.uploader], subject, message, p, footer=body)
        log_activity(
            request.user,
            'VIDEO_APPROVED' if approved else 'VIDEO_REJECTED',
            'VideoSubmission',
            sub.pk,
            {'comment': comment},
        )
        return Response(self.get_serializer(sub).data)

    @action(detail=True, methods=['post'])
    def comments(self, request, pk=None):
        sub = self.get_object()
        serializer = VideoCommentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        ts = serializer.validated_data.get('timestamp_seconds')
        if ts is not None and ts < 0:
            return error(_('timestamp_seconds cannot be negative.'), 'invalid_timestamp')
        comment = serializer.save(submission=sub, author=request.user)
        others = [u for u in [sub.uploader, *reviewers_for(sub.project)] if u and u != request.user]
        notify(
            others,
            gettext_lazy('New comment'),
            gettext_lazy('%(name)s commented on %(what)s: %(body)s'),
            'video_comment',
            'VideoSubmission',
            sub.pk,
            params={'name': display_name(request.user), 'what': label(sub), 'body': comment.body[:140]},
        )
        return Response(VideoCommentSerializer(comment).data, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=['get'])
    def storage(self, request):
        if request.user.role not in MANAGERS:
            raise PermissionDenied()
        return Response(video_quota.usage())
