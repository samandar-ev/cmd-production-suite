from datetime import timedelta

from django.db.models import Count, Q, Sum
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from rest_framework.exceptions import ValidationError

from .models import (
    ActivityLog,
    ContentItem,
    ContentStatusChange,
    Project,
    Revision,
    Task,
    TaskStatus,
    Transaction,
    User,
    UserRole,
)
from .models import ContentItemStatus as CS
from .serializers import ActivityLogSerializer, display_name

OPEN = [TaskStatus.NOT_STARTED, TaskStatus.IN_PROGRESS, TaskStatus.OVERDUE, TaskStatus.REJECTED]
IN_PRODUCTION = [
    CS.READY_FOR_SHOOTING,
    CS.SHOOTING,
    CS.READY_FOR_EDITING,
    CS.EDITING,
    CS.UNDER_REVIEW,
    CS.REVISION_REQUESTED,
]


def period(params, default_days=30):
    now = timezone.now()
    start, end = parse_datetime(params.get('start') or ''), parse_datetime(params.get('end') or '')
    end = end or now
    start = start or end - timedelta(days=default_days)
    if start >= end:
        raise ValidationError({'end': 'End must be after start.'})
    return start, end


def today_numbers(tasks, items, start, end):
    now = timezone.now()
    due = tasks.filter(due_date__gte=start, due_date__lt=end).exclude(status=TaskStatus.CANCELLED)
    return {
        'active_tasks': tasks.filter(status__in=OPEN).count(),
        'in_review_tasks': tasks.filter(status=TaskStatus.WAITING_FOR_REVIEW).count(),
        'due_today': due.count(),
        'due_today_done': due.filter(status=TaskStatus.COMPLETED).count(),
        'done_today': tasks.filter(completed_at__gte=start, completed_at__lt=end).count(),
        'overdue': tasks.filter(Q(status=TaskStatus.OVERDUE) | Q(status__in=OPEN, due_date__lt=now)).count(),
        'published_today': ContentStatusChange.objects.filter(
            content_item__in=items, status=CS.PUBLISHED, changed_at__gte=start, changed_at__lt=end
        ).count(),
        'moved_today': ContentStatusChange.objects.filter(
            content_item__in=items, changed_at__gte=start, changed_at__lt=end
        )
        .values('content_item')
        .distinct()
        .count(),
    }


def _avg_days(pairs):
    pairs = [(a, b) for a, b in pairs if a and b and b >= a]
    return round(sum((b - a).total_seconds() for a, b in pairs) / len(pairs) / 86400, 1) if pairs else None


def _kpis(projects, items, tasks, member, start, end):
    done = tasks.filter(completed_at__gte=start, completed_at__lt=end)
    done_rows = list(done.values('id', 'created_at', 'completed_at', 'due_date'))
    with_due = [t for t in done_rows if t['due_date']]
    published = ContentStatusChange.objects.filter(
        content_item__in=items, status=CS.PUBLISHED, changed_at__gte=start, changed_at__lt=end
    ).select_related('content_item')
    revisions = Revision.objects.filter(content_item__in=items, created_at__gte=start, created_at__lt=end)
    if member:
        revisions = revisions.filter(assigned_to=member)
    revised_tasks = set(Revision.objects.filter(task__in=[t['id'] for t in done_rows]).values_list('task', flat=True))
    income = Transaction.objects.filter(type='income', date__gte=start.date(), date__lt=end.date() + timedelta(days=1))
    if projects is not None:
        income = income.filter(Q(project__in=projects) | Q(project__isnull=True, client__in=projects.values('client')))
    return {
        'content_created': items.filter(created_at__gte=start, created_at__lt=end).count(),
        'content_published': published.values('content_item').distinct().count(),
        'content_approved': ContentStatusChange.objects.filter(
            content_item__in=items, status=CS.APPROVED, changed_at__gte=start, changed_at__lt=end
        )
        .values('content_item')
        .distinct()
        .count(),
        'orders_completed': len(done_rows),
        'on_time_rate': round(100 * sum(t['completed_at'] <= t['due_date'] for t in with_due) / len(with_due))
        if with_due
        else None,
        'first_pass_rate': round(100 * sum(t['id'] not in revised_tasks for t in done_rows) / len(done_rows))
        if done_rows
        else None,
        'avg_order_days': _avg_days((t['created_at'], t['completed_at']) for t in done_rows),
        'avg_publish_days': _avg_days((c.content_item.created_at, c.changed_at) for c in published),
        'revisions': revisions.count(),
        'income': income.aggregate(s=Sum('amount'))['s'] or 0,
    }


def build_report(params):
    start, end = period(params)
    span = end - start
    tz = timedelta(minutes=int(params.get('tz') or 0))
    member = User.objects.filter(pk=params.get('member')).first() if params.get('member') else None

    projects = Project.objects.all()
    filtered = bool(params.get('client') or params.get('project'))
    if params.get('client'):
        projects = projects.filter(client=params['client'])
    if params.get('project'):
        projects = projects.filter(pk=params['project'])
    items = ContentItem.objects.filter(project__in=projects)
    tasks = Task.objects.filter(project__in=projects)
    if member:
        tasks = tasks.filter(assigned_to=member)
        items = items.filter(
            Q(assigned_editor=member) | Q(assigned_videographer=member) | Q(tasks__assigned_to=member)
        ).distinct()
    now = timezone.now()

    weekly = span > timedelta(days=62)

    def bucket(dt):
        d = (dt + tz).date()
        return d - timedelta(days=d.weekday()) if weekly else d

    first, last = bucket(start), bucket(end - timedelta(microseconds=1))
    trend, d = {}, first
    while d <= last:
        trend[d] = {'created': 0, 'published': 0, 'completed': 0}
        d += timedelta(days=7 if weekly else 1)
    for at in items.filter(created_at__gte=start, created_at__lt=end).values_list('created_at', flat=True):
        trend.setdefault(bucket(at), {'created': 0, 'published': 0, 'completed': 0})['created'] += 1
    for at in ContentStatusChange.objects.filter(
        content_item__in=items, status=CS.PUBLISHED, changed_at__gte=start, changed_at__lt=end
    ).values_list('changed_at', flat=True):
        trend.setdefault(bucket(at), {'created': 0, 'published': 0, 'completed': 0})['published'] += 1
    for at in tasks.filter(completed_at__gte=start, completed_at__lt=end).values_list('completed_at', flat=True):
        trend.setdefault(bucket(at), {'created': 0, 'published': 0, 'completed': 0})['completed'] += 1

    team_qs = User.objects.filter(role__in=[UserRole.VIDEOGRAPHER, UserRole.EDITOR], is_active=True)
    if member:
        team_qs = team_qs.filter(pk=member.pk)
    team = []
    for u in team_qs.order_by('first_name', 'username'):
        mine = Task.objects.filter(project__in=projects, assigned_to=u)
        done = list(
            mine.filter(completed_at__gte=start, completed_at__lt=end).values('created_at', 'completed_at', 'due_date')
        )
        with_due = [t for t in done if t['due_date']]
        team.append(
            {
                'id': u.id,
                'name': display_name(u),
                'role': u.role,
                'completed': len(done),
                'on_time_rate': round(100 * sum(t['completed_at'] <= t['due_date'] for t in with_due) / len(with_due))
                if with_due
                else None,
                'avg_days': _avg_days((t['created_at'], t['completed_at']) for t in done),
                'revisions': Revision.objects.filter(
                    assigned_to=u, content_item__project__in=projects, created_at__gte=start, created_at__lt=end
                ).count(),
                'open': mine.filter(status__in=OPEN).count(),
                'in_review': mine.filter(status=TaskStatus.WAITING_FOR_REVIEW).count(),
                'overdue': mine.filter(Q(status=TaskStatus.OVERDUE) | Q(status__in=OPEN, due_date__lt=now)).count(),
            }
        )

    project_rows = []
    for p in projects.select_related('client').order_by('status', 'name'):
        p_items = items.filter(project=p)
        p_tasks = tasks.filter(project=p)
        published = (
            ContentStatusChange.objects.filter(
                content_item__in=p_items, status=CS.PUBLISHED, changed_at__gte=start, changed_at__lt=end
            )
            .values('content_item')
            .distinct()
            .count()
        )
        row = {
            'id': p.id,
            'name': p.name,
            'client': p.client.client_name,
            'status': p.status,
            'fee': p.service_fee,
            'end_date': p.end_date,
            'content_total': p_items.count(),
            'published_in_period': published,
            'done_total': p_items.filter(status__in=[CS.APPROVED, CS.PUBLISHED, CS.COMPLETED]).count(),
            'in_production': p_items.filter(status__in=IN_PRODUCTION).count(),
            'overdue_orders': p_tasks.filter(
                Q(status=TaskStatus.OVERDUE) | Q(status__in=OPEN, due_date__lt=now)
            ).count(),
            'revisions': Revision.objects.filter(
                content_item__in=p_items, created_at__gte=start, created_at__lt=end
            ).count(),
        }
        if filtered or member or p.status in ('active', 'on_hold') or published or row['revisions']:
            project_rows.append(row)

    activity = ActivityLog.objects.select_related('user').filter(created_at__gte=start, created_at__lt=end)
    if filtered or member:
        refs = (
            Q(entity_type='Project', entity_id__in=projects.values('id'))
            | Q(entity_type='ContentItem', entity_id__in=items.values('id'))
            | Q(entity_type='Task', entity_id__in=tasks.values('id'))
        )
        activity = activity.filter(refs)
    if member:
        activity = activity.filter(Q(user=member) | Q(entity_type='Task', entity_id__in=tasks.values('id')))

    scoped = projects if (filtered or member) else None
    return {
        'period': {'start': start, 'end': end, 'weekly': weekly},
        'kpis': _kpis(scoped, items, tasks, member, start, end),
        'previous': _kpis(scoped, items, tasks, member, start - span, start),
        'now': {
            'active_projects': projects.filter(status='active').count(),
            'open_orders': tasks.filter(status__in=OPEN).count(),
            'in_review': tasks.filter(status=TaskStatus.WAITING_FOR_REVIEW).count(),
            'overdue_orders': tasks.filter(Q(status=TaskStatus.OVERDUE) | Q(status__in=OPEN, due_date__lt=now)).count(),
            'pipeline': dict(items.values_list('status').annotate(n=Count('id'))),
        },
        'trend': [{'date': k, **v} for k, v in sorted(trend.items())],
        'team': team,
        'projects': project_rows,
        'activity': ActivityLogSerializer(activity.order_by('-created_at')[:30], many=True).data,
    }
