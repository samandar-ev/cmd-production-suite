from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from api import telegram

COMMANDS = {
    'en': [
        ('tasks', 'My open orders and deadlines'),
        ('id', 'My chat ID'),
        ('stop', 'Pause notifications'),
        ('resume', 'Turn notifications back on'),
        ('help', 'Help'),
    ],
    'ru': [
        ('tasks', 'Мои открытые заказы и сроки'),
        ('id', 'Мой chat ID'),
        ('stop', 'Приостановить уведомления'),
        ('resume', 'Снова включить уведомления'),
        ('help', 'Справка'),
    ],
}


class Command(BaseCommand):
    help = (
        'Point the Telegram bot at this app (webhook + command menu). Run once after deploying or changing the domain.'
    )

    def handle(self, *args, **opts):
        if not (settings.TELEGRAM_BOT_TOKEN and settings.TELEGRAM_WEBHOOK_SECRET):
            raise CommandError('Set TELEGRAM_BOT_TOKEN and TELEGRAM_WEBHOOK_SECRET first.')
        url = telegram.app_url('/api/v1/telegram/webhook/')
        telegram.call(
            'setWebhook',
            {
                'url': url,
                'secret_token': settings.TELEGRAM_WEBHOOK_SECRET,
                'allowed_updates': ['message', 'callback_query'],
                'drop_pending_updates': True,
            },
        )
        for lang, cmds in COMMANDS.items():
            payload = {'commands': [{'command': c, 'description': d} for c, d in cmds]}
            if lang != 'en':
                payload['language_code'] = lang
            telegram.call('setMyCommands', payload)
        me = telegram.call('getMe', {})['result']
        self.stdout.write(self.style.SUCCESS(f'Webhook set to {url} for @{me["username"]}'))
