import json
import logging
import re
import secrets
import threading
import urllib.request
from datetime import timedelta
from html import escape
from zoneinfo import ZoneInfo

from django.conf import settings
from django.utils import timezone
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy, override
from rest_framework import permissions
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from .i18n import render
from .models import Task, TaskStatus, User, UserRole, VideoSubmission

log = logging.getLogger('api.telegram')
OPEN = [TaskStatus.NOT_STARTED, TaskStatus.IN_PROGRESS, TaskStatus.OVERDUE, TaskStatus.REJECTED]


def enabled():
    return bool(settings.TELEGRAM_BOT_TOKEN)


def call(method, payload):
    req = urllib.request.Request(
        f'https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/{method}',
        data=json.dumps(payload).encode(),
        headers={'Content-Type': 'application/json'},
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        log.warning('Telegram %s failed: %s %s', method, e.code, e.read()[:300].decode(errors='replace'))
        raise


def try_call(method, payload):
    try:
        return call(method, payload)
    except Exception:
        return None


def send(chat_id, text, button=None, keyboard=None):
    payload = {'chat_id': chat_id, 'text': text, 'parse_mode': 'HTML', 'disable_web_page_preview': True}
    if button:
        keyboard = [[{'text': button[0], 'url': button[1]}]]
    if keyboard:
        payload['reply_markup'] = {'inline_keyboard': keyboard}
    try:
        call('sendMessage', payload)
        return True
    except Exception as e:
        log.warning('Telegram send to %s failed: %s', chat_id, e)
        return False


def _background(jobs):
    if jobs:
        threading.Thread(target=lambda: [send(*j) for j in jobs], daemon=True).start()


dispatch = _background


def local_time(dt):
    return timezone.localtime(dt, ZoneInfo(settings.DISPLAY_TIME_ZONE)).strftime('%d.%m.%Y, %H:%M')


def app_url(path):
    return settings.APP_BASE_URL.rstrip('/') + path


def item_path(user, entity_type, entity_id):
    if not entity_id:
        return '/'
    manager = user.role in (UserRole.OWNER, UserRole.PROJECT_MANAGER)
    paths = {
        'Task': f'/orders/{entity_id}',
        'VideoSubmission': f'/videos/{entity_id}',
        'Todo': '/workspace?view=today',
        'Event': '/calendar',
        'Project': f'/projects/{entity_id}' if manager else f'/orders/projects/{entity_id}',
        'ContentItem': f'/content/{entity_id}' if manager else '/orders',
    }
    return paths.get(entity_type, '/')


def _details(entity_type, entity_id):
    if entity_type == 'Task':
        t = Task.objects.select_related('project').filter(pk=entity_id).first()
        if t:
            return [(gettext_lazy('Project'), t.project.name)] + (
                [(gettext_lazy('Deadline'), local_time(t.due_date))] if t.due_date else []
            )
    if entity_type == 'VideoSubmission':
        v = VideoSubmission.objects.select_related('project').filter(pk=entity_id).first()
        if v:
            return [(gettext_lazy('Project'), v.project.name)]
    return []


def compose(user, title, message, params=None, details=(), entity_type=None, entity_id=None):
    with override(user.language or 'en'):
        lines = [
            f'<b>{escape(render(title, params, user.language))}</b>',
            escape(render(message, params, user.language)),
        ]
        lines += [f'{escape(str(k))}: <b>{escape(str(v))}</b>' for k, v in details]
        button = (_('Open in CMD'), app_url(item_path(user, entity_type, entity_id)))
    return '\n'.join(lines), button


def recipients(users):
    return [u for u in {u for u in users if u} if u.telegram_chat_id and u.telegram_enabled and u.is_active]


def notify_users(users, title, message, params=None, entity_type=None, entity_id=None):
    targets = recipients(users)
    if not enabled() or not targets:
        return
    details = _details(entity_type, entity_id)
    jobs = []
    for u in targets:
        text, button = compose(u, title, message, params, details, entity_type, entity_id)
        jobs.append((u.telegram_chat_id, text, button))
    dispatch(jobs)


def notify_chat_message(msg):
    from .views import project_managers

    task = msg.task
    people = {task.assigned_to, task.assigned_by, *project_managers(task.project)} - {msg.sender}
    body = msg.body or (_('📎 File: %(name)s') % {'name': msg.attachment.filename} if msg.attachment else '')
    notify_users(
        people,
        gettext_lazy('New message · %(title)s'),
        gettext_lazy('%(name)s: %(text)s'),
        {
            'title': task.title,
            'name': msg.sender.get_full_name() or msg.sender.username if msg.sender else '—',
            'text': body[:400],
        },
        'Task',
        task.id,
    )


def send_welcome(user):
    if not (enabled() and user.telegram_chat_id):
        return
    with override(user.language or 'en'):
        text = _(
            '<b>You are connected to CMD Agency</b>\nYou will get your orders, deadlines, reviews and messages here.\n'
            'Sign in with the username: <b>%(username)s</b>\n\n/tasks — your open orders'
        ) % {'username': escape(user.username)}
        dispatch([(user.telegram_chat_id, text, (_('Open CMD'), app_url('/')))])


_last_check = {'at': None}


def send_due_reminders(now=None):
    if not enabled():
        return 0
    from .views import project_managers

    now = now or timezone.now()
    sent = 0
    soon = Task.objects.filter(
        status__in=OPEN,
        due_date__gt=now,
        due_date__lte=now + timedelta(hours=24),
        reminded_due_soon_at__isnull=True,
        assigned_to__isnull=False,
    ).select_related('assigned_to', 'project')
    for t in soon:
        if not Task.objects.filter(pk=t.pk, reminded_due_soon_at__isnull=True).update(reminded_due_soon_at=now):
            continue
        notify_users(
            [t.assigned_to],
            gettext_lazy('⏰ Deadline in less than 24 hours'),
            gettext_lazy('“%(title)s” is due soon.'),
            {'title': t.title},
            'Task',
            t.id,
        )
        sent += 1
    late = Task.objects.filter(status__in=OPEN, due_date__lte=now, reminded_overdue_at__isnull=True).select_related(
        'assigned_to', 'project'
    )
    for t in late:
        if not Task.objects.filter(pk=t.pk, reminded_overdue_at__isnull=True).update(reminded_overdue_at=now):
            continue
        notify_users(
            [t.assigned_to, *project_managers(t.project)],
            gettext_lazy('⚠️ Order overdue'),
            gettext_lazy('“%(title)s” has passed its deadline.'),
            {'title': t.title},
            'Task',
            t.id,
        )
        sent += 1
    return sent


def maybe_send_reminders():
    now = timezone.now()
    if _last_check['at'] and now - _last_check['at'] < timedelta(minutes=10):
        return
    _last_check['at'] = now
    try:
        send_due_reminders(now)
    except Exception:
        log.exception('Telegram reminders failed')


class ReminderMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if enabled() and request.path.startswith('/api/'):
            maybe_send_reminders()
        return response


def _orders_text(user):
    tasks = list(
        Task.objects.filter(assigned_to=user, status__in=OPEN + [TaskStatus.WAITING_FOR_REVIEW])
        .select_related('project')
        .order_by('due_date')[:10]
    )
    if not tasks:
        lines = [_('You have no open orders. 🎉')]
    else:
        lines = [f'<b>{_("Your open orders")}</b>']
        for t in tasks:
            due = local_time(t.due_date) if t.due_date else _('no deadline')
            late = ' ⚠️' if t.due_date and t.due_date < timezone.now() and t.status in OPEN else ''
            lines.append(f'• <a href="{app_url(f"/orders/{t.id}")}">{escape(t.title)}</a> — {due}{late}')
    if user.role in (UserRole.OWNER, UserRole.PROJECT_MANAGER):
        from .views import managed_projects

        waiting = VideoSubmission.objects.filter(
            project__in=managed_projects(user), status='pending', deleted=False
        ).count()
        if waiting:
            lines.append('\n' + _('Waiting for your review: %(n)s') % {'n': waiting})
    return '\n'.join(lines)


def _help_text():
    return '\n'.join(
        [
            _('<b>CMD Agency bot</b>'),
            _('/tasks — your open orders and deadlines'),
            _('/id — your chat ID'),
            _('/stop — pause notifications'),
            _('/resume — turn notifications back on'),
        ]
    )


def handle_callback(cb):
    from .mcp import decide
    from .models import AIApproval

    chat_id = str((cb.get('message') or {}).get('chat', {}).get('id', ''))
    m = re.fullmatch(r'ai:(approve|deny):(\d+)', cb.get('data') or '')
    approval = AIApproval.objects.filter(pk=m.group(2)).select_related('user').first() if m else None
    if not approval or not chat_id or approval.user.telegram_chat_id != chat_id:
        try_call('answerCallbackQuery', {'callback_query_id': cb['id'], 'text': '—'})
        return
    approve = m.group(1) == 'approve'
    with override(approval.user.language or 'en'):
        done = decide(approval.id, approval.user, approve)
        note = (_('✅ Approved') if approve else _('❌ Denied')) if done else _('Already decided or expired.')
        try_call('answerCallbackQuery', {'callback_query_id': cb['id'], 'text': note})
        if done:
            try_call(
                'editMessageText',
                {
                    'chat_id': chat_id,
                    'message_id': cb['message']['message_id'],
                    'parse_mode': 'HTML',
                    'text': f'{escape(approval.summary[:800])}\n\n<b>{escape(note)}</b>',
                },
            )


def handle_update(update):
    if update.get('callback_query'):
        return handle_callback(update['callback_query'])
    msg = update.get('message') or {}
    chat = msg.get('chat') or {}
    text = (msg.get('text') or '').strip()
    if not chat.get('id') or chat.get('type') != 'private':
        return
    chat_id = str(chat['id'])
    user = User.objects.filter(telegram_chat_id=chat_id, is_active=True).first()
    lang = (
        user.language if user else ('ru' if (msg.get('from') or {}).get('language_code', '').startswith('ru') else 'en')
    )
    command, _sep, arg = text.partition(' ')
    command = command.split('@')[0].lower()
    with override(lang):
        if command == '/start' and arg:
            linked = User.objects.filter(
                telegram_link_code=arg.strip(), telegram_link_expires__gt=timezone.now(), is_active=True
            ).first()
            if linked:
                User.objects.filter(telegram_chat_id=chat_id).exclude(pk=linked.pk).update(
                    telegram_chat_id='', two_factor_enabled=False
                )
                linked.telegram_chat_id, linked.telegram_enabled, linked.telegram_link_code = chat_id, True, ''
                linked.save(update_fields=['telegram_chat_id', 'telegram_enabled', 'telegram_link_code'])
                with override(linked.language or 'en'):
                    send(
                        chat_id,
                        _('✅ Connected as <b>%(name)s</b>. Notifications will arrive here.')
                        % {'name': escape(linked.get_full_name() or linked.username)}
                        + '\n\n'
                        + _help_text(),
                    )
                return
            send(
                chat_id,
                _('This connect link has expired. Open Settings in the app and press “Connect Telegram” again.'),
            )
            return
        if command in ('/start', '/id'):
            lines = [_('Your chat ID: <code>%(id)s</code>') % {'id': chat_id}]
            if user:
                lines.append(
                    _('You are connected as <b>%(name)s</b>.') % {'name': escape(user.get_full_name() or user.username)}
                )
            else:
                lines.append(
                    _(
                        'Send this number to your manager so they can add it to your profile, or connect yourself in the app: Settings → Notifications → Connect Telegram.'
                    )
                )
            send(chat_id, '\n\n'.join(lines))
            return
        if not user:
            send(
                chat_id,
                _('This chat is not connected to a CMD account yet.')
                + '\n'
                + _('Your chat ID: <code>%(id)s</code>') % {'id': chat_id},
            )
            return
        if command == '/tasks':
            send(chat_id, _orders_text(user), (_('Open CMD'), app_url('/')))
        elif command == '/stop':
            User.objects.filter(pk=user.pk).update(telegram_enabled=False)
            send(chat_id, _('Notifications are paused. Send /resume to turn them back on.'))
        elif command == '/resume':
            User.objects.filter(pk=user.pk).update(telegram_enabled=True)
            send(chat_id, _('Notifications are on again.'))
        else:
            send(chat_id, _help_text())


@api_view(['POST'])
@permission_classes([permissions.AllowAny])
def webhook(request):
    if not enabled() or request.headers.get('X-Telegram-Bot-Api-Secret-Token') != settings.TELEGRAM_WEBHOOK_SECRET:
        return Response(status=403)
    try:
        handle_update(request.data)
    except Exception:
        log.exception('Telegram update failed')
    maybe_send_reminders()
    return Response({'ok': True})


@api_view(['GET'])
def info(request):
    return Response(
        {
            'enabled': enabled(),
            'bot_username': settings.TELEGRAM_BOT_USERNAME,
            'connected': bool(request.user.telegram_chat_id),
            'notifications_on': request.user.telegram_enabled,
        }
    )


@api_view(['POST'])
def connect_link(request):
    if not (enabled() and settings.TELEGRAM_BOT_USERNAME):
        return Response({'error': _('Telegram is not set up yet.')}, status=503)
    if request.user.two_factor_enabled:
        return Response(
            {'error': _('Turn off two-step sign-in before changing or disconnecting Telegram.')}, status=400
        )
    code = secrets.token_urlsafe(24)
    User.objects.filter(pk=request.user.pk).update(
        telegram_link_code=code, telegram_link_expires=timezone.now() + timedelta(hours=1)
    )
    return Response({'url': f'https://t.me/{settings.TELEGRAM_BOT_USERNAME}?start={code}'})


@api_view(['POST'])
def test_message(request):
    user = request.user
    if not (enabled() and user.telegram_chat_id):
        return Response({'error': _('Connect Telegram first.')}, status=400)
    with override(user.language or 'en'):
        ok = send(user.telegram_chat_id, _('🔔 Test notification from CMD Agency. Everything works!'))
    return (
        Response({'sent': ok})
        if ok
        else Response(
            {'error': _('Telegram did not accept the message. Press Start in the bot and try again.')}, status=502
        )
    )
