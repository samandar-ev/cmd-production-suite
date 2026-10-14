from datetime import timedelta
from unittest import mock

from django.core.cache import cache
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from api import telegram
from api.models import User, UserRole

LOGIN = '/api/v1/auth/login/'


@override_settings(TELEGRAM_BOT_TOKEN='1:x', TELEGRAM_WEBHOOK_SECRET='s', TELEGRAM_BOT_USERNAME='bot')
class SecurityTest(TestCase):
    def setUp(self):
        cache.clear()
        self.api = APIClient()
        self.ed = User.objects.create_user('ed', password='Secret-pass-1', role=UserRole.EDITOR)
        self.owner = User.objects.create_user(
            'boss', password='Secret-pass-1', role=UserRole.OWNER, telegram_chat_id='42', two_factor_enabled=True
        )
        self.sent = []
        p = mock.patch.object(telegram, 'send', side_effect=lambda c, t, b=None: self.sent.append(t) or True)
        p.start()
        self.addCleanup(p.stop)

    def login(self, user, password='Secret-pass-1', **extra):
        return self.api.post(LOGIN, {'username': user, 'password': password, **extra}, format='json')

    def test_failed_logins_are_limited_per_username(self):
        for _ in range(8):
            self.assertEqual(self.login('ed', 'wrong').status_code, 401)
        self.assertEqual(self.login('ed').status_code, 429)

    def test_lock_lasts_15_minutes(self):
        for _ in range(8):
            self.login('ed', 'wrong')
        with mock.patch(
            'django.core.cache.backends.filebased.time.time', return_value=__import__('time').time() + 14 * 60
        ):
            self.assertEqual(self.login('ed').status_code, 429)
        with mock.patch(
            'django.core.cache.backends.filebased.time.time', return_value=__import__('time').time() + 16 * 60
        ):
            self.assertEqual(self.login('ed').status_code, 200)

    def test_success_resets_the_counter(self):
        for _ in range(5):
            self.login('ed', 'wrong')
        self.assertEqual(self.login('ed').status_code, 200)
        for _ in range(5):
            self.login('ed', 'wrong')
        self.assertEqual(self.login('ed').status_code, 200)

    def test_owner_needs_telegram_code(self):
        r = self.login('boss')
        self.assertEqual(r.status_code, 202)
        self.assertNotIn('access', r.data)
        code = self.sent[-1].split('<code>')[1].split('</code>')[0]
        self.assertEqual(self.login('boss', code='000000' if code != '000000' else '111111').status_code, 401)
        r = self.login('boss', code=code)
        self.assertEqual(r.status_code, 200)
        self.assertIn('access', r.data)
        self.assertEqual(self.login('boss', code=code).status_code, 401)

    def test_code_expires_and_wrong_password_never_sends_code(self):
        self.assertEqual(self.login('boss', 'wrong').status_code, 401)
        self.assertEqual(self.sent, [])
        self.login('boss')
        code = self.sent[-1].split('<code>')[1].split('</code>')[0]
        User.objects.filter(pk=self.owner.pk).update(login_code_expires=timezone.now() - timedelta(seconds=1))
        self.assertEqual(self.login('boss', code=code).status_code, 401)

    def test_two_step_is_opt_in_for_everyone(self):
        User.objects.filter(pk=self.ed.pk).update(telegram_chat_id='7')
        self.assertEqual(self.login('ed').status_code, 200)
        self.ed.refresh_from_db()
        self.api.force_authenticate(self.ed)
        self.assertEqual(self.api.post('/api/v1/auth/two-step/', {'enabled': True}, format='json').status_code, 200)
        self.api.force_authenticate(None)
        self.assertEqual(self.login('ed').status_code, 202)

    def test_turning_off_needs_password_and_blocks_telegram_changes(self):
        self.api.force_authenticate(self.owner)
        self.assertEqual(self.api.patch('/api/v1/users/me/', {'telegram_chat_id': ''}, format='json').status_code, 400)
        self.assertEqual(self.api.post('/api/v1/telegram/connect/').status_code, 400)
        self.assertEqual(
            self.api.post('/api/v1/auth/two-step/', {'enabled': False, 'password': 'nope'}, format='json').status_code,
            400,
        )
        self.assertEqual(
            self.api.post(
                '/api/v1/auth/two-step/', {'enabled': False, 'password': 'Secret-pass-1'}, format='json'
            ).status_code,
            200,
        )
        self.owner.refresh_from_db()
        self.assertFalse(self.owner.two_factor_enabled)

    def test_turning_on_signs_out_other_sessions_and_logs(self):
        User.objects.filter(pk=self.ed.pk).update(telegram_chat_id='7')
        other = self.login('ed').data
        self.ed.refresh_from_db()
        self.api.force_authenticate(self.ed)
        r = self.api.post('/api/v1/auth/two-step/', {'enabled': True}, format='json')
        self.api.force_authenticate(None)
        self.assertEqual(
            self.api.post('/api/v1/auth/refresh/', {'refresh': other['refresh']}, format='json').status_code, 401
        )
        self.assertEqual(
            self.api.post('/api/v1/auth/refresh/', {'refresh': r.data['tokens']['refresh']}, format='json').status_code,
            200,
        )
        from api.models import ActivityLog

        self.assertTrue(ActivityLog.objects.filter(user=self.ed, action_type='TWO_STEP_ON').exists())
        self.assertEqual(
            ActivityLog.objects.filter(user=self.ed, action_type='SIGN_IN').first().details_json['two_step'], False
        )

    def test_cannot_turn_on_without_telegram(self):
        self.api.force_authenticate(self.ed)
        self.assertEqual(self.api.post('/api/v1/auth/two-step/', {'enabled': True}, format='json').status_code, 400)

    def test_manager_clearing_chat_turns_two_step_off(self):
        self.api.force_authenticate(self.owner)
        User.objects.filter(pk=self.ed.pk).update(telegram_chat_id='7', two_factor_enabled=True)
        self.api.patch(f'/api/v1/users/{self.ed.id}/', {'telegram_chat_id': ''}, format='json')
        self.ed.refresh_from_db()
        self.assertFalse(self.ed.two_factor_enabled)

    def test_owner_without_telegram_signs_in_with_password(self):
        User.objects.filter(pk=self.owner.pk).update(telegram_chat_id='')
        self.assertEqual(self.login('boss').status_code, 200)

    def test_logout_and_rotation_revoke_refresh_tokens(self):
        tokens = self.login('ed').data
        r = self.api.post('/api/v1/auth/refresh/', {'refresh': tokens['refresh']}, format='json')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(
            self.api.post('/api/v1/auth/refresh/', {'refresh': tokens['refresh']}, format='json').status_code, 401
        )
        self.api.post('/api/v1/auth/logout/', {'refresh': r.data['refresh']}, format='json')
        self.assertEqual(
            self.api.post('/api/v1/auth/refresh/', {'refresh': r.data['refresh']}, format='json').status_code, 401
        )

    def test_password_change_signs_out_other_devices_but_keeps_this_one(self):
        other = self.login('ed').data
        self.api.force_authenticate(self.ed)
        r = self.api.patch('/api/v1/users/me/', {'password': 'New-secret-pass-2'}, format='json')
        self.assertIn('tokens', r.data)
        self.api.force_authenticate(None)
        self.assertEqual(
            self.api.post('/api/v1/auth/refresh/', {'refresh': other['refresh']}, format='json').status_code, 401
        )
        self.assertEqual(
            self.api.post('/api/v1/auth/refresh/', {'refresh': r.data['tokens']['refresh']}, format='json').status_code,
            200,
        )

    @override_settings(DEBUG=False)
    def test_security_headers(self):
        r = self.api.get('/api/v1/auth/logout/', secure=True)
        self.assertIn("script-src 'self'", r['Content-Security-Policy'])
        self.assertIn('camera=()', r['Permissions-Policy'])
