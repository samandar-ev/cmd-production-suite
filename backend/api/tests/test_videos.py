import urllib.parse
import urllib.request
from datetime import timedelta
from io import StringIO

import boto3
from django.core import mail
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.utils import timezone
from moto.server import ThreadedMotoServer
from rest_framework.test import APIClient

from api import video_storage
from api.models import Client, ContentItem, Notification, Project, User, VideoComment, VideoStatus, VideoSubmission

PORT = 5099
ENDPOINT = f'http://127.0.0.1:{PORT}'
BUCKET = 'test-videos'
MP4_HEADER = b'\x00\x00\x00\x18ftypmp42\x00\x00\x00\x00'
R2 = dict(
    R2_ENDPOINT_URL=ENDPOINT,
    R2_BUCKET=BUCKET,
    R2_ACCESS_KEY_ID='test',
    R2_SECRET_ACCESS_KEY='test',
    EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
)


def http(method, url, data=None, headers=None):
    req = urllib.request.Request(url, data=data, method=method, headers=headers or {})
    with urllib.request.urlopen(req) as res:
        return res.status, dict(res.headers), res.read()


@override_settings(**R2)
class VideoTestBase(TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadedMotoServer(port=PORT, verbose=False)
        cls.server.start()
        super().setUpClass()

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        cls.server.stop()

    def setUp(self):
        video_storage.reset_client()
        s3 = boto3.client(
            's3', endpoint_url=ENDPOINT, aws_access_key_id='test', aws_secret_access_key='test', region_name='us-east-1'
        )
        try:
            s3.create_bucket(Bucket=BUCKET)
        except s3.exceptions.BucketAlreadyOwnedByYou:
            for obj in s3.list_objects_v2(Bucket=BUCKET).get('Contents', []):
                s3.delete_object(Bucket=BUCKET, Key=obj['Key'])
        self.s3 = s3
        self.owner = User.objects.create_user('owner', password='x', role='OWNER', email='owner@x.io')
        self.pm = User.objects.create_user('pm', password='x', role='PROJECT_MANAGER', email='pm@x.io')
        self.pm2 = User.objects.create_user('pm2', password='x', role='PROJECT_MANAGER')
        self.editor = User.objects.create_user('ed', password='x', role='EDITOR', email='ed@x.io')
        self.outsider = User.objects.create_user('ed2', password='x', role='EDITOR')
        client = Client.objects.create(client_name='Acme', contact_person='A')
        self.project = Project.objects.create(client=client, name='Launch', project_manager=self.pm, status='active')
        self.item = ContentItem.objects.create(
            project=self.project,
            title='Hero Reel',
            content_type='Reel',
            platform='Instagram',
            status='editing',
            assigned_editor=self.editor,
        )

    def api(self, user):
        c = APIClient()
        c.force_authenticate(user)
        return c

    def init(self, user=None, size=1000, **extra):
        body = {
            'project': self.project.id,
            'content_item': self.item.id,
            'filename': 'cut.mp4',
            'content_type': 'video/mp4',
            'size': size,
            'note': 'first cut',
            **extra,
        }
        return self.api(user or self.editor).post('/api/v1/video-submissions/', body, format='json')

    def upload(self, data=MP4_HEADER + b'x' * 500, declared=None, user=None):
        res = self.init(user=user, size=declared or len(data))
        assert res.status_code == 201, res.data
        sub_id = res.data['id']
        c = self.api(user or self.editor)
        url = c.post(f'/api/v1/video-submissions/{sub_id}/sign-part/', {'part_number': 1}, format='json').data['url']
        assert url.startswith(ENDPOINT)
        _, headers, _ = http('PUT', url, data, {'Content-Type': 'application/octet-stream'})
        parts = [{'PartNumber': 1, 'ETag': headers['ETag']}]
        return sub_id, c.post(f'/api/v1/video-submissions/{sub_id}/complete/', {'parts': parts}, format='json')

    def stored(self, sub, status, size, reviewed_minutes_ago=None):
        key = f'videos/{self.project.id}/{status}-{VideoSubmission.objects.count()}.mp4'
        self.s3.put_object(Bucket=BUCKET, Key=key, Body=b'0' * size)
        return VideoSubmission.objects.create(
            project=self.project,
            uploader=self.editor,
            object_key=key,
            size_bytes=size,
            original_filename='a.mp4',
            status=status,
            version=sub,
            reviewed_at=timezone.now() - timedelta(minutes=reviewed_minutes_ago) if reviewed_minutes_ago else None,
        )

    def exists(self, key):
        return video_storage.head(key) is not None


class UploadConfirmTests(VideoTestBase):
    def test_upload_records_real_size_and_notifies_reviewer(self):
        sub_id, res = self.upload(declared=5000)
        self.assertEqual(res.status_code, 200, res.data)
        sub = VideoSubmission.objects.get(pk=sub_id)
        self.assertEqual((sub.status, sub.size_bytes, sub.version), ('pending', len(MP4_HEADER) + 500, 1))
        self.item.refresh_from_db()
        self.assertEqual(self.item.status, 'under_review')
        self.assertTrue(Notification.objects.filter(recipient_user=self.pm, type='video_submitted').exists())
        self.assertIn('pm@x.io', mail.outbox[0].to)

    def test_larger_than_declared_is_deleted(self):
        sub_id, res = self.upload(data=MP4_HEADER + b'x' * 500, declared=100)
        self.assertEqual(res.data['code'], 'size_mismatch')
        sub = VideoSubmission.objects.get(pk=sub_id)
        self.assertTrue(sub.deleted)
        self.assertFalse(self.exists(sub.object_key))

    def test_any_file_type_is_accepted(self):
        res = self.init(filename='footage.zip', content_type='application/zip', size=10)
        self.assertEqual(res.status_code, 201, res.data)
        sub = VideoSubmission.objects.get(pk=res.data['id'])
        self.assertTrue(sub.object_key.endswith('.zip'))
        self.assertEqual(sub.content_type, 'application/zip')
        self.api(self.editor).post(f'/api/v1/video-submissions/{sub.id}/abort/')
        res = self.init(filename='clip.braw', content_type='', size=10)
        self.assertEqual(VideoSubmission.objects.get(pk=res.data['id']).content_type, 'application/octet-stream')

    def test_submit_from_task_updates_task(self):
        from api.models import Task

        task = Task.objects.create(
            project=self.project,
            content_item=self.item,
            title='Edit',
            task_type='Edit',
            assigned_to=self.editor,
            status='in_progress',
        )
        res = self.api(self.editor).post(
            '/api/v1/video-submissions/',
            {'task': task.id, 'filename': 'cut.mov', 'content_type': 'video/quicktime', 'size': 600},
            format='json',
        )
        self.assertEqual(res.status_code, 201, res.data)
        sub_id = res.data['id']
        c = self.api(self.editor)
        url = c.post(f'/api/v1/video-submissions/{sub_id}/sign-part/', {'part_number': 1}, format='json').data['url']
        _, headers, _ = http('PUT', url, b'x' * 600, {'Content-Type': 'application/octet-stream'})
        c.post(
            f'/api/v1/video-submissions/{sub_id}/complete/',
            {'parts': [{'PartNumber': 1, 'ETag': headers['ETag']}]},
            format='json',
        )
        task.refresh_from_db()
        self.assertEqual(task.status, 'waiting_for_review')
        self.api(self.pm).post(f'/api/v1/video-submissions/{sub_id}/review/', {'decision': 'approved'}, format='json')
        task.refresh_from_db()
        self.assertEqual(task.status, 'completed')
        other = Task.objects.create(project=self.project, title='x', task_type='Edit', assigned_to=self.outsider)
        res = self.api(self.editor).post(
            '/api/v1/video-submissions/',
            {'task': other.id, 'filename': 'a.mp4', 'content_type': 'video/mp4', 'size': 10},
            format='json',
        )
        self.assertEqual(res.status_code, 404)

    def test_bad_parts_fail_and_release_reservation(self):
        res = self.init()
        sub_id = res.data['id']
        res = self.api(self.editor).post(
            f'/api/v1/video-submissions/{sub_id}/complete/',
            {'parts': [{'PartNumber': 1, 'ETag': '"nope"'}]},
            format='json',
        )
        self.assertEqual(res.status_code, 400)
        self.assertTrue(VideoSubmission.objects.get(pk=sub_id).deleted)

    def test_double_complete_is_rejected(self):
        sub_id, res = self.upload()
        again = self.api(self.editor).post(
            f'/api/v1/video-submissions/{sub_id}/complete/', {'parts': [{'PartNumber': 1, 'ETag': 'x'}]}, format='json'
        )
        self.assertEqual(again.status_code, 404)

    def test_init_validation_and_permissions(self):
        self.assertEqual(self.init(size=600 * 1024 * 1024).data['code'], 'too_large')
        self.assertEqual(self.init(filename='').data['code'], 'invalid_name')
        self.assertEqual(self.init(user=self.outsider).status_code, 403)
        self.assertEqual(self.init(user=self.pm).status_code, 403)
        self.assertEqual(VideoSubmission.objects.count(), 0)

    def test_only_uploader_can_sign_parts(self):
        sub_id = self.init().data['id']
        res = self.api(self.outsider).post(
            f'/api/v1/video-submissions/{sub_id}/sign-part/', {'part_number': 1}, format='json'
        )
        self.assertEqual(res.status_code, 404)
        res = self.api(self.pm).post(
            f'/api/v1/video-submissions/{sub_id}/sign-part/', {'part_number': 1}, format='json'
        )
        self.assertEqual(res.status_code, 403)

    def test_cannot_upload_while_previous_version_pending(self):
        self.upload()
        self.assertEqual(self.init().data['code'], 'pending_exists')

    def test_abort_releases_space(self):
        sub_id = self.init(size=700).data['id']
        self.api(self.editor).post(f'/api/v1/video-submissions/{sub_id}/abort/')
        self.assertTrue(VideoSubmission.objects.get(pk=sub_id).deleted)


class EvictionTests(VideoTestBase):
    @override_settings(VIDEO_STORAGE_LIMIT_BYTES=1000)
    def test_evicts_oldest_reviewed_first_and_only_as_many_as_needed(self):
        a = self.stored(1, VideoStatus.APPROVED, 300, reviewed_minutes_ago=30)
        b = self.stored(2, VideoStatus.REJECTED, 300, reviewed_minutes_ago=20)
        c = self.stored(3, VideoStatus.APPROVED, 300, reviewed_minutes_ago=10)
        pending = self.stored(4, VideoStatus.PENDING, 100)
        VideoComment.objects.create(submission=a, author=self.pm, body='keep me')
        self.assertEqual(self.init(size=350).status_code, 201)
        for sub, gone in ((a, True), (b, True), (c, False), (pending, False)):
            sub.refresh_from_db()
            self.assertEqual(sub.deleted, gone, sub.status)
            self.assertEqual(self.exists(sub.object_key), not gone)
        self.assertEqual(a.comments.get().body, 'keep me')

    @override_settings(VIDEO_STORAGE_LIMIT_BYTES=1000)
    def test_never_evicts_pending_or_uploading(self):
        pending = self.stored(1, VideoStatus.PENDING, 500)
        uploading = self.stored(None, VideoStatus.UPLOADING, 400)
        res = self.init(size=200)
        self.assertEqual((res.status_code, res.data['code']), (507, 'queue_full'))
        self.assertIn('review queue is full', res.data['error'])
        for sub in (pending, uploading):
            sub.refresh_from_db()
            self.assertFalse(sub.deleted)
            self.assertTrue(self.exists(sub.object_key))

    @override_settings(VIDEO_STORAGE_LIMIT_BYTES=1000)
    def test_rejects_without_deleting_when_eviction_cannot_free_enough(self):
        reviewed = self.stored(1, VideoStatus.APPROVED, 200, reviewed_minutes_ago=5)
        self.stored(2, VideoStatus.PENDING, 700)
        self.assertEqual(self.init(size=600).status_code, 507)
        reviewed.refresh_from_db()
        self.assertFalse(reviewed.deleted)
        self.assertTrue(self.exists(reviewed.object_key))

    @override_settings(VIDEO_STORAGE_LIMIT_BYTES=1000)
    def test_reservation_holds_space_for_concurrent_uploads(self):
        self.assertEqual(self.init(size=700).status_code, 201)
        other = ContentItem.objects.create(
            project=self.project, title='B', content_type='Reel', platform='TikTok', assigned_editor=self.editor
        )
        self.assertEqual(self.init(size=400, content_item=other.id).status_code, 507)


class ReviewTests(VideoTestBase):
    def setUp(self):
        super().setUp()
        self.sub_id, res = self.upload()
        assert res.status_code == 200, res.data
        self.url = f'/api/v1/video-submissions/{self.sub_id}/'

    def review(self, user, decision, comment=''):
        return self.api(user).post(self.url + 'review/', {'decision': decision, 'comment': comment}, format='json')

    def test_permissions(self):
        self.assertEqual(self.review(self.editor, 'approved').status_code, 403)
        self.assertEqual(self.review(self.pm2, 'approved').status_code, 404)
        self.assertEqual(self.review(self.outsider, 'approved').status_code, 404)
        self.assertEqual(self.api(self.outsider).get(self.url).status_code, 404)
        self.assertEqual(self.review(self.owner, 'approved').status_code, 200)

    def test_double_click_only_first_decision_wins(self):
        self.assertEqual(self.review(self.pm, 'approved').status_code, 200)
        second = self.review(self.owner, 'rejected', 'too late')
        self.assertEqual((second.status_code, second.data['code']), (409, 'already_reviewed'))
        self.assertEqual(VideoSubmission.objects.get(pk=self.sub_id).status, 'approved')

    def test_reject_requires_comment_then_new_version(self):
        self.assertEqual(self.review(self.pm, 'rejected').data['code'], 'comment_required')
        self.assertEqual(self.review(self.pm, 'rejected', 'Music too loud').status_code, 200)
        sub = VideoSubmission.objects.get(pk=self.sub_id)
        self.assertEqual((sub.status, sub.review_comment, sub.reviewer), ('rejected', 'Music too loud', self.pm))
        self.assertTrue(self.exists(sub.object_key))
        self.assertIn('Music too loud', mail.outbox[-1].body)
        self.item.refresh_from_db()
        self.assertEqual((self.item.status, self.item.revision_count), ('revision_requested', 1))

        detail = self.api(self.editor).get(self.url).data
        self.assertTrue(detail['can_upload_new_version'])
        v2_id, res = self.upload()
        self.assertEqual(res.data['version'], 2)
        history = self.api(self.pm).get(f'/api/v1/video-submissions/{v2_id}/').data['history']
        self.assertEqual([(h['version'], h['review_comment']) for h in history], [(2, ''), (1, 'Music too loud')])

    def test_playback_url_supports_seeking_and_expires_with_file(self):
        detail = self.api(self.pm).get(self.url).data
        self.assertIn('attachment', urllib.parse.unquote(detail['download_url']))
        url = detail['view_url']
        status_code, headers, body = http('GET', url, headers={'Range': 'bytes=4-7'})
        self.assertEqual((status_code, body), (206, b'ftyp'))
        self.review(self.pm, 'approved')
        VideoSubmission.objects.filter(pk=self.sub_id).update(deleted=True)
        data = self.api(self.editor).get(self.url).data
        self.assertIsNone(data['view_url'])
        self.assertTrue(data['deleted'])

    def test_timestamped_comments(self):
        res = self.api(self.pm).post(
            self.url + 'comments/', {'body': 'Cut here', 'timestamp_seconds': 12.5}, format='json'
        )
        self.assertEqual(res.status_code, 201)
        self.assertEqual(self.api(self.editor).get(self.url).data['comments'][0]['timestamp_seconds'], 12.5)


class CleanupTests(VideoTestBase):
    def test_cleanup_releases_abandoned_and_flags_stale(self):
        sub_id = self.init(size=700).data['id']
        VideoSubmission.objects.filter(pk=sub_id).update(created_at=timezone.now() - timedelta(hours=25))
        stale = self.stored(1, VideoStatus.PENDING, 100)
        VideoSubmission.objects.filter(pk=stale.pk).update(created_at=timezone.now() - timedelta(days=31))
        out = StringIO()
        call_command('video_cleanup', stdout=out)
        self.assertTrue(VideoSubmission.objects.get(pk=sub_id).deleted)
        stale.refresh_from_db()
        self.assertFalse(stale.deleted)
        self.assertIsNotNone(stale.stale_flagged_at)
        self.assertTrue(Notification.objects.filter(type='video_stale', recipient_user=self.editor).exists())
        self.assertIn('R2 audit', out.getvalue())


class ChatAttachmentTests(VideoTestBase):
    def setUp(self):
        super().setUp()
        from api.models import Task

        self.task = Task.objects.create(
            project=self.project, content_item=self.item, title='Edit', task_type='Edit', assigned_to=self.editor
        )
        self.base = f'/api/v1/chats/{self.task.id}/'

    def send_file(self, user, data, declared=None, ctype='image/png', name='frame.png'):
        c = self.api(user)
        res = c.post(
            self.base + 'attachments/',
            {'filename': name, 'size': declared or len(data), 'content_type': ctype},
            format='json',
        )
        assert res.status_code == 201, res.data
        assert res.data['upload_url'].startswith(ENDPOINT)
        http('PUT', res.data['upload_url'], data, {'Content-Type': res.data['content_type']})
        return res.data['id'], c.post(
            self.base + 'messages/', {'body': 'see attached', 'attachment': res.data['id']}, format='json'
        )

    def test_send_and_view_file(self):
        att_id, res = self.send_file(self.editor, b'\x89PNG' + b'x' * 300, declared=1000)
        self.assertEqual(res.status_code, 201, res.data)
        msgs = self.api(self.pm).get(self.base + 'messages/').data
        att = msgs[0]['attachment']
        self.assertEqual((att['filename'], att['size_bytes']), ('frame.png', 304))
        _, _, body = http('GET', att['view_url'])
        self.assertEqual(body[:4], b'\x89PNG')
        self.assertEqual(self.api(self.pm).get('/api/v1/chats/').data[0]['last_message'], 'see attached')
        again = self.api(self.editor).post(self.base + 'messages/', {'attachment': att_id}, format='json')
        self.assertEqual(again.status_code, 400)
        self.assertEqual(
            self.api(self.outsider)
            .post(
                self.base + 'attachments/', {'filename': 'a.png', 'size': 5, 'content_type': 'image/png'}, format='json'
            )
            .status_code,
            404,
        )

    def test_limits_and_failed_upload(self):
        too_big = self.api(self.editor).post(
            self.base + 'attachments/',
            {'filename': 'a.zip', 'size': 200 * 1000**2, 'content_type': 'application/zip'},
            format='json',
        )
        self.assertEqual(too_big.status_code, 400)
        _, res = self.send_file(self.editor, b'x' * 500, declared=100, ctype='application/pdf', name='brief.pdf')
        self.assertEqual(res.status_code, 400)
        from api.models import ChatAttachment

        self.assertTrue(ChatAttachment.objects.get(filename='brief.pdf').deleted)

    @override_settings(VIDEO_STORAGE_LIMIT_BYTES=1000)
    def test_chat_files_count_toward_storage(self):
        self.send_file(self.editor, b'x' * 900)
        self.assertEqual(self.init(size=200).status_code, 507)


class ProductionWorkflowTests(VideoTestBase):
    def setUp(self):
        super().setUp()
        self.vg = User.objects.create_user('vg', password='x', role='VIDEOGRAPHER', email='vg@x.io')
        self.item.status = 'scripting'
        self.item.assigned_editor = None
        self.item.save()

    def deliver(self, user, task_id, data=MP4_HEADER + b'x' * 300):
        c = self.api(user)
        res = c.post(
            '/api/v1/video-submissions/',
            {'task': task_id, 'filename': 'f.mp4', 'content_type': 'video/mp4', 'size': len(data)},
            format='json',
        )
        if res.status_code != 201:
            return res
        url = c.post(f'/api/v1/video-submissions/{res.data["id"]}/sign-part/', {'part_number': 1}, format='json').data[
            'url'
        ]
        _, h, _ = http('PUT', url, data, {'Content-Type': 'application/octet-stream'})
        return c.post(
            f'/api/v1/video-submissions/{res.data["id"]}/complete/',
            {'parts': [{'PartNumber': 1, 'ETag': h['ETag']}]},
            format='json',
        )

    def status(self):
        self.item.refresh_from_db()
        return self.item.status

    def review(self, sub_id, decision, comment=''):
        return self.api(self.pm).post(
            f'/api/v1/video-submissions/{sub_id}/review/', {'decision': decision, 'comment': comment}, format='json'
        )

    def test_full_sequence(self):
        url = f'/api/v1/content-items/{self.item.id}/start-production/'
        plan = {
            'workflow': 'shoot_edit',
            'videographer': self.vg.id,
            'editor': self.editor.id,
            'shoot_due': '2030-01-05T10:00:00Z',
            'edit_due': '2030-01-03T10:00:00Z',
        }
        self.assertEqual(self.api(self.pm).post(url, plan, format='json').status_code, 400)
        self.assertEqual(self.api(self.editor).post(url, plan, format='json').status_code, 403)
        plan['edit_due'] = '2030-01-08T10:00:00Z'
        res = self.api(self.pm).post(url, plan, format='json')
        self.assertEqual(res.status_code, 200, res.data)
        self.assertEqual([s['stage'] for s in res.data['production']], ['shoot', 'edit'])
        self.assertEqual(self.api(self.pm).post(url, plan, format='json').status_code, 400)
        shoot = self.api(self.vg).get('/api/v1/tasks/').data[0]
        edit = self.api(self.editor).get('/api/v1/tasks/').data[0]
        self.assertEqual(self.status(), 'ready_for_shooting')
        self.assertTrue(edit['is_blocked'])

        self.assertEqual(self.api(self.editor).post(f'/api/v1/tasks/{edit["id"]}/start/').status_code, 409)
        self.assertEqual(self.deliver(self.editor, edit['id']).data['code'], 'blocked')

        self.api(self.vg).post(f'/api/v1/tasks/{shoot["id"]}/start/')
        self.assertEqual(self.status(), 'shooting')
        v1 = self.deliver(self.vg, shoot['id']).data
        self.assertEqual(self.status(), 'under_review')
        self.review(v1['id'], 'rejected', 'Too dark')
        self.assertEqual(self.status(), 'revision_requested')
        self.assertTrue(self.api(self.editor).get(f'/api/v1/tasks/{edit["id"]}/').data['is_blocked'])
        v2 = self.deliver(self.vg, shoot['id']).data
        self.review(v2['id'], 'approved')
        self.assertEqual(self.status(), 'ready_for_editing')

        edit = self.api(self.editor).get(f'/api/v1/tasks/{edit["id"]}/').data
        self.assertFalse(edit['is_blocked'])
        self.assertTrue(Notification.objects.filter(recipient_user=self.editor, title='Order ready to start').exists())
        self.assertEqual([f['id'] for f in edit['input_files']], [v2['id']])
        footage = self.api(self.editor).get(f'/api/v1/video-submissions/{v2["id"]}/').data
        self.assertTrue(footage['view_url'])
        self.assertEqual(self.api(self.editor).get(f'/api/v1/video-submissions/{v1["id"]}/').status_code, 404)

        cut = self.deliver(self.editor, edit['id']).data
        self.assertEqual(self.status(), 'under_review')
        self.review(cut['id'], 'approved')
        self.assertEqual(self.status(), 'approved')
        pub = self.api(self.pm).post(
            f'/api/v1/content-items/{self.item.id}/publish/', {'post_url': 'https://instagram.com/p/x'}, format='json'
        )
        self.assertEqual(pub.data['status'], 'published')

    def test_edit_only(self):
        res = self.api(self.pm).post(
            f'/api/v1/content-items/{self.item.id}/start-production/',
            {'workflow': 'edit_only', 'editor': self.editor.id, 'edit_due': '2030-01-08T10:00:00Z'},
            format='json',
        )
        self.assertEqual(res.status_code, 200, res.data)
        self.assertEqual(self.status(), 'ready_for_editing')
        self.assertFalse(self.api(self.editor).get('/api/v1/tasks/').data[0]['is_blocked'])


class ProjectDeleteTests(VideoTestBase):
    def test_only_owner_deletes_and_files_are_removed(self):
        sub_id, res = self.upload()
        key = VideoSubmission.objects.get(pk=sub_id).object_key
        self.assertTrue(self.exists(key))
        self.assertEqual(self.api(self.pm).delete(f'/api/v1/projects/{self.project.id}/').status_code, 403)
        self.project.status = 'archived'
        self.project.save()
        self.assertEqual(self.api(self.owner).delete(f'/api/v1/projects/{self.project.id}/').status_code, 204)
        self.assertFalse(self.exists(key))
        self.assertFalse(VideoSubmission.objects.filter(pk=sub_id).exists())
