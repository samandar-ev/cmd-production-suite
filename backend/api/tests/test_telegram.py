from datetime import timedelta
from unittest import mock

from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from api import telegram
from api.models import Client, Project, Task, TaskStatus, User, UserRole

TG = dict(
    TELEGRAM_BOT_TOKEN='123:abc',
    TELEGRAM_BOT_USERNAME='cmd_bot',
    TELEGRAM_WEBHOOK_SECRET='s3cret',
    APP_BASE_URL='https://app.test',
)


@override_settings(**TG)
class TelegramTest(TestCase):
    def setUp(self):
        self.sent = []
        self.patches = [
            mock.patch.object(telegram, 'send', side_effect=lambda c, t, b=None: self.sent.append((c, t, b)) or True),
            mock.patch.object(telegram, 'dispatch', side_effect=lambda jobs: [telegram.send(*j) for j in jobs]),
        ]
        for p in self.patches:
            p.start()
        telegram._last_check['at'] = None
        self.owner = User.objects.create_user('boss', password='x', role=UserRole.OWNER, telegram_chat_id='100')
        self.editor = User.objects.create_user(
            'ed', password='x', role=UserRole.EDITOR, first_name='Ed', telegram_chat_id='200', language='ru'
        )
        client = Client.objects.create(client_name='Acme')
        self.project = Project.objects.create(name='Launch', client=client, project_manager=self.owner)
        self.api = APIClient()

    def tearDown(self):
        for p in self.patches:
            p.stop()

    def hook(self, text, chat_id=200, secret='s3cret', lang='en'):
        update = {
            'message': {'chat': {'id': chat_id, 'type': 'private'}, 'from': {'language_code': lang}, 'text': text}
        }
        return self.api.post(
            '/api/v1/telegram/webhook/', update, format='json', HTTP_X_TELEGRAM_BOT_API_SECRET_TOKEN=secret
        )

    def test_new_order_goes_to_telegram_with_deadline_in_recipient_language(self):
        due = timezone.now() + timedelta(days=3)
        self.api.force_authenticate(self.owner)
        r = self.api.post(
            '/api/v1/tasks/',
            {
                'title': 'Cut reel',
                'project': self.project.id,
                'assigned_to': self.editor.id,
                'task_type': 'Edit',
                'due_date': due.isoformat(),
            },
            format='json',
        )
        self.assertEqual(r.status_code, 201, r.data)
        chat, text, button = self.sent[-1]
        self.assertEqual(chat, '200')
        self.assertIn('Cut reel', text)
        self.assertIn('Срок', text)
        self.assertIn(telegram.local_time(due), text)
        self.assertEqual(button[1], f'https://app.test/orders/{r.data["id"]}')

    def test_chat_message_notifies_the_other_side_only(self):
        task = Task.objects.create(title='Cut', project=self.project, assigned_to=self.editor, assigned_by=self.owner)
        self.api.force_authenticate(self.owner)
        r = self.api.post(f'/api/v1/chats/{task.id}/messages/', {'body': 'Hi <b>there</b>'}, format='json')
        self.assertEqual(r.status_code, 201)
        self.assertEqual([s[0] for s in self.sent], ['200'])
        self.assertIn('Hi &lt;b&gt;there&lt;/b&gt;', self.sent[0][1])

    def test_disabled_or_unlinked_users_get_nothing(self):
        self.editor.telegram_enabled = False
        self.editor.save()
        telegram.notify_users([self.editor, User.objects.create_user('nochat', password='x')], 'T', 'M')
        self.assertEqual(self.sent, [])

    def test_webhook_rejects_wrong_secret(self):
        self.assertEqual(self.hook('/start', secret='nope').status_code, 403)
        self.assertEqual(self.sent, [])

    def test_start_returns_chat_id(self):
        self.hook('/start', chat_id=555)
        self.assertIn('<code>555</code>', self.sent[0][1])

    def test_deep_link_connects_account(self):
        self.api.force_authenticate(self.owner)
        url = self.api.post('/api/v1/telegram/connect/').data['url']
        code = url.split('start=')[1]
        self.hook(f'/start {code}', chat_id=777)
        self.owner.refresh_from_db()
        self.assertEqual(self.owner.telegram_chat_id, '777')
        self.assertEqual(self.owner.telegram_link_code, '')
        self.hook(f'/start {code}', chat_id=888)
        self.assertIn('expired', self.sent[-1][1])

    def test_stop_and_tasks_commands(self):
        Task.objects.create(title='Shoot ad', project=self.project, assigned_to=self.editor)
        self.hook('/tasks')
        self.assertIn('Shoot ad', self.sent[-1][1])
        self.hook('/stop')
        self.editor.refresh_from_db()
        self.assertFalse(self.editor.telegram_enabled)

    def test_deadline_reminders_sent_once(self):
        now = timezone.now()
        Task.objects.create(
            title='Soon', project=self.project, assigned_to=self.editor, due_date=now + timedelta(hours=5)
        )
        Task.objects.create(
            title='Late', project=self.project, assigned_to=self.editor, due_date=now - timedelta(hours=1)
        )
        Task.objects.create(
            title='Done',
            project=self.project,
            assigned_to=self.editor,
            due_date=now - timedelta(hours=1),
            status=TaskStatus.COMPLETED,
        )
        self.assertEqual(telegram.send_due_reminders(now), 2)
        self.assertEqual(telegram.send_due_reminders(now), 0)
        texts = ' '.join(t for _c, t, _b in self.sent)
        self.assertIn('Soon', texts)
        self.assertIn('Late', texts)
        self.assertNotIn('Done', texts)
        self.assertIn('100', [c for c, _t, _b in self.sent])

    def test_manager_adding_chat_id_sends_welcome_and_validates(self):
        self.api.force_authenticate(self.owner)
        bad = self.api.patch(f'/api/v1/users/{self.editor.id}/', {'telegram_chat_id': '@ed'}, format='json')
        self.assertEqual(bad.status_code, 400)
        self.api.patch(f'/api/v1/users/{self.editor.id}/', {'telegram_chat_id': '300'}, format='json')
        self.assertEqual(self.sent[-1][0], '300')
