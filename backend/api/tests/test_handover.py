from django.test import TestCase
from rest_framework.test import APIClient

from api.models import Client, ContentItem, Notification, Project, Task, TaskStatus, User, VideoSubmission


class HandoverTest(TestCase):
    def setUp(self):
        self.pm = User.objects.create_user('pm', password='x', role='PROJECT_MANAGER', first_name='Ron')
        self.vg = User.objects.create_user('vg', password='x', role='VIDEOGRAPHER', first_name='Alex')
        self.ed = User.objects.create_user('ed', password='x', role='EDITOR')
        project = Project.objects.create(
            client=Client.objects.create(client_name='Acme', contact_person='A'),
            name='Launch',
            project_manager=self.pm,
            status='active',
        )
        self.item = ContentItem.objects.create(
            project=project,
            title='Hero Reel',
            content_type='Reel',
            platform='Instagram',
            status='shooting',
            assigned_videographer=self.vg,
            assigned_editor=self.ed,
        )
        self.shoot = Task.objects.create(
            title='Shoot',
            project=project,
            content_item=self.item,
            stage='shoot',
            assigned_to=self.vg,
            assigned_by=self.pm,
            task_type='shoot',
        )
        self.edit = Task.objects.create(
            title='Edit',
            project=project,
            content_item=self.item,
            stage='edit',
            assigned_to=self.ed,
            assigned_by=self.pm,
            task_type='edit',
            depends_on=self.shoot,
        )

    def api(self, user):
        c = APIClient()
        c.force_authenticate(user)
        return c

    def hand_over(self, **extra):
        return self.api(self.vg).post(
            '/api/v1/video-submissions/handover/',
            {
                'task': self.shoot.id,
                'media': 'hard_drive',
                'handed_to': self.pm.id,
                'note': '2 cameras, 180 GB',
                **extra,
            },
            format='json',
        )

    def test_handover_goes_to_review_and_unlocks_editing_when_confirmed(self):
        receivers = self.api(self.vg).get(f'/api/v1/video-submissions/receivers/?project={self.shoot.project_id}').data
        self.assertEqual([r['id'] for r in receivers], [self.pm.id])
        r = self.hand_over()
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(r.data['delivery'], 'in_person')
        self.assertEqual(r.data['handover_to_name'], 'Ron')
        self.shoot.refresh_from_db()
        self.assertEqual(self.shoot.status, TaskStatus.WAITING_FOR_REVIEW)
        self.assertTrue(
            Notification.objects.filter(recipient_user=self.pm, title='Work handed over in person').exists()
        )
        detail = self.api(self.pm).get(f'/api/v1/video-submissions/{r.data["id"]}/').data
        self.assertIsNone(detail['view_url'])
        self.assertTrue(detail['can_review'])
        self.api(self.pm).post(
            f'/api/v1/video-submissions/{r.data["id"]}/review/', {'decision': 'approved'}, format='json'
        )
        self.shoot.refresh_from_db()
        self.assertEqual(self.shoot.status, TaskStatus.COMPLETED)
        self.assertTrue(Notification.objects.filter(recipient_user=self.vg, title='Handover confirmed').exists())
        files = self.api(self.ed).get(f'/api/v1/tasks/{self.edit.id}/').data['input_files']
        self.assertEqual(files[0]['delivery'], 'in_person')
        self.assertEqual(files[0]['handover_to_name'], 'Ron')

    def test_validation(self):
        self.assertEqual(self.hand_over(media='floppy').status_code, 400)
        self.assertEqual(self.hand_over(handed_to=self.ed.id).status_code, 400)
        self.assertEqual(self.hand_over(handed_over_at='2099-01-01T10:00:00Z').status_code, 400)
        self.assertEqual(self.hand_over().status_code, 201)
        self.assertEqual(self.hand_over().status_code, 409)
        other = User.objects.create_user('vg2', password='x', role='VIDEOGRAPHER')
        r = self.api(other).post(
            '/api/v1/video-submissions/handover/', {'task': self.shoot.id, 'media': 'ssd'}, format='json'
        )
        self.assertEqual(r.status_code, 404)

    def test_handovers_are_never_evicted_from_storage(self):
        self.hand_over()
        sub = VideoSubmission.objects.get()
        VideoSubmission.objects.filter(pk=sub.pk).update(status='approved')
        from api import video_quota

        with self.settings(VIDEO_STORAGE_LIMIT_BYTES=0):
            try:
                video_quota.evict(1)
            except video_quota.QueueFull:
                pass
        sub.refresh_from_db()
        self.assertFalse(sub.deleted)
