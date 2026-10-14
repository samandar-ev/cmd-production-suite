from django.db.models import Count, Q, Sum
from django.utils import timezone
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from . import telegram
from .i18n import render
from .models import (
    ActivityLog,
    Client,
    Comment,
    ContentItem,
    ContentItemStatus,
    Contract,
    Notification,
    OrderChatRead,
    OrderMessage,
    Project,
    ProjectStatus,
    PublishRecord,
    Revision,
    RevisionStatus,
    SubmissionRecord,
    Task,
    TaskChecklistItem,
    TaskStatus,
    Template,
    User,
    UserRole,
)
from .permissions import IsOwnerOrAdmin, IsOwnerOrPM
from .serializers import (
    ActivityLogSerializer,
    ClientSerializer,
    CommentSerializer,
    ContentItemSerializer,
    ContractSerializer,
    NotificationSerializer,
    OrderMessageSerializer,
    ProjectOrderSerializer,
    ProjectSerializer,
    PublishRecordSerializer,
    RevisionSerializer,
    SubmissionRecordSerializer,
    TaskChecklistItemSerializer,
    TaskSerializer,
    TemplateSerializer,
    UserSerializer,
    display_name,
    unread_count,
)

MANAGERS = [UserRole.OWNER, UserRole.PROJECT_MANAGER]
OPEN_TASK = [TaskStatus.NOT_STARTED, TaskStatus.IN_PROGRESS]
OPEN_REVISION = [RevisionStatus.REQUESTED, RevisionStatus.IN_PROGRESS]
STATUS_LOCKED = gettext_lazy(
    'Status follows the production sequence and can’t be set by hand: '
    'Start working → Submit work → review (approve / request changes) → Mark published.'
)


def log_activity(user, action_type, entity_type, entity_id, details):
    ActivityLog.objects.create(
        user=user, action_type=action_type, entity_type=entity_type, entity_id=entity_id, details_json=details
    )


def notify(users, title, message, type_, entity_type=None, entity_id=None, params=None):
    for u in {u for u in users if u}:
        Notification.objects.create(
            recipient_user=u,
            title=render(title, params, u.language),
            message=render(message, params, u.language),
            type=type_,
            related_entity_type=entity_type,
            related_entity_id=entity_id,
        )
    telegram.notify_users(users, title, message, params, entity_type, entity_id)


def overdue_q(prefix=''):
    return Q(**{f'{prefix}status': TaskStatus.OVERDUE}) | Q(
        **{f'{prefix}due_date__lt': timezone.now(), f'{prefix}status__in': OPEN_TASK}
    )


def managed_projects(user):
    if user.role == UserRole.OWNER:
        return Project.objects.all()
    return Project.objects.filter(Q(project_manager=user) | Q(owner=user))


def filter_params(request, qs, **params):
    for param, lookup in params.items():
        value = request.query_params.get(param)
        if value not in (None, ''):
            qs = qs.filter(**{lookup: value})
    return qs


def project_managers(project):
    if project and project.project_manager:
        return [project.project_manager]
    return list(User.objects.filter(role=UserRole.OWNER, is_active=True))


class UserViewSet(viewsets.ModelViewSet):
    queryset = User.objects.all().order_by('first_name', 'username')
    serializer_class = UserSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        if user.role not in MANAGERS:
            projects = ProjectViewSet(request=self.request, action='list').get_queryset()
            qs = qs.filter(Q(pk=user.pk) | Q(managed_projects__in=projects) | Q(role=UserRole.OWNER)).distinct()
        return filter_params(self.request, qs, role='role')

    def get_permissions(self):
        if self.action in ['create', 'destroy', 'update', 'partial_update']:
            return [IsOwnerOrAdmin()]
        return [permissions.IsAuthenticated()]

    def perform_destroy(self, instance):
        if instance == self.request.user:
            from rest_framework.exceptions import ValidationError

            raise ValidationError(_('You cannot delete your own account.'))
        instance.delete()

    @action(detail=False, methods=['get', 'patch'])
    def me(self, request):
        if request.method == 'GET':
            return Response(UserSerializer(request.user).data)
        data = {
            k: v
            for k, v in request.data.items()
            if k
            in (
                'first_name',
                'last_name',
                'email',
                'phone',
                'avatar_url',
                'password',
                'language',
                'telegram_chat_id',
                'telegram_enabled',
            )
        }
        if (
            request.user.two_factor_enabled
            and 'telegram_chat_id' in data
            and data['telegram_chat_id'] != request.user.telegram_chat_id
        ):
            raise ValidationError({'error': _('Turn off two-step sign-in before changing or disconnecting Telegram.')})
        serializer = UserSerializer(request.user, data=data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        result = dict(serializer.data)
        if data.get('password'):
            from rest_framework_simplejwt.tokens import RefreshToken

            refresh = RefreshToken.for_user(request.user)
            refresh['role'] = request.user.role
            result['tokens'] = {'refresh': str(refresh), 'access': str(refresh.access_token)}
        return Response(result)


class ClientViewSet(viewsets.ModelViewSet):
    serializer_class = ClientSerializer

    def get_queryset(self):
        user = self.request.user
        if user.role == UserRole.OWNER:
            return Client.objects.all().order_by('client_name')
        if user.role == UserRole.PROJECT_MANAGER:
            return Client.objects.filter(projects__in=managed_projects(user)).distinct().order_by('client_name')
        return Client.objects.none()

    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [IsOwnerOrAdmin()]
        return [permissions.IsAuthenticated()]


class ProjectViewSet(viewsets.ModelViewSet):
    serializer_class = ProjectSerializer

    def get_serializer_class(self):
        if self.request.user.role not in MANAGERS:
            return ProjectOrderSerializer
        return ProjectSerializer

    def get_queryset(self):
        user = self.request.user
        if user.role in MANAGERS:
            qs = managed_projects(user)
        else:
            qs = Project.objects.filter(
                Q(tasks__assigned_to=user)
                | Q(content_items__assigned_videographer=user)
                | Q(content_items__assigned_editor=user)
            ).distinct()
        qs = filter_params(
            self.request, qs.select_related('client', 'project_manager'), status='status', client='client'
        )
        return qs.order_by('-created_at')

    def get_permissions(self):
        if self.action == 'destroy':
            return [IsOwnerOrAdmin()]
        if self.action in ['create', 'update', 'partial_update']:
            return [IsOwnerOrPM()]
        return [permissions.IsAuthenticated()]

    def perform_destroy(self, instance):
        if instance.status != ProjectStatus.ARCHIVED:
            from rest_framework.exceptions import ValidationError

            raise ValidationError(
                {'error': _('Archive the project first. Projects can only be deleted from the archive.')}
            )
        import logging

        from . import video_storage
        from .models import ChatAttachment, VideoSubmission

        keys = list(
            VideoSubmission.objects.filter(project=instance, deleted=False).values_list('object_key', flat=True)
        )
        keys += list(
            ChatAttachment.objects.filter(task__project=instance, deleted=False).values_list('object_key', flat=True)
        )
        for key in keys:
            try:
                video_storage.delete(key)
            except Exception:
                logging.getLogger('api.video').exception(
                    'Could not delete %s while deleting project %s', key, instance.pk
                )
        log_activity(
            self.request.user, 'PROJECT_DELETED', 'Project', instance.pk, {'name': instance.name, 'files': len(keys)}
        )
        instance.delete()

    def perform_create(self, serializer):
        user = self.request.user
        extra = {'owner': user}
        if user.role == UserRole.PROJECT_MANAGER and not serializer.validated_data.get('project_manager'):
            extra['project_manager'] = user
        project = serializer.save(**extra)
        log_activity(user, 'PROJECT_CREATED', 'Project', project.id, {'name': project.name})
        if project.project_manager and project.project_manager != user:
            notify(
                [project.project_manager],
                gettext_lazy('New project assigned'),
                gettext_lazy('You are the project manager for “%(name)s”.'),
                'project_assignment',
                'Project',
                project.id,
                params={'name': project.name},
            )


class ContractViewSet(viewsets.ModelViewSet):
    serializer_class = ContractSerializer
    permission_classes = [IsOwnerOrAdmin]

    def get_queryset(self):
        qs = Contract.objects.select_related('project__client').order_by('-created_at')
        return filter_params(self.request, qs, project='project')


class TemplateViewSet(viewsets.ModelViewSet):
    """Reusable templates. type='note' are notes templates anyone can save; other types (contracts) stay owner-only."""

    serializer_class = TemplateSerializer

    def get_queryset(self):
        qs = Template.objects.all().order_by('name')
        if self.request.query_params.get('type'):
            qs = qs.filter(type=self.request.query_params['type'])
        if self.request.user.role != UserRole.OWNER:
            qs = qs.filter(type='note')
        return qs

    def perform_create(self, serializer):
        if serializer.validated_data.get('type') != 'note' and self.request.user.role != UserRole.OWNER:
            from rest_framework.exceptions import PermissionDenied

            raise PermissionDenied(_('Only the owner can create this kind of template.'))
        serializer.save(created_by=self.request.user)

    def _check_author(self, template):
        if self.request.user.role != UserRole.OWNER and template.created_by_id != self.request.user.id:
            from rest_framework.exceptions import PermissionDenied

            raise PermissionDenied(_('Only the person who made this template can change or delete it.'))

    def perform_update(self, serializer):
        self._check_author(serializer.instance)
        serializer.save()

    def perform_destroy(self, instance):
        self._check_author(instance)
        instance.delete()


class ContentItemViewSet(viewsets.ModelViewSet):
    serializer_class = ContentItemSerializer

    def get_queryset(self):
        user = self.request.user
        if user.role in MANAGERS:
            qs = ContentItem.objects.filter(project__in=managed_projects(user))
        else:
            qs = ContentItem.objects.filter(Q(assigned_videographer=user) | Q(assigned_editor=user))
        qs = qs.select_related('project__client', 'assigned_videographer', 'assigned_editor')
        return filter_params(self.request, qs, project='project', status='status').order_by('-updated_at')

    def get_permissions(self):
        if self.action in ['create', 'destroy', 'publish', 'start_production']:
            return [IsOwnerOrPM()]
        return [permissions.IsAuthenticated()]

    def perform_create(self, serializer):
        item = serializer.save(created_by=self.request.user)
        log_activity(self.request.user, 'CONTENT_ITEM_CREATED', 'ContentItem', item.id, {'title': item.title})
        notify(
            [item.assigned_videographer, item.assigned_editor],
            gettext_lazy('New content assigned'),
            gettext_lazy('You were assigned to “%(title)s”.'),
            'content_assignment',
            'ContentItem',
            item.id,
            params={'title': item.title},
        )

    def perform_update(self, serializer):
        if 'status' in self.request.data:
            from rest_framework.exceptions import ValidationError

            raise ValidationError({'status': STATUS_LOCKED})
        old = self.get_object()
        old_vg, old_ed = old.assigned_videographer, old.assigned_editor
        item = serializer.save()
        newly = [
            u for u, prev in ((item.assigned_videographer, old_vg), (item.assigned_editor, old_ed)) if u and u != prev
        ]
        notify(
            newly,
            gettext_lazy('New content assigned'),
            gettext_lazy('You were assigned to “%(title)s”.'),
            'content_assignment',
            'ContentItem',
            item.id,
            params={'title': item.title},
        )

    @action(detail=True, methods=['post'], url_path='start-production')
    def start_production(self, request, pk=None):
        from . import workflow

        item = self.get_object()
        tasks = workflow.start_production(item, request.user, request.data)
        for t in tasks:
            if workflow.is_blocked(t):
                notify(
                    [t.assigned_to],
                    gettext_lazy('Upcoming order'),
                    gettext_lazy('“%(title)s” starts after the previous step is approved.'),
                    'task_assignment',
                    'Task',
                    t.id,
                    params={'title': t.title},
                )
            else:
                notify(
                    [t.assigned_to],
                    gettext_lazy('New order'),
                    gettext_lazy('You have a new order: %(title)s'),
                    'task_assignment',
                    'Task',
                    t.id,
                    params={'title': t.title},
                )
        log_activity(request.user, 'PRODUCTION_STARTED', 'ContentItem', item.id, {'tasks': [t.id for t in tasks]})
        return Response(ContentItemSerializer(ContentItem.objects.get(pk=item.pk)).data)

    @action(detail=True, methods=['post'])
    def publish(self, request, pk=None):
        content_item = self.get_object()
        if content_item.status != ContentItemStatus.APPROVED:
            return Response({'error': _('Content must be approved before publishing.')}, status=400)

        post_url = request.data.get('post_url', '')
        PublishRecord.objects.update_or_create(
            content_item=content_item,
            defaults=dict(
                platform=request.data.get('platform') or content_item.platform,
                publish_datetime=timezone.now(),
                post_url=post_url,
                caption_notes=request.data.get('caption_notes', ''),
                published_by=request.user,
            ),
        )
        content_item.status = ContentItemStatus.PUBLISHED
        content_item.publish_url = post_url
        content_item.save()
        log_activity(request.user, 'CONTENT_PUBLISHED', 'ContentItem', content_item.id, {'url': post_url})
        return Response(ContentItemSerializer(content_item).data)


class TaskViewSet(viewsets.ModelViewSet):
    serializer_class = TaskSerializer

    def get_queryset(self):
        user = self.request.user
        if user.role in MANAGERS:
            qs = Task.objects.filter(project__in=managed_projects(user))
        else:
            qs = Task.objects.filter(assigned_to=user)
        qs = qs.select_related('project', 'content_item', 'assigned_to')
        return filter_params(
            self.request, qs, project='project', content_item='content_item', assigned_to='assigned_to'
        ).order_by('due_date')

    def get_permissions(self):
        if self.action in ['create', 'destroy']:
            return [IsOwnerOrPM()]
        return [permissions.IsAuthenticated()]

    def perform_destroy(self, instance):
        item = instance.content_item
        instance.delete()
        from .workflow import refresh_item_status

        refresh_item_status(item)

    def perform_create(self, serializer):
        task = serializer.save(assigned_by=self.request.user)
        from .workflow import refresh_item_status

        refresh_item_status(task.content_item)
        log_activity(self.request.user, 'TASK_ASSIGNED', 'Task', task.id, {'assigned_to': task.assigned_to_id})
        notify(
            [task.assigned_to],
            gettext_lazy('New task assigned'),
            gettext_lazy('You have been assigned a new task: %(title)s'),
            'task_assignment',
            'Task',
            task.id,
            params={'title': task.title},
        )

    def perform_update(self, serializer):
        from rest_framework.exceptions import PermissionDenied, ValidationError

        if self.request.user.role not in MANAGERS:
            raise PermissionDenied(
                _('Orders are changed by the project manager. Use “Start working” or “Submit work”.')
            )
        if 'status' in self.request.data:
            raise ValidationError({'status': STATUS_LOCKED})
        before = self.get_object()
        old_person, old_due = before.assigned_to, before.due_date
        task = serializer.save()
        from .workflow import refresh_item_status

        reassigned = task.assigned_to != old_person
        moved = task.due_date != old_due
        if reassigned:
            if task.status in (TaskStatus.IN_PROGRESS, TaskStatus.OVERDUE):
                task.status = TaskStatus.NOT_STARTED
            if task.content_item_id and task.stage in ('shoot', 'edit'):
                field = 'assigned_videographer' if task.stage == 'shoot' else 'assigned_editor'
                ContentItem.objects.filter(pk=task.content_item_id).update(**{field: task.assigned_to})
        if reassigned or moved:
            task.reminded_due_soon_at = task.reminded_overdue_at = None
            task.save(update_fields=['status', 'reminded_due_soon_at', 'reminded_overdue_at'])
        refresh_item_status(task.content_item)
        p = {'title': task.title, 'name': display_name(self.request.user)}
        if reassigned:
            notify(
                [task.assigned_to],
                gettext_lazy('New task assigned'),
                gettext_lazy('You have been assigned a new task: %(title)s'),
                'task_assignment',
                'Task',
                task.id,
                params=p,
            )
            notify(
                [old_person],
                gettext_lazy('Order reassigned'),
                gettext_lazy(
                    '“%(title)s” was given to someone else by %(name)s. You don’t need to work on it any more.'
                ),
                'task_assignment',
                None,
                None,
                params=p,
            )
            log_activity(
                self.request.user,
                'TASK_REASSIGNED',
                'Task',
                task.id,
                {'from': old_person.id if old_person else None, 'to': task.assigned_to_id},
            )
        elif moved and task.assigned_to:
            p['due'] = telegram.local_time(task.due_date) if task.due_date else gettext_lazy('no deadline')
            notify(
                [task.assigned_to],
                gettext_lazy('Deadline changed'),
                gettext_lazy('New deadline for “%(title)s”: %(due)s'),
                'task_assignment',
                'Task',
                task.id,
                params=p,
            )

    @action(detail=True, methods=['post'])
    def start(self, request, pk=None):
        """The assignee's "Start working" step: New -> In progress. The only manual status step."""
        from .workflow import is_blocked, refresh_item_status

        task = self.get_object()
        if task.assigned_to_id != request.user.id:
            return Response({'error': _('Only the person assigned to this order can start it.')}, status=403)
        if is_blocked(task):
            return Response({'error': _('This order starts after the previous step is approved.')}, status=409)
        updated = Task.objects.filter(pk=task.pk, status=TaskStatus.NOT_STARTED).update(status=TaskStatus.IN_PROGRESS)
        if not updated:
            return Response({'error': _('This order has already been started.')}, status=409)
        task.refresh_from_db()
        refresh_item_status(task.content_item)
        return Response(TaskSerializer(task, context={'request': request}).data)


class OrderChatViewSet(viewsets.ViewSet):
    """Chat per order (task). Anyone who can see the task can read and post:
    the assignee, the project's PM, and owners."""

    permission_classes = [permissions.IsAuthenticated]

    def _task(self, pk):
        task = TaskViewSet(request=self.request, action='retrieve').get_queryset().filter(pk=pk).first()
        if task is None:
            from rest_framework.exceptions import NotFound

            raise NotFound(_('Order not found.'))
        return task

    def _mark_read(self, task):
        OrderChatRead.objects.update_or_create(
            task=task, user=self.request.user, defaults={'last_read_at': timezone.now()}
        )

    @action(detail=True, methods=['post'])
    def attachments(self, request, pk=None):
        import os
        import re

        from django.conf import settings

        from . import video_quota, video_storage

        task = self._task(pk)
        filename = os.path.basename(str(request.data.get('filename') or '').replace('\\', '/')).strip()[:255]
        content_type = str(request.data.get('content_type') or '').strip().lower()
        if not re.match(r'^[\w.+-]+/[\w.+-]+$', content_type):
            content_type = 'application/octet-stream'
        try:
            size = int(request.data.get('size'))
        except (TypeError, ValueError):
            return Response({'error': _('File size is required.')}, status=400)
        if not filename or size <= 0:
            return Response({'error': _('Choose a file to send.')}, status=400)
        limit = settings.CHAT_MAX_ATTACHMENT_BYTES
        if size > limit:
            return Response(
                {
                    'error': _('Files in chat can be up to %(mb)s MB. Use “Submit work” for larger deliveries.')
                    % {'mb': f'{limit / 1e6:.0f}'}
                },
                status=400,
            )
        try:
            att = video_quota.reserve_attachment(
                task=task, uploader=request.user, size=size, filename=filename, content_type=content_type
            )
            url = video_storage.presign_put(att.object_key, content_type)
        except video_quota.QueueFull as e:
            return Response({'error': str(e), 'code': 'queue_full'}, status=507)
        except Exception:
            import logging

            logging.getLogger('api.video').exception('Chat attachment init failed')
            return Response({'error': _('File storage is unavailable right now.')}, status=503)
        return Response({'id': att.id, 'upload_url': url, 'content_type': content_type}, status=201)

    def _confirm_attachment(self, task, att_id):
        from rest_framework.exceptions import ValidationError

        from . import video_storage
        from .models import ChatAttachment

        att = ChatAttachment.objects.filter(
            pk=att_id, task=task, uploader=self.request.user, ready=False, deleted=False
        ).first()
        if att is None:
            raise ValidationError({'error': _('That file is not available. Please attach it again.')})
        meta = video_storage.head(att.object_key)
        if meta is None or meta['size'] > att.size_bytes:
            if meta is not None:
                video_storage.delete(att.object_key)
            ChatAttachment.objects.filter(pk=att.pk).update(deleted=True)
            raise ValidationError({'error': _('The file upload did not complete. Please attach it again.')})
        att.size_bytes, att.ready = meta['size'], True
        att.save(update_fields=['size_bytes', 'ready'])
        return att

    @action(detail=True, methods=['get', 'post'])
    def messages(self, request, pk=None):
        task = self._task(pk)
        if request.method == 'POST':
            body = str(request.data.get('body') or '').strip()
            att_id = request.data.get('attachment')
            if not body and not att_id:
                return Response({'error': _('Message is empty.')}, status=400)
            att = self._confirm_attachment(task, att_id) if att_id else None
            msg = OrderMessage.objects.create(task=task, sender=request.user, body=body[:5000], attachment=att)
            telegram.notify_chat_message(msg)
            self._mark_read(task)
            return Response(OrderMessageSerializer(msg).data, status=201)
        self._mark_read(task)
        return Response(OrderMessageSerializer(task.messages.select_related('sender', 'attachment'), many=True).data)

    def list(self, request):
        user = request.user
        tasks = TaskViewSet(request=request, action='list').get_queryset().select_related('project', 'assigned_to')
        if user.role in MANAGERS:
            tasks = tasks.filter(messages__isnull=False).distinct()
        else:
            tasks = tasks.exclude(status=TaskStatus.CANCELLED)
        rows = []
        for t in tasks:
            last = t.messages.select_related('sender').order_by('-created_at').first()
            preview = (last.body or (f'📎 {last.attachment.filename}' if last.attachment else '')) if last else ''
            rows.append(
                {
                    'task': t.id,
                    'title': t.title,
                    'project_name': t.project.name,
                    'status': t.status,
                    'with_name': display_name(t.assigned_to)
                    if user.role in MANAGERS
                    else display_name(t.project.project_manager) or 'Project manager',
                    'last_message': preview[:120],
                    'last_sender': display_name(last.sender) if last else None,
                    'last_at': last.created_at if last else None,
                    'unread': unread_count(t, user),
                }
            )
        rows.sort(key=lambda r: (r['last_at'] is not None, r['last_at'] or timezone.now()), reverse=True)
        return Response(rows)

    @action(detail=False, methods=['get'])
    def unread(self, request):
        tasks = TaskViewSet(request=request, action='list').get_queryset().filter(messages__isnull=False).distinct()
        return Response({'unread': sum(unread_count(t, request.user) for t in tasks)})


class TaskChecklistItemViewSet(viewsets.ModelViewSet):
    serializer_class = TaskChecklistItemSerializer

    def get_queryset(self):
        tasks = TaskViewSet(request=self.request, action='list').get_queryset()
        return filter_params(self.request, TaskChecklistItem.objects.filter(task__in=tasks), task='task').order_by(
            'order_index', 'id'
        )

    def perform_create(self, serializer):
        tasks = TaskViewSet(request=self.request, action='list').get_queryset()
        if not tasks.filter(pk=serializer.validated_data['task'].pk).exists():
            from rest_framework.exceptions import PermissionDenied

            raise PermissionDenied(_('Not your order.'))
        serializer.save()


class SubmissionRecordViewSet(viewsets.ModelViewSet):
    serializer_class = SubmissionRecordSerializer

    def get_queryset(self):
        user = self.request.user
        if user.role in MANAGERS:
            projects = managed_projects(user)
            qs = SubmissionRecord.objects.filter(Q(content_item__project__in=projects) | Q(task__project__in=projects))
        else:
            qs = SubmissionRecord.objects.filter(
                Q(submitted_by=user)
                | Q(content_item__assigned_videographer=user)
                | Q(content_item__assigned_editor=user)
            )
        qs = filter_params(self.request, qs.distinct(), content_item='content_item', task='task')
        return qs.select_related('submitted_by').order_by('-created_at')

    def perform_create(self, serializer):
        serializer.save(submitted_by=self.request.user)


class RevisionViewSet(viewsets.ModelViewSet):
    serializer_class = RevisionSerializer

    def get_queryset(self):
        user = self.request.user
        if user.role in MANAGERS:
            qs = Revision.objects.filter(content_item__project__in=managed_projects(user))
        else:
            qs = Revision.objects.filter(
                Q(assigned_to=user)
                | Q(content_item__assigned_videographer=user)
                | Q(content_item__assigned_editor=user)
            )
        return filter_params(self.request, qs.distinct(), content_item='content_item').order_by('-created_at')

    def get_permissions(self):
        if self.action in ['create', 'destroy']:
            return [IsOwnerOrPM()]
        return [permissions.IsAuthenticated()]

    def perform_create(self, serializer):
        serializer.save(requested_by=self.request.user)


class CommentViewSet(viewsets.ModelViewSet):
    serializer_class = CommentSerializer

    def get_queryset(self):
        qs = Comment.objects.select_related('author').order_by('created_at')
        return filter_params(self.request, qs, entity_type='entity_type', entity_id='entity_id')

    def perform_create(self, serializer):
        serializer.save(author=self.request.user)

    def perform_destroy(self, instance):
        if instance.author != self.request.user and self.request.user.role != UserRole.OWNER:
            from rest_framework.exceptions import PermissionDenied

            raise PermissionDenied(_('You can only delete your own comments.'))
        instance.delete()


class NotificationViewSet(viewsets.ModelViewSet):
    serializer_class = NotificationSerializer
    http_method_names = ['get', 'patch', 'delete', 'post']

    def get_queryset(self):
        return Notification.objects.filter(recipient_user=self.request.user).order_by('-created_at')

    def create(self, request, *args, **kwargs):
        return Response({'error': _('Notifications are created by the system.')}, status=405)

    @action(detail=False, methods=['post'])
    def mark_all_read(self, request):
        self.get_queryset().filter(is_read=False).update(is_read=True)
        return Response({'status': 'ok'})


class ActivityLogViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = ActivityLogSerializer
    permission_classes = [IsOwnerOrAdmin]

    def get_queryset(self):
        return ActivityLog.objects.select_related('user').order_by('-created_at')[:200]


class PublishRecordViewSet(viewsets.ModelViewSet):
    serializer_class = PublishRecordSerializer

    def get_queryset(self):
        user = self.request.user
        if user.role in MANAGERS:
            return PublishRecord.objects.filter(content_item__project__in=managed_projects(user))
        return PublishRecord.objects.none()


def pipeline_counts(items):
    counts = dict(items.values_list('status').annotate(n=Count('id')))
    return {s: counts.get(s, 0) for s in ContentItemStatus.values}


def review_items(projects):
    from .models import VideoSubmission

    qs = (
        VideoSubmission.objects.filter(project__in=projects, status='pending')
        .select_related('project__client', 'content_item', 'uploader')
        .order_by('created_at')[:10]
    )
    return [
        {
            'id': s.id,
            'title': s.content_item.title if s.content_item else s.project.name,
            'content_type': s.original_filename,
            'platform': f'v{s.version}',
            'project_name': s.project.name,
            'client_name': s.project.client.client_name,
            'updated_at': s.created_at,
        }
        for s in qs
    ]


def pending_reviews(projects):
    from .models import VideoSubmission

    return VideoSubmission.objects.filter(project__in=projects, status='pending').count()


class DashboardViewSet(viewsets.ViewSet):
    permission_classes = [permissions.IsAuthenticated]

    @action(detail=False, methods=['get'])
    def metrics(self, request):
        user = request.user

        from .reports import period, today_numbers

        day_start, day_end = period(request.query_params, default_days=1)

        if user.role == UserRole.OWNER:
            active_projs = Project.objects.filter(status=ProjectStatus.ACTIVE)
            open_tasks = Task.objects.filter(status__in=OPEN_TASK + [TaskStatus.OVERDUE])
            items = ContentItem.objects.all()
            return Response(
                {
                    'active_projects': active_projs.count(),
                    'pending_approvals': pending_reviews(Project.objects.all()),
                    'overdue_tasks': Task.objects.filter(overdue_q()).count(),
                    'open_tasks': open_tasks.count(),
                    'recent_submissions': [
                        {
                            'id': s.id,
                            'content_item': s.content_item_id,
                            'content_item__title': s.content_item.title
                            if s.content_item
                            else (s.task.title if s.task else ''),
                            'submitted_by_name': display_name(s.submitted_by),
                            'created_at': s.created_at,
                        }
                        for s in SubmissionRecord.objects.select_related(
                            'content_item', 'task', 'submitted_by'
                        ).order_by('-created_at')[:5]
                    ],
                    'revenue': active_projs.aggregate(total=Sum('service_fee'))['total'] or 0,
                    'portfolio': list(
                        active_projs.order_by('-created_at')[:5].values(
                            'id', 'name', 'client__client_name', 'status', 'end_date'
                        )
                    ),
                    'pipeline': pipeline_counts(items),
                    'review_items': review_items(Project.objects.all()),
                    'today': today_numbers(Task.objects.all(), items, day_start, day_end),
                }
            )

        if user.role == UserRole.PROJECT_MANAGER:
            projects = managed_projects(user)
            items = ContentItem.objects.filter(project__in=projects)
            return Response(
                {
                    'assigned_projects': projects.exclude(status=ProjectStatus.ARCHIVED).count(),
                    'review_queue': pending_reviews(projects),
                    'open_revisions': Revision.objects.filter(
                        content_item__project__in=projects, status__in=OPEN_REVISION
                    ).count(),
                    'overdue_tasks': Task.objects.filter(overdue_q(), project__in=projects).count(),
                    'pipeline': pipeline_counts(items),
                    'review_items': review_items(projects),
                    'today': today_numbers(Task.objects.filter(project__in=projects), items, day_start, day_end),
                }
            )

        if user.role in (UserRole.VIDEOGRAPHER, UserRole.EDITOR):
            tasks = Task.objects.filter(assigned_to=user)
            return Response(
                {
                    'assigned_tasks': tasks.filter(status__in=OPEN_TASK).count(),
                    'open_revisions': Revision.objects.filter(assigned_to=user, status__in=OPEN_REVISION).count(),
                    'overdue_tasks': tasks.filter(overdue_q()).count(),
                }
            )

        return Response({'error': _('Role not recognized.')}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=['get'])
    def search(self, request):
        q = (request.query_params.get('q') or '').strip()
        if len(q) < 2:
            return Response({'projects': [], 'clients': [], 'content_items': [], 'tasks': []})
        projects = ProjectViewSet(request=request, action='list').get_queryset()
        items = ContentItemViewSet(request=request, action='list').get_queryset()
        tasks = TaskViewSet(request=request, action='list').get_queryset()
        clients = ClientViewSet(request=request, action='list').get_queryset()
        return Response(
            {
                'projects': list(
                    projects.filter(Q(name__icontains=q) | Q(client__client_name__icontains=q)).values(
                        'id', 'name', 'status'
                    )[:8]
                ),
                'clients': list(
                    clients.filter(
                        Q(client_name__icontains=q) | Q(brand_name__icontains=q) | Q(niche__icontains=q)
                    ).values('id', 'client_name', 'niche')[:8]
                ),
                'content_items': list(items.filter(title__icontains=q).values('id', 'title', 'status', 'platform')[:8]),
                'tasks': list(tasks.filter(title__icontains=q).values('id', 'title', 'status', 'content_item')[:8]),
            }
        )

    @action(detail=False, methods=['get'], permission_classes=[IsOwnerOrAdmin])
    def reports(self, request):
        """Filters: start, end (ISO, the viewer's local boundaries), tz (minutes east of UTC), client, project, member."""
        from .reports import build_report

        return Response(build_report(request.query_params))
