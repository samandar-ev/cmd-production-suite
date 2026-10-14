import inspect
import json
import posixpath
import re
import time
from datetime import timedelta
from urllib.parse import urlencode

from django.db import close_old_connections
from django.http import HttpResponse, JsonResponse
from django.urls import Resolver404, resolve
from django.utils import timezone
from django.utils.translation import gettext as _
from django.utils.translation import override, pgettext_lazy
from django.views.decorators.csrf import csrf_exempt
from rest_framework import serializers as drf
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework.test import APIRequestFactory, force_authenticate

from . import telegram
from .models import ActivityLog, AIApproval, AIConnection, Notification
from .oauth import base_url, connection_for, sha

PROTOCOLS = ['2025-06-18', '2025-03-26', '2024-11-05']
APPROVAL_WAIT_S, APPROVAL_VALID = 40, timedelta(minutes=30)
BLOCKED_PATHS = re.compile(r'^(users/me/|auth/|telegram/|ai/)')
BLOCKED_MODULES = ('api.security', 'api.telegram', 'api.mcp', 'api.oauth', 'rest_framework_simplejwt')
MONEY_KEYS = {
    'service_fee',
    'fee',
    'revenue',
    'income',
    'amount',
    'monthly_budget',
    'balance',
    'balances',
    'expenses',
    'expense',
    'profit',
    'net_profit',
    'gross_profit',
    'cash',
    'total_fees',
}
HIDDEN = '[hidden: finance data — repeat the call with include_finance=true; the user must approve]'
factory = APIRequestFactory()


def _has_key(obj, keys):
    if isinstance(obj, dict):
        return any(k in keys or _has_key(v, keys) for k, v in obj.items())
    if isinstance(obj, list):
        return any(_has_key(v, keys) for v in obj)
    return False


def _redact(obj):
    if isinstance(obj, dict):
        return {k: (HIDDEN if k in MONEY_KEYS and v not in (None, '', [], {}) else _redact(v)) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_redact(v) for v in obj]
    return obj


class Refused(Exception):
    pass


def _route(method, path):
    path = (path or '').strip().lstrip('/')
    path = re.sub(r'^api/v1/', '', path).split('?')[0]
    if '%' in path or '..' in path or '\\' in path:
        raise Refused(_('That path is not allowed.'))
    path = posixpath.normpath(path) + '/' if path else ''
    if not path or BLOCKED_PATHS.match(path):
        raise Refused(_('Claude can’t open settings, passwords, sign-in, Telegram or AI-connection pages.'))
    try:
        match = resolve('/api/v1/' + path)
    except Resolver404:
        raise Refused(_('No such API path. Use cmd_catalog to see what exists.')) from None
    view = getattr(match.func, 'cls', match.func)
    module = getattr(view, '__module__', '')
    if match.url_name == 'user-me' or module.startswith(BLOCKED_MODULES) or not match.route.startswith('api/v1/'):
        raise Refused(_('Claude can’t open settings, passwords, sign-in, Telegram or AI-connection pages.'))
    return path, match, module == 'api.finance'


def _dispatch(user, method, path, match, query, body):
    url = '/api/v1/' + path + ('?' + urlencode(query, doseq=True) if query else '')
    request = factory.generic(
        method,
        url,
        data=json.dumps(body) if body is not None else '',
        content_type='application/json',
        HTTP_ACCEPT_LANGUAGE=user.language or 'en',
    )
    force_authenticate(request, user=user)
    with override(user.language or 'en'):
        response = match.func(request, *match.args, **match.kwargs)
        if hasattr(response, 'render'):
            response.render()
    data = getattr(response, 'data', None)
    if data is None and response.content:
        try:
            data = json.loads(response.content)
        except ValueError:
            data = response.content.decode(errors='replace')[:2000]
    return response.status_code, data


def _ask(conn, kind, method, path, request_hash, summary):
    recent = timezone.now() - timedelta(minutes=10)
    approval = AIApproval.objects.filter(
        connection=conn, request_hash=request_hash, status=AIApproval.PENDING, created_at__gte=recent
    ).first()
    if approval:
        return approval
    approval = AIApproval.objects.create(
        connection=conn,
        user=conn.user,
        kind=kind,
        method=method,
        path=path,
        request_hash=request_hash,
        summary=summary[:1000],
    )
    user = conn.user
    with override(user.language or 'en'):
        title = _('Claude asks to see finance data') if kind == 'finance' else _('Claude asks to delete something')
        Notification.objects.create(
            recipient_user=user,
            title=title,
            message=summary[:500],
            type='ai_approval',
            related_entity_type='AIApproval',
            related_entity_id=approval.id,
        )
        if telegram.enabled() and user.telegram_chat_id:
            from html import escape

            text = f'🤖 <b>{escape(title)}</b>\n{escape(summary[:800])}\n\n' + _(
                'Approve only if you asked Claude for this.'
            )
            keyboard = [
                [
                    {'text': '✅ ' + _('Approve'), 'callback_data': f'ai:approve:{approval.id}'},
                    {'text': '❌ ' + _('Deny'), 'callback_data': f'ai:deny:{approval.id}'},
                ]
            ]
            telegram.dispatch([(user.telegram_chat_id, text, None, keyboard)])
    return approval


def _await(approval):
    deadline = time.monotonic() + APPROVAL_WAIT_S
    while time.monotonic() < deadline:
        approval.refresh_from_db(fields=['status'])
        if approval.status != AIApproval.PENDING:
            return approval.status
        time.sleep(1.5)
    return approval.status


def _use(conn, approval_id, request_hash):
    return (
        AIApproval.objects.filter(
            pk=approval_id,
            user=conn.user,
            request_hash=request_hash,
            status=AIApproval.APPROVED,
            created_at__gte=timezone.now() - APPROVAL_VALID,
        ).update(status=AIApproval.USED)
        == 1
    )


NOUNS = {
    'clients': pgettext_lazy('of the', 'client'),
    'projects': pgettext_lazy('of the', 'project'),
    'content-items': pgettext_lazy('of the', 'content item'),
    'tasks': pgettext_lazy('of the', 'order'),
    'contracts': pgettext_lazy('of the', 'contract'),
    'users': pgettext_lazy('of the', 'team member'),
    'comments': pgettext_lazy('of the', 'comment'),
    'calendar-events': pgettext_lazy('of the', 'event'),
    'workspace-todos': pgettext_lazy('of the', 'to-do'),
    'workspace-pages': pgettext_lazy('of the', 'page'),
    'video-submissions': pgettext_lazy('of the', 'file'),
    'revisions': pgettext_lazy('of the', 'revision'),
}


def _label(user, path, match):
    if 'pk' not in match.kwargs:
        return ''
    try:
        code, data = _dispatch(user, 'GET', path, match, {}, None)
    except Exception:
        return ''
    if code != 200 or not isinstance(data, dict):
        return ''
    for key in ('name', 'title', 'client_name', 'contract_number', 'full_name', 'username', 'text', 'description'):
        if data.get(key):
            return str(data[key])[:80]
    return ''


def _describe(user, method, path, match, query, body, kind):
    what = {'GET': _('read'), 'POST': _('create'), 'PUT': _('change'), 'PATCH': _('change'), 'DELETE': _('delete')}[
        method
    ]
    noun, name = NOUNS.get(path.split('/')[0]), _label(user, path, match)
    if name and noun:
        head = f'{what.capitalize()} {noun} “{name}”'
        return head + (
            ' · ' + ', '.join(f'{k}={json.dumps(v, ensure_ascii=False)[:60]}' for k, v in list(body.items())[:6])
            if body
            else ''
        )
    extra = ''
    if body:
        extra = ' · ' + ', '.join(f'{k}={json.dumps(v, ensure_ascii=False)[:60]}' for k, v in list(body.items())[:6])
    if query:
        extra += ' · ' + urlencode(query, doseq=True)[:120]
    return f'{what.capitalize()}: /{path}{extra}'


def run(conn, method, args):
    path, query, body = args.get('path', ''), args.get('query') or {}, args.get('body')
    if method == 'GET':
        body = None
    if body is not None and not isinstance(body, dict):
        return True, {'error': _('body must be a JSON object.')}
    if _has_key(body, {'password', 'new_password'}):
        return True, {'error': _('Claude can’t set or change passwords.')}
    try:
        path, match, finance = _route(method, path)
    except Refused as e:
        return True, {'error': str(e)}
    include_finance = bool(args.get('include_finance'))
    kind = (
        'delete'
        if method == 'DELETE'
        else 'finance'
        if (finance or include_finance or _has_key(body, MONEY_KEYS))
        else None
    )
    approved = False
    if kind:
        request_hash = sha(json.dumps([method, path, query, body, include_finance], sort_keys=True, default=str))
        if args.get('approval_id'):
            approved = _use(conn, args['approval_id'], request_hash)
            if not approved:
                return True, {
                    'error': _(
                        'That approval is not valid for this exact request (wrong id, denied, already used or expired).'
                    )
                }
        else:
            approval = _ask(
                conn, kind, method, path, request_hash, _describe(conn.user, method, path, match, query, body, kind)
            )
            status = _await(approval)
            if status == AIApproval.DENIED:
                return True, {'error': _('The user denied this request.')}
            if status != AIApproval.APPROVED or not _use(conn, approval.id, request_hash):
                return True, {
                    'status': 'waiting_for_approval',
                    'approval_id': approval.id,
                    'message': _(
                        'The user has been asked to approve this in the CMD app / Telegram. When they say they '
                        'approved, repeat exactly the same call with approval_id=%(id)s.'
                    )
                    % {'id': approval.id},
                }
            approved = True
    code, data = _dispatch(conn.user, method, path, match, query, body)
    if method != 'GET':
        ActivityLog.objects.create(
            user=conn.user,
            action_type=f'AI_{method}',
            entity_type='AIConnection',
            entity_id=conn.id,
            details_json={'via': conn.client.name, 'path': path, 'status': code},
        )
    if not (approved and kind == 'finance'):
        data = _redact(data)
    return code >= 400, {'status': code, 'data': data}


def _field(f):
    kind = (
        type(f).__name__.replace('Field', '').replace('PrimaryKeyRelated', 'id').replace('ManyRelated', 'id list')
        or 'value'
    )
    out = {'type': kind}
    if f.read_only:
        out['read_only'] = True
    elif f.required:
        out['required'] = True
    choices = getattr(f, 'choices', None)
    if choices and not isinstance(f, (drf.PrimaryKeyRelatedField, drf.ManyRelatedField)):
        out['choices'] = list(choices)[:15]
    return out


def catalog(search=''):
    from .urls import router

    out = []
    for prefix, viewset, _basename in router.registry:
        if BLOCKED_PATHS.match(prefix + '/'):
            continue
        entry = {'path': f'{prefix}/', 'what': (viewset.__doc__ or '').strip().split('\n')[0][:160]}
        has = lambda name, vs=viewset: hasattr(vs, name)
        entry['actions'] = [
            a
            for a, ok in [
                ('GET list', has('list')),
                ('POST create', has('create')),
                ('GET {id}/', has('retrieve')),
                ('PATCH {id}/', has('partial_update')),
                ('DELETE {id}/ (needs approval)', has('destroy')),
            ]
            if ok
        ]
        for action in viewset.get_extra_actions():
            if action.__name__ == 'me':
                continue
            methods = ','.join(m.upper() for m in action.mapping)
            doc = (action.__doc__ or '').strip().split('\n')[0][:120]
            entry['actions'].append(
                f'{methods} {"{id}/" if action.detail else ""}{action.url_path}/' + (f' — {doc}' if doc else '')
            )
        try:
            src = inspect.getsource(viewset)
            filters = sorted(
                set(re.findall(r"query_params\.get\('(\w+)'", src)) | set(re.findall(r"(\w+)='[\w_]+__?\w*'", src))
            )
            if filters:
                entry['list_filters'] = filters[:20]
        except (OSError, TypeError):
            pass
        ser = getattr(viewset, 'serializer_class', None)
        if ser:
            try:
                entry['fields'] = {n: _field(f) for n, f in ser(context={}).fields.items() if n not in ('password',)}
            except Exception:
                pass
        if prefix.startswith('finance'):
            entry['note'] = 'Finance: every call needs the user’s approval.'
        out.append(entry)
    if search:
        s = search.lower()
        out = [e for e in out if s in json.dumps(e).lower()]
    return out


_req_props = {
    'path': {
        'type': 'string',
        'description': 'API path from cmd_catalog, e.g. "projects/" or "tasks/12/" or "content-items/5/start-production/".',
    },
    'query': {'type': 'object', 'description': 'Query parameters, e.g. {"project": 3, "status": "in_progress"}.'},
    'approval_id': {'type': 'integer', 'description': 'Only when repeating a call the user has approved.'},
}
TOOLS = [
    {
        'name': 'cmd_catalog',
        'title': 'CMD: what can be done',
        'description': 'List the CMD Agency app API: endpoints, actions, fields (with required/choices) and list filters. '
        'Call this first. Optional "search" narrows it (e.g. "client", "task", "calendar").',
        'inputSchema': {'type': 'object', 'properties': {'search': {'type': 'string'}}},
        'annotations': {'readOnlyHint': True},
    },
    {
        'name': 'cmd_read',
        'title': 'CMD: read',
        'description': 'GET data from the CMD app as the signed-in user (same permissions as in the app). Money fields are '
        'hidden unless include_finance=true, which asks the user to approve first.',
        'inputSchema': {
            'type': 'object',
            'required': ['path'],
            'properties': {
                **_req_props,
                'include_finance': {
                    'type': 'boolean',
                    'description': 'Show fees/revenue/finance data (needs approval each time).',
                },
            },
        },
        'annotations': {'readOnlyHint': True},
    },
    {
        'name': 'cmd_write',
        'title': 'CMD: create or change',
        'description': 'Create or change things in the CMD app as the signed-in user: clients, projects, content items, '
        'orders/tasks and assignments, production, reviews, chat messages to employees, calendar, to-dos… '
        'method POST (create / actions) or PATCH (change). Anything with money needs the user’s approval.',
        'inputSchema': {
            'type': 'object',
            'required': ['method', 'path'],
            'properties': {
                'method': {'type': 'string', 'enum': ['POST', 'PATCH', 'PUT']},
                **_req_props,
                'body': {'type': 'object', 'description': 'JSON body (fields from cmd_catalog).'},
            },
        },
        'annotations': {'readOnlyHint': False, 'destructiveHint': False},
    },
    {
        'name': 'cmd_delete',
        'title': 'CMD: delete (needs approval)',
        'description': 'DELETE something in the CMD app. The user must approve every deletion in the app or Telegram.',
        'inputSchema': {'type': 'object', 'required': ['path'], 'properties': _req_props},
        'annotations': {'readOnlyHint': False, 'destructiveHint': True},
    },
]
INSTRUCTIONS = (
    'This is the CMD Agency management app (marketing/video agency). You act as the signed-in user with their '
    'permissions. Start with cmd_catalog to find endpoints and fields. Ids come from list calls (e.g. '
    'GET clients/ before creating a project for a client). Production for a content item is started with '
    'POST content-items/{id}/start-production/ (creates and assigns the shoot/edit orders); employees are '
    'messaged in order chats via POST chats/{task_id}/messages/ {"body": "..."}. Finance data and deletions need the '
    'user’s approval: tell them to approve in the CMD app or Telegram, then repeat the call with approval_id. '
    'You cannot open settings or passwords.'
)


def call_tool(conn, name, args):
    if name == 'cmd_catalog':
        return False, {
            'you': {'name': conn.user.get_full_name() or conn.user.username, 'role': conn.user.role},
            'api': catalog(args.get('search', '')),
        }
    if name == 'cmd_read':
        return run(conn, 'GET', args)
    if name == 'cmd_write':
        method = str(args.get('method', 'POST')).upper()
        if method not in ('POST', 'PATCH', 'PUT'):
            return True, {'error': 'method must be POST, PATCH or PUT'}
        return run(conn, method, args)
    if name == 'cmd_delete':
        return run(conn, 'DELETE', args)
    return True, {'error': f'Unknown tool {name}'}


def _text(payload, limit=60000):
    text = json.dumps(payload, ensure_ascii=False, default=str, indent=1)
    return text if len(text) <= limit else text[:limit] + '\n… (truncated — narrow the request with query filters)'


def handle(conn, msg):
    rid, method, params = msg.get('id'), msg.get('method'), msg.get('params') or {}
    if rid is None:
        return None
    ok = lambda result: {'jsonrpc': '2.0', 'id': rid, 'result': result}
    if method == 'initialize':
        wanted = params.get('protocolVersion')
        return ok(
            {
                'protocolVersion': wanted if wanted in PROTOCOLS else PROTOCOLS[0],
                'capabilities': {'tools': {'listChanged': False}},
                'serverInfo': {'name': 'cmd-agency', 'title': 'CMD Agency', 'version': '1.0'},
                'instructions': INSTRUCTIONS,
            }
        )
    if method == 'ping':
        return ok({})
    if method == 'tools/list':
        return ok({'tools': TOOLS})
    if method == 'tools/call':
        try:
            is_error, payload = call_tool(conn, params.get('name'), params.get('arguments') or {})
        except Exception as e:
            is_error, payload = True, {'error': f'{type(e).__name__}: {e}'}
        return ok({'content': [{'type': 'text', 'text': _text(payload)}], 'isError': is_error})
    return {'jsonrpc': '2.0', 'id': rid, 'error': {'code': -32601, 'message': f'Method not found: {method}'}}


@csrf_exempt
def endpoint(request):
    conn = connection_for(request)
    if not conn:
        response = JsonResponse({'error': 'invalid_token'}, status=401)
        response['WWW-Authenticate'] = (
            f'Bearer resource_metadata="{base_url(request)}/.well-known/oauth-protected-resource"'
        )
        return response
    if request.method != 'POST':
        response = HttpResponse(status=405)
        response['Allow'] = 'POST'
        return response
    try:
        msg = json.loads(request.body)
    except ValueError:
        return JsonResponse(
            {'jsonrpc': '2.0', 'id': None, 'error': {'code': -32700, 'message': 'Parse error'}}, status=400
        )
    if isinstance(msg, list):
        replies = [r for r in (handle(conn, m) for m in msg) if r]
        return JsonResponse(replies, safe=False) if replies else HttpResponse(status=202)
    reply = handle(conn, msg)
    close_old_connections()
    return JsonResponse(reply) if reply else HttpResponse(status=202)


@api_view(['GET'])
def approvals(request):
    rows = AIApproval.objects.filter(user=request.user).select_related('connection__client')[:50]
    return Response(
        [
            {
                'id': a.id,
                'kind': a.kind,
                'summary': a.summary,
                'status': a.status,
                'created_at': a.created_at,
                'decided_at': a.decided_at,
                'app': a.connection.client.name,
            }
            for a in rows
        ]
    )


def decide(approval_id, user, approve):
    return (
        AIApproval.objects.filter(pk=approval_id, user=user, status=AIApproval.PENDING).update(
            status=AIApproval.APPROVED if approve else AIApproval.DENIED, decided_at=timezone.now()
        )
        == 1
    )


@api_view(['POST'])
def decide_view(request, pk):
    if not decide(pk, request.user, bool(request.data.get('approve'))):
        return Response({'error': _('This request was already decided or has expired.')}, status=400)
    return Response({'ok': True})


@api_view(['GET'])
def connections(request):
    rows = AIConnection.objects.filter(
        user=request.user, revoked=False, refresh_expires__gt=timezone.now()
    ).select_related('client')
    return Response(
        [{'id': c.id, 'app': c.client.name, 'created_at': c.created_at, 'last_used_at': c.last_used_at} for c in rows]
    )


@api_view(['POST'])
def revoke(request, pk):
    AIConnection.objects.filter(pk=pk, user=request.user).update(revoked=True)
    return Response({'ok': True})
