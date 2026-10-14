import base64
import hashlib
import json
from unittest import mock
from urllib.parse import parse_qs, urlparse

from django.core.cache import cache
from django.test import Client as HttpClient
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from api import mcp, telegram
from api.models import AIApproval, Client, Project, Task, User, UserRole

REDIRECT = 'https://claude.ai/api/mcp/auth_callback'


@override_settings(TELEGRAM_BOT_TOKEN='1:x', TELEGRAM_WEBHOOK_SECRET='s', TELEGRAM_BOT_USERNAME='bot')
class ClaudeConnectorTest(TestCase):
    def setUp(self):
        cache.clear()
        self.owner = User.objects.create_user(
            'boss', password='Secret-pass-1', role=UserRole.OWNER, first_name='Boss', telegram_chat_id='42'
        )
        self.ed = User.objects.create_user('ed', password='Secret-pass-1', role=UserRole.EDITOR, first_name='Ed')
        self.client_obj = Client.objects.create(client_name='Halo Coffee')
        self.project = Project.objects.create(
            name='Launch', client=self.client_obj, project_manager=self.owner, service_fee=1500
        )
        self.sent = []
        for target, fn in [(telegram, 'send'), (telegram, 'call')]:
            p = mock.patch.object(target, fn, side_effect=lambda *a, **k: self.sent.append(a) or {'ok': True})
            p.start()
            self.addCleanup(p.stop)
        p = mock.patch.object(telegram, 'dispatch', side_effect=lambda jobs: [telegram.send(*j) for j in jobs])
        p.start()
        self.addCleanup(p.stop)
        p = mock.patch.object(mcp, 'APPROVAL_WAIT_S', 0)
        p.start()
        self.addCleanup(p.stop)
        self.http = HttpClient()
        self.token = self.connect()

    def connect(self, username='boss'):
        reg = self.http.post(
            '/oauth/register',
            json.dumps({'client_name': 'Claude', 'redirect_uris': [REDIRECT]}),
            content_type='application/json',
        ).json()
        verifier = 'v' * 50
        challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b'=').decode()
        q = {
            'client_id': reg['client_id'],
            'redirect_uri': REDIRECT,
            'response_type': 'code',
            'state': 'xyz',
            'code_challenge': challenge,
            'code_challenge_method': 'S256',
        }
        self.assertEqual(self.http.get('/oauth/authorize', q).status_code, 200)
        r = self.http.post(
            '/oauth/authorize', {**q, 'username': username, 'password': 'Secret-pass-1', 'action': 'allow'}
        )
        self.assertEqual(r.status_code, 302, r.content[:300])
        back = parse_qs(urlparse(r['Location']).query)
        self.assertEqual(back['state'], ['xyz'])
        tok = self.http.post(
            '/oauth/token',
            {
                'grant_type': 'authorization_code',
                'code': back['code'][0],
                'client_id': reg['client_id'],
                'redirect_uri': REDIRECT,
                'code_verifier': verifier,
            },
        ).json()
        self.assertIn('access_token', tok)
        self.reg, self.refresh = reg, tok['refresh_token']
        return tok['access_token']

    def rpc(self, method, params=None, token=None):
        r = self.http.post(
            '/mcp/',
            json.dumps({'jsonrpc': '2.0', 'id': 1, 'method': method, 'params': params or {}}),
            content_type='application/json',
            HTTP_AUTHORIZATION=f'Bearer {token or self.token}',
        )
        return r

    def tool(self, name, **args):
        res = self.rpc('tools/call', {'name': name, 'arguments': args}).json()['result']
        return res['isError'], json.loads(res['content'][0]['text'])

    def test_discovery_and_auth_required(self):
        meta = self.http.get('/.well-known/oauth-authorization-server').json()
        self.assertTrue(meta['token_endpoint'].endswith('/oauth/token'))
        self.assertIn('S256', meta['code_challenge_methods_supported'])
        r = self.http.post('/mcp/', '{}', content_type='application/json')
        self.assertEqual(r.status_code, 401)
        self.assertIn('resource_metadata=', r['WWW-Authenticate'])

    def test_only_claude_or_localhost_redirects_can_register(self):
        r = self.http.post(
            '/oauth/register',
            json.dumps({'redirect_uris': ['https://evil.example/cb']}),
            content_type='application/json',
        )
        self.assertEqual(r.status_code, 400)

    def test_wrong_pkce_verifier_is_rejected(self):
        reg = self.http.post(
            '/oauth/register', json.dumps({'redirect_uris': [REDIRECT]}), content_type='application/json'
        ).json()
        q = {
            'client_id': reg['client_id'],
            'redirect_uri': REDIRECT,
            'response_type': 'code',
            'state': 's',
            'code_challenge': 'abc',
            'code_challenge_method': 'S256',
        }
        r = self.http.post(
            '/oauth/authorize', {**q, 'username': 'boss', 'password': 'Secret-pass-1', 'action': 'allow'}
        )
        code = parse_qs(urlparse(r['Location']).query)['code'][0]
        bad = self.http.post(
            '/oauth/token',
            {
                'grant_type': 'authorization_code',
                'code': code,
                'client_id': reg['client_id'],
                'redirect_uri': REDIRECT,
                'code_verifier': 'wrong',
            },
        )
        self.assertEqual(bad.status_code, 400)

    def test_handshake_and_tools(self):
        init = self.rpc(
            'initialize', {'protocolVersion': '2025-06-18', 'capabilities': {}, 'clientInfo': {'name': 't'}}
        ).json()
        self.assertEqual(init['result']['protocolVersion'], '2025-06-18')
        names = [t['name'] for t in self.rpc('tools/list').json()['result']['tools']]
        self.assertEqual(names, ['cmd_catalog', 'cmd_read', 'cmd_write', 'cmd_delete'])
        _, cat = self.tool('cmd_catalog', search='client')
        self.assertTrue(any(e['path'] == 'clients/' for e in cat['api']))
        _, full = self.tool('cmd_catalog')
        self.assertFalse(any(e['path'].startswith(('users/me', 'auth/', 'telegram/', 'ai/')) for e in full['api']))

    def test_full_workflow_client_project_task_message(self):
        err, res = self.tool(
            'cmd_write', method='POST', path='clients/', body={'client_name': 'Nike', 'contact_person': 'Anna'}
        )
        self.assertFalse(err, res)
        nike = res['data']['id']
        err, res = self.tool(
            'cmd_write', method='POST', path='projects/', body={'name': 'Spring', 'client': nike, 'status': 'active'}
        )
        self.assertFalse(err, res)
        err, res = self.tool(
            'cmd_write',
            method='POST',
            path='tasks/',
            body={
                'title': 'Edit spring reel',
                'project': res['data']['id'],
                'assigned_to': self.ed.id,
                'task_type': 'edit',
            },
        )
        self.assertFalse(err, res)
        task_id = res['data']['id']
        err, res = self.tool(
            'cmd_write', method='POST', path=f'chats/{task_id}/messages/', body={'body': 'Please start today'}
        )
        self.assertFalse(err, res)
        self.assertEqual(Task.objects.get(pk=task_id).assigned_to, self.ed)

    def test_fees_are_hidden_without_approval(self):
        err, res = self.tool('cmd_read', path=f'projects/{self.project.id}/')
        self.assertFalse(err)
        self.assertIn('hidden', str(res['data']['service_fee']))

    def test_blocked_settings_and_passwords(self):
        for path in [
            'users/me/',
            '/api/v1/users/me/',
            'auth/two-step/',
            'telegram/',
            'ai/approvals/',
            'projects/../users/me/',
        ]:
            err, res = self.tool('cmd_read', path=path)
            self.assertTrue(err, path)
        err, res = self.tool('cmd_write', method='PATCH', path=f'users/{self.ed.id}/', body={'password': 'Hacked-123'})
        self.assertTrue(err)
        self.assertTrue(User.objects.get(pk=self.ed.pk).check_password('Secret-pass-1'))

    def test_delete_needs_approval_each_time(self):
        err, res = self.tool('cmd_delete', path=f'clients/{self.client_obj.id}/')
        self.assertEqual(res['status'], 'waiting_for_approval')
        self.assertTrue(Client.objects.filter(pk=self.client_obj.id).exists())
        self.assertTrue(any('ai:approve:' in json.dumps(a) for a in self.sent))
        self.assertEqual(AIApproval.objects.get(pk=res['approval_id']).summary, 'Delete client “Halo Coffee”')
        app = APIClient()
        app.force_authenticate(self.owner)
        self.assertEqual(
            app.post(
                f'/api/v1/ai/approvals/{res["approval_id"]}/decide/', {'approve': True}, format='json'
            ).status_code,
            200,
        )
        err, res2 = self.tool('cmd_delete', path=f'clients/{self.client_obj.id}/', approval_id=res['approval_id'])
        self.assertFalse(err, res2)
        self.assertFalse(Client.objects.filter(pk=self.client_obj.id).exists())
        other = Client.objects.create(client_name='Other')
        err, res3 = self.tool('cmd_delete', path=f'clients/{other.id}/', approval_id=res['approval_id'])
        self.assertTrue(err)

    def test_finance_read_approved_via_telegram_button(self):
        err, res = self.tool('cmd_read', path=f'projects/{self.project.id}/', include_finance=True)
        aid = res['approval_id']
        update = {
            'callback_query': {
                'id': 'cb1',
                'data': f'ai:approve:{aid}',
                'message': {'message_id': 5, 'chat': {'id': 42}},
            }
        }
        self.http.post(
            '/api/v1/telegram/webhook/',
            json.dumps(update),
            content_type='application/json',
            HTTP_X_TELEGRAM_BOT_API_SECRET_TOKEN='s',
        )
        self.assertEqual(AIApproval.objects.get(pk=aid).status, AIApproval.APPROVED)
        err, res = self.tool('cmd_read', path=f'projects/{self.project.id}/', include_finance=True, approval_id=aid)
        self.assertFalse(err)
        self.assertEqual(float(res['data']['service_fee']), 1500)

    def test_telegram_button_from_another_chat_cannot_approve(self):
        err, res = self.tool('cmd_read', path='finance/summary/')
        update = {
            'callback_query': {
                'id': 'cb',
                'data': f'ai:approve:{res["approval_id"]}',
                'message': {'message_id': 1, 'chat': {'id': 999}},
            }
        }
        self.http.post(
            '/api/v1/telegram/webhook/',
            json.dumps(update),
            content_type='application/json',
            HTTP_X_TELEGRAM_BOT_API_SECRET_TOKEN='s',
        )
        self.assertEqual(AIApproval.objects.get(pk=res['approval_id']).status, AIApproval.PENDING)

    def test_denied_and_money_in_body_needs_approval(self):
        err, res = self.tool('cmd_write', method='PATCH', path=f'projects/{self.project.id}/', body={'service_fee': 1})
        self.assertEqual(res['status'], 'waiting_for_approval')
        app = APIClient()
        app.force_authenticate(self.owner)
        app.post(f'/api/v1/ai/approvals/{res["approval_id"]}/decide/', {'approve': False}, format='json')
        err, res = self.tool(
            'cmd_write',
            method='PATCH',
            path=f'projects/{self.project.id}/',
            body={'service_fee': 1},
            approval_id=res['approval_id'],
        )
        self.assertTrue(err)
        self.project.refresh_from_db()
        self.assertEqual(float(self.project.service_fee), 1500)

    def test_only_owner_and_project_managers_can_connect(self):
        reg = self.http.post(
            '/oauth/register', json.dumps({'redirect_uris': [REDIRECT]}), content_type='application/json'
        ).json()
        q = {
            'client_id': reg['client_id'],
            'redirect_uri': REDIRECT,
            'response_type': 'code',
            'state': 's',
            'code_challenge': 'c' * 43,
            'code_challenge_method': 'S256',
        }
        r = self.http.post('/oauth/authorize', {**q, 'username': 'ed', 'password': 'Secret-pass-1', 'action': 'allow'})
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'project managers')
        User.objects.create_user('pm', password='Secret-pass-1', role=UserRole.PROJECT_MANAGER)
        self.assertEqual(self.rpc('tools/list', token=self.connect('pm')).status_code, 200)
        self.owner.role = UserRole.EDITOR
        self.owner.save()
        self.assertEqual(self.rpc('tools/list', token=self.token).status_code, 401)

    def test_refresh_rotation_and_revoke(self):
        tok = self.http.post(
            '/oauth/token',
            {'grant_type': 'refresh_token', 'refresh_token': self.refresh, 'client_id': self.reg['client_id']},
        ).json()
        self.assertIn('access_token', tok)
        other = self.http.post(
            '/oauth/token',
            {'grant_type': 'refresh_token', 'refresh_token': tok['refresh_token'], 'client_id': 'another-registration'},
        ).json()
        self.assertIn('access_token', other)
        tok = other
        self.assertEqual(
            self.http.post(
                '/oauth/token',
                {'grant_type': 'refresh_token', 'refresh_token': self.refresh, 'client_id': self.reg['client_id']},
            ).status_code,
            400,
        )
        app = APIClient()
        app.force_authenticate(self.owner)
        conn_id = app.get('/api/v1/ai/connections/').data[-1]['id']
        app.post(f'/api/v1/ai/connections/{conn_id}/revoke/')
        self.assertEqual(self.rpc('ping', token=tok['access_token']).status_code, 401)
