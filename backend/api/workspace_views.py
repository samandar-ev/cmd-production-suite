from datetime import datetime, time, timedelta
from datetime import timezone as dt_timezone

from django.db.models import Q
from django.utils import timezone
from django.utils.dateparse import parse_date
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy
from rest_framework import permissions, serializers, viewsets
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response

from .models import CalendarEvent, ContentItem, TaskStatus, WorkspacePage, WorkspaceTodo
from .serializers import display_name
from .views import MANAGERS, TaskViewSet, managed_projects, notify


def can_manage(user, project):
    return project is not None and user.role in MANAGERS and managed_projects(user).filter(pk=project.pk).exists()


class PageSerializer(serializers.ModelSerializer):
    project_name = serializers.CharField(source='project.name', read_only=True, default=None)
    updated_by_name = serializers.SerializerMethodField()

    class Meta:
        model = WorkspacePage
        fields = [
            'id',
            'project',
            'project_name',
            'title',
            'icon',
            'body',
            'created_by',
            'updated_by',
            'updated_by_name',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['created_by', 'updated_by']

    def get_updated_by_name(self, obj):
        return display_name(obj.updated_by or obj.created_by)


class TodoSerializer(serializers.ModelSerializer):
    project_name = serializers.CharField(source='project.name', read_only=True, default=None)
    assignee_name = serializers.SerializerMethodField()

    class Meta:
        model = WorkspaceTodo
        fields = [
            'id',
            'project',
            'project_name',
            'title',
            'notes',
            'section',
            'due_date',
            'priority',
            'completed',
            'completed_at',
            'assignee',
            'assignee_name',
            'order_index',
            'created_by',
            'created_at',
        ]
        read_only_fields = ['created_by', 'completed_at']

    def get_assignee_name(self, obj):
        return display_name(obj.assignee) if obj.assignee else None


class EventSerializer(serializers.ModelSerializer):
    project_name = serializers.CharField(source='project.name', read_only=True, default=None)
    attendee_names = serializers.SerializerMethodField()
    created_by_name = serializers.SerializerMethodField()

    class Meta:
        model = CalendarEvent
        fields = [
            'id',
            'project',
            'project_name',
            'title',
            'notes',
            'location',
            'start',
            'end',
            'all_day',
            'attendees',
            'attendee_names',
            'created_by',
            'created_by_name',
            'created_at',
        ]
        read_only_fields = ['created_by']

    def get_attendee_names(self, obj):
        return [display_name(u) for u in obj.attendees.all()]

    def get_created_by_name(self, obj):
        return display_name(obj.created_by)

    def validate(self, data):
        start = data.get('start', getattr(self.instance, 'start', None))
        end = data.get('end', getattr(self.instance, 'end', None))
        if start and end and end < start:
            raise ValidationError({'end': _('The event must end after it starts.')})
        return data


def _check_project(user, project):
    if project is not None and not can_manage(user, project):
        raise PermissionDenied(_('Only the managers of this project can add to its workspace.'))


class PageViewSet(viewsets.ModelViewSet):
    serializer_class = PageSerializer

    def get_queryset(self):
        user = self.request.user
        mine = Q(project__isnull=True, created_by=user)
        qs = (
            WorkspacePage.objects.filter(mine | Q(project__in=managed_projects(user)))
            if user.role in MANAGERS
            else WorkspacePage.objects.filter(mine)
        )
        project = self.request.query_params.get('project')
        if project == 'personal':
            qs = qs.filter(project__isnull=True)
        elif project:
            qs = qs.filter(project=project)
        return qs.select_related('project', 'updated_by', 'created_by')

    def perform_create(self, serializer):
        _check_project(self.request.user, serializer.validated_data.get('project'))
        serializer.save(created_by=self.request.user, updated_by=self.request.user)

    def perform_update(self, serializer):
        if 'project' in serializer.validated_data:
            _check_project(self.request.user, serializer.validated_data['project'])
        serializer.save(updated_by=self.request.user)


class TodoViewSet(viewsets.ModelViewSet):
    serializer_class = TodoSerializer

    def get_queryset(self):
        user = self.request.user
        q = Q(project__isnull=True, created_by=user) | Q(assignee=user)
        if user.role in MANAGERS:
            q |= Q(project__in=managed_projects(user))
        qs = WorkspaceTodo.objects.filter(q).distinct().select_related('project', 'assignee')
        params = self.request.query_params
        project = params.get('project')
        if project == 'personal':
            qs = qs.filter(project__isnull=True, created_by=user)
        elif project:
            qs = qs.filter(project=project)
        if params.get('view') == 'mine':
            qs = qs.filter(
                Q(assignee=user)
                | Q(assignee__isnull=True, created_by=user)
                | Q(assignee__isnull=True, project__isnull=True, created_by=user)
            )
        if params.get('completed') in ('0', 'false'):
            qs = qs.filter(completed=False)
        return qs

    def _can_edit(self, todo):
        user = self.request.user
        if todo.project_id:
            return can_manage(user, todo.project)
        return todo.created_by_id == user.id

    def perform_create(self, serializer):
        user = self.request.user
        project = serializer.validated_data.get('project')
        _check_project(user, project)
        assignee = serializer.validated_data.get('assignee')
        if assignee and assignee != user and project is None:
            raise ValidationError(
                {'assignee': _('Personal to-dos are for yourself. Add it to a project to assign it.')}
            )
        todo = serializer.save(created_by=user)
        if todo.assignee and todo.assignee != user:
            notify(
                [todo.assignee],
                gettext_lazy('New to-do'),
                gettext_lazy('%(name)s gave you a to-do: %(title)s'),
                'todo',
                'Todo',
                todo.id,
                params={'name': display_name(user), 'title': todo.title},
            )

    def perform_update(self, serializer):
        todo = serializer.instance
        data = serializer.validated_data
        if not self._can_edit(todo):
            if todo.assignee_id != self.request.user.id or set(data) - {'completed'}:
                raise PermissionDenied(_('You can only mark this to-do as done.'))
        if 'project' in data and data['project'] != todo.project:
            _check_project(self.request.user, data['project'])
        extra = {}
        if 'completed' in data:
            extra['completed_at'] = timezone.now() if data['completed'] else None
        serializer.save(**extra)

    def perform_destroy(self, instance):
        if not self._can_edit(instance):
            raise PermissionDenied(_('You can’t delete this to-do.'))
        instance.delete()


class EventViewSet(viewsets.ModelViewSet):
    serializer_class = EventSerializer

    def get_queryset(self):
        user = self.request.user
        q = Q(created_by=user) | Q(attendees=user)
        if user.role in MANAGERS:
            q |= Q(project__in=managed_projects(user))
        return (
            CalendarEvent.objects.filter(q)
            .distinct()
            .select_related('project', 'created_by')
            .prefetch_related('attendees')
        )

    def _can_edit(self, event):
        user = self.request.user
        return event.created_by_id == user.id or (event.project and can_manage(user, event.project))

    def _clean_attendees(self, serializer):
        user = self.request.user
        if user.role not in MANAGERS:
            serializer.validated_data['attendees'] = [user]
        _check_project(user, serializer.validated_data.get('project'))

    def perform_create(self, serializer):
        self._clean_attendees(serializer)
        event = serializer.save(created_by=self.request.user)
        others = [u for u in event.attendees.all() if u != self.request.user]
        when = (
            timezone.localtime(event.start).strftime('%b %d, %H:%M')
            if not event.all_day
            else event.start.strftime('%b %d')
        )
        notify(
            others,
            gettext_lazy('New event'),
            gettext_lazy('%(name)s invited you: %(title)s · %(when)s'),
            'event',
            'Event',
            event.id,
            params={'name': display_name(self.request.user), 'title': event.title, 'when': when},
        )

    def perform_update(self, serializer):
        if not self._can_edit(serializer.instance):
            raise PermissionDenied(_('Only the organiser or the project’s manager can change this event.'))
        if 'attendees' in serializer.validated_data or 'project' in serializer.validated_data:
            self._clean_attendees(serializer)
        serializer.save()

    def perform_destroy(self, instance):
        if not self._can_edit(instance):
            raise PermissionDenied(_('Only the organiser or the project’s manager can delete this event.'))
        instance.delete()


class CalendarViewSet(viewsets.ViewSet):
    """GET /calendar/?start=YYYY-MM-DD&end=YYYY-MM-DD[&project=id] -> everything planned in that range."""

    permission_classes = [permissions.IsAuthenticated]

    def list(self, request):
        start = parse_date(request.query_params.get('start') or '')
        end = parse_date(request.query_params.get('end') or '')
        if not start or not end or end < start or (end - start).days > 62:
            raise ValidationError({'error': _('Pass start and end dates (at most about 2 months apart).')})
        try:
            tz = dt_timezone(timedelta(minutes=int(request.query_params['tz'])))
        except (KeyError, ValueError, OverflowError):
            tz = timezone.get_current_timezone()
        start_dt = timezone.make_aware(datetime.combine(start, time.min), tz)
        end_dt = timezone.make_aware(datetime.combine(end + timedelta(days=1), time.min), tz)
        project = request.query_params.get('project')
        user = request.user
        manager = user.role in MANAGERS
        items = []

        tasks = (
            TaskViewSet(request=request, action='list')
            .get_queryset()
            .filter(due_date__gte=start_dt, due_date__lt=end_dt)
            .exclude(status=TaskStatus.CANCELLED)
        )
        if project:
            tasks = tasks.filter(project=project)
        for t in tasks.select_related('project', 'assigned_to'):
            items.append(
                {
                    'id': f'order-{t.id}',
                    'type': 'order',
                    'ref': t.id,
                    'title': t.title,
                    'start': t.due_date,
                    'all_day': False,
                    'project': t.project_id,
                    'project_name': t.project.name,
                    'who': display_name(t.assigned_to),
                    'status': t.status,
                    'stage': t.stage,
                    'can_move': manager,
                    'link': f'/orders/{t.id}',
                }
            )

        if manager:
            content = ContentItem.objects.filter(project__in=managed_projects(user))
        else:
            content = ContentItem.objects.filter(Q(assigned_videographer=user) | Q(assigned_editor=user))
        content = content.filter(target_publish_date__gte=start_dt, target_publish_date__lt=end_dt)
        if project:
            content = content.filter(project=project)
        for c in content.select_related('project'):
            items.append(
                {
                    'id': f'publish-{c.id}',
                    'type': 'publish',
                    'ref': c.id,
                    'title': _('Publish: %(title)s') % {'title': c.title},
                    'start': c.target_publish_date,
                    'all_day': True,
                    'project': c.project_id,
                    'project_name': c.project.name,
                    'status': c.status,
                    'platform': c.platform,
                    'can_move': manager,
                    'link': f'/content/{c.id}' if manager else None,
                }
            )

        todos = (
            TodoViewSet(request=request, action='list').get_queryset().filter(due_date__gte=start, due_date__lte=end)
        )
        if project:
            todos = todos.filter(project=project)
        for t in todos:
            can = can_manage(user, t.project) if t.project_id else t.created_by_id == user.id
            items.append(
                {
                    'id': f'todo-{t.id}',
                    'type': 'todo',
                    'ref': t.id,
                    'title': t.title,
                    'start': t.due_date,
                    'all_day': True,
                    'project': t.project_id,
                    'project_name': t.project.name if t.project else _('Personal'),
                    'completed': t.completed,
                    'priority': t.priority,
                    'who': display_name(t.assignee) if t.assignee else None,
                    'can_move': can,
                    'can_toggle': can or t.assignee_id == user.id,
                }
            )

        events = EventViewSet(request=request, action='list').get_queryset().filter(start__lt=end_dt, end__gte=start_dt)
        if project:
            events = events.filter(project=project)
        for e in events:
            items.append(
                {
                    'id': f'event-{e.id}',
                    'type': 'event',
                    'ref': e.id,
                    'title': e.title,
                    'start': e.start,
                    'end': e.end,
                    'all_day': e.all_day,
                    'project': e.project_id,
                    'project_name': e.project.name if e.project else _('Personal'),
                    'location': e.location,
                    'notes': e.notes,
                    'who': ', '.join(display_name(u) for u in e.attendees.all()),
                    'organiser': display_name(e.created_by),
                    'can_move': e.created_by_id == user.id or (e.project_id and can_manage(user, e.project)),
                }
            )
        return Response(items)
