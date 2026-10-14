from datetime import timedelta

from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from api.models import Client, ContentItem, ContentStatusChange, Project, Revision, Task, User


class ReportsTest(TestCase):
    def test_stage_times_today_and_report(self):
        owner = User.objects.create_user('o', password='x', role='OWNER')
        ed = User.objects.create_user('e', password='x', role='EDITOR', first_name='Ed')
        owner_api = APIClient()
        owner_api.force_authenticate(owner)
        a = Project.objects.create(
            client=Client.objects.create(client_name='A', contact_person='-'), name='PA', status='active'
        )
        b = Project.objects.create(
            client=Client.objects.create(client_name='B', contact_person='-'), name='PB', status='active'
        )

        item = ContentItem.objects.create(project=a, title='Reel', content_type='Reel', platform='IG')
        assert item.status_changed_at and item.status_changes.count() == 1
        first = item.status_changed_at
        item = ContentItem.objects.get(pk=item.pk)
        item.title = 'Reel 2'
        item.save()
        assert item.status_changed_at == first and item.status_changes.count() == 1
        ContentItem.set_status(item.pk, 'editing')
        item.refresh_from_db()
        assert item.status == 'editing' and item.status_changed_at > first and item.status_changes.count() == 2
        ContentItem.set_status(item.pk, 'editing')
        assert item.status_changes.count() == 2
        item.status = 'published'
        item.save(update_fields=['status'])
        item.refresh_from_db()
        assert item.status_changes.filter(status='published').exists() and item.status_changed_at

        now = timezone.now()
        day = {'start': (now - timedelta(hours=1)).isoformat(), 'end': (now + timedelta(hours=1)).isoformat()}
        Task.objects.create(
            project=a, title='due now', task_type='Edit', assigned_to=ed, due_date=now + timedelta(minutes=30)
        )
        Task.objects.create(
            project=a,
            title='done now',
            task_type='Edit',
            assigned_to=ed,
            status='completed',
            completed_at=now,
            due_date=now + timedelta(minutes=10),
        )
        late = Task.objects.create(
            project=b,
            title='done late',
            task_type='Edit',
            assigned_to=ed,
            status='completed',
            completed_at=now,
            due_date=now - timedelta(days=1),
        )
        Task.objects.create(
            project=b,
            title='old',
            task_type='Edit',
            assigned_to=ed,
            status='completed',
            completed_at=now - timedelta(days=40),
        )
        Revision.objects.create(task=late, content_item=item, revision_number=1, reason='fix', assigned_to=ed)

        today = owner_api.get('/api/v1/dashboards/metrics/', day).data['today']
        assert (
            today['due_today'],
            today['due_today_done'],
            today['done_today'],
            today['active_tasks'],
            today['published_today'],
        ) == (2, 1, 2, 1, 1), today

        week = {
            'start': (now - timedelta(days=7)).isoformat(),
            'end': (now + timedelta(hours=1)).isoformat(),
            'tz': 300,
        }
        r = owner_api.get('/api/v1/dashboards/reports/', week).data
        k = r['kpis']
        assert (k['orders_completed'], k['content_published'], k['on_time_rate'], k['first_pass_rate']) == (
            2,
            1,
            50,
            50,
        ), k
        assert r['previous']['orders_completed'] == 0 and len(r['trend']) >= 7
        assert [t['completed'] for t in r['team']] == [2]
        ra = owner_api.get('/api/v1/dashboards/reports/', {**week, 'project': a.id}).data
        assert ra['kpis']['orders_completed'] == 1 and [p['name'] for p in ra['projects']] == ['PA']
        assert (
            owner_api.get('/api/v1/dashboards/reports/', {**week, 'member': owner.id}).data['kpis']['orders_completed']
            == 0
        )
        assert (
            owner_api.get('/api/v1/dashboards/reports/', {'start': week['end'], 'end': week['start']}).status_code
            == 400
        )
        pm_api = APIClient()
        pm_api.force_authenticate(ed)
        assert pm_api.get('/api/v1/dashboards/reports/').status_code == 403
        assert ContentStatusChange.objects.count() == 3
