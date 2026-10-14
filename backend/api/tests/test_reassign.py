from datetime import timedelta

from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from api.models import Client, ContentItem, Notification, Project, Task, TaskStatus, User


class ReassignTest(TestCase):
    def setUp(self):
        self.pm = User.objects.create_user('pm', password='x', role='PROJECT_MANAGER', first_name='Ron')
        self.alex = User.objects.create_user('alex', password='x', role='VIDEOGRAPHER', first_name='Alex')
        self.sam = User.objects.create_user('sam', password='x', role='VIDEOGRAPHER', first_name='Sam')
        project = Project.objects.create(
            client=Client.objects.create(client_name='Acme', contact_person='A'),
            name='Launch',
            project_manager=self.pm,
            status='active',
        )
        self.item = ContentItem.objects.create(
            project=project,
            title='Reel',
            content_type='Reel',
            platform='Instagram',
            status='shooting',
            assigned_videographer=self.alex,
        )
        self.task = Task.objects.create(
            title='Shoot: Reel',
            project=project,
            content_item=self.item,
            stage='shoot',
            task_type='shoot',
            assigned_to=self.alex,
            assigned_by=self.pm,
            status=TaskStatus.IN_PROGRESS,
            due_date=timezone.now() + timedelta(hours=5),
            reminded_due_soon_at=timezone.now(),
        )
        self.api = APIClient()
        self.api.force_authenticate(self.pm)

    def test_reassign_notifies_both_and_restarts(self):
        r = self.api.patch(f'/api/v1/tasks/{self.task.id}/', {'assigned_to': self.sam.id}, format='json')
        self.assertEqual(r.status_code, 200, r.data)
        self.task.refresh_from_db()
        self.item.refresh_from_db()
        self.assertEqual(self.task.status, TaskStatus.NOT_STARTED)
        self.assertIsNone(self.task.reminded_due_soon_at)
        self.assertEqual(self.item.assigned_videographer, self.sam)
        self.assertTrue(Notification.objects.filter(recipient_user=self.sam, title='New task assigned').exists())
        self.assertTrue(Notification.objects.filter(recipient_user=self.alex, title='Order reassigned').exists())

    def test_deadline_change_notifies_assignee(self):
        new = timezone.now() + timedelta(days=3)
        self.api.patch(f'/api/v1/tasks/{self.task.id}/', {'due_date': new.isoformat()}, format='json')
        self.task.refresh_from_db()
        self.assertEqual(self.task.status, TaskStatus.IN_PROGRESS)
        self.assertIsNone(self.task.reminded_due_soon_at)
        self.assertTrue(Notification.objects.filter(recipient_user=self.alex, title='Deadline changed').exists())

    def test_creators_cannot_reassign(self):
        c = APIClient()
        c.force_authenticate(self.alex)
        self.assertEqual(
            c.patch(f'/api/v1/tasks/{self.task.id}/', {'assigned_to': self.sam.id}, format='json').status_code, 403
        )
