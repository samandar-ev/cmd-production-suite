import base64
import hashlib
import json
import logging
import re
import secrets
from datetime import timedelta
from urllib.parse import urlencode

from django.conf import settings
from django.contrib.auth import authenticate
from django.http import HttpResponseRedirect, JsonResponse
from django.shortcuts import render
from django.utils import timezone
from django.utils.csp import CSP
from django.utils.translation import gettext as _
from django.views.decorators.csp import csp_override
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from .models import ActivityLog, AIAuthCode, AIConnection, OAuthClient, User
from .security import IP_LIMIT, USER_LIMIT, _hit, _over, check_code, client_ip, needs_second_step, send_code

log = logging.getLogger('api.telegram')
ACCESS_TTL, REFRESH_TTL, CODE_TTL = timedelta(hours=1), timedelta(days=30), timedelta(minutes=5)
REDIRECT_OK = re.compile(r'^(https://([a-z0-9-]+\.)?claude\.(ai|com)/|http://(localhost|127\.0\.0\.1)(:\d+)?/)')


def can_use_ai(user):
    return user.is_active and user.role in ('OWNER', 'PROJECT_MANAGER')


def sha(value):
    return hashlib.sha256(value.encode()).hexdigest()


def base_url(request):
    return request.build_absolute_uri('/').rstrip('/')


def protected_resource(request):
    base = base_url(request)
    return JsonResponse(
        {
            'resource': f'{base}/mcp/',
            'authorization_servers': [base],
            'scopes_supported': ['cmd'],
            'bearer_methods_supported': ['header'],
        }
    )


def authorization_server(request):
    base = base_url(request)
    return JsonResponse(
        {
            'issuer': base,
            'authorization_endpoint': f'{base}/oauth/authorize',
            'token_endpoint': f'{base}/oauth/token',
            'registration_endpoint': f'{base}/oauth/register',
            'scopes_supported': ['cmd'],
            'response_types_supported': ['code'],
            'grant_types_supported': ['authorization_code', 'refresh_token'],
            'code_challenge_methods_supported': ['S256'],
            'token_endpoint_auth_methods_supported': ['none'],
        }
    )


@csrf_exempt
@require_POST
def register(request):
    ip_key = f'oauth:register:{client_ip(request)}'
    if _over(ip_key, IP_LIMIT):
        return JsonResponse({'error': 'slow_down'}, status=429)
    _hit(ip_key)
    try:
        data = json.loads(request.body or b'{}')
    except ValueError:
        return JsonResponse({'error': 'invalid_client_metadata'}, status=400)
    uris = data.get('redirect_uris') or []
    if not uris or not all(isinstance(u, str) and REDIRECT_OK.match(u) for u in uris):
        return JsonResponse(
            {
                'error': 'invalid_redirect_uri',
                'error_description': 'Only Claude (claude.ai / claude.com) or localhost redirect URIs are allowed.',
            },
            status=400,
        )
    client = OAuthClient.objects.create(
        client_id=secrets.token_urlsafe(24), name=str(data.get('client_name') or 'AI app')[:200], redirect_uris=uris
    )
    return JsonResponse(
        {
            'client_id': client.client_id,
            'client_name': client.name,
            'redirect_uris': uris,
            'token_endpoint_auth_method': 'none',
            'grant_types': ['authorization_code', 'refresh_token'],
            'response_types': ['code'],
        },
        status=201,
    )


def _back(redirect_uri, **params):
    return HttpResponseRedirect(f'{redirect_uri}{"&" if "?" in redirect_uri else "?"}{urlencode(params)}')


AUTH_FIELDS = ('client_id', 'redirect_uri', 'state', 'code_challenge', 'code_challenge_method', 'scope', 'resource')


@csp_override(
    {
        **settings.SECURE_CSP,
        'form-action': [
            CSP.SELF,
            'https://claude.ai',
            'https://*.claude.ai',
            'https://claude.com',
            'https://*.claude.com',
            'http://localhost:*',
            'http://127.0.0.1:*',
        ],
    }
)
def authorize(request):
    q = request.POST if request.method == 'POST' else request.GET
    params = {k: q.get(k, '') for k in AUTH_FIELDS}
    client = OAuthClient.objects.filter(client_id=params['client_id']).first()
    if not client or params['redirect_uri'] not in client.redirect_uris:
        return render(
            request,
            'oauth_authorize.html',
            {'fatal': _('This connection link is not valid. Start connecting again from Claude.')},
            status=400,
        )
    if (
        q.get('response_type', 'code') != 'code'
        or not params['code_challenge']
        or params['code_challenge_method'] not in ('S256', '')
    ):
        return _back(params['redirect_uri'], error='invalid_request', state=params['state'])
    ctx = {'client': client, 'params': params, 'step': 'login'}
    if request.method == 'GET':
        return render(request, 'oauth_authorize.html', ctx)
    if q.get('action') == 'deny':
        return _back(params['redirect_uri'], error='access_denied', state=params['state'])

    pending_key = 'ai_oauth:' + sha(json.dumps(params, sort_keys=True))
    if q.get('step') == 'code':
        user = User.objects.filter(pk=request.session.get(pending_key), is_active=True).first()
        if not user:
            return render(
                request, 'oauth_authorize.html', {**ctx, 'error': _('Your sign-in expired. Please sign in again.')}
            )
        if not check_code(user, q.get('code', '')):
            _hit('login:user:' + user.username.lower())
            return render(
                request,
                'oauth_authorize.html',
                {
                    **ctx,
                    'step': 'code',
                    'error': _('Wrong or expired code. Check Telegram, or go back and request a new one.'),
                },
            )
        request.session.pop(pending_key, None)
    else:
        username = q.get('username', '').strip()
        ip_key, user_key = f'login:ip:{client_ip(request)}', 'login:user:' + username.lower()
        if _over(ip_key, IP_LIMIT) or _over(user_key, USER_LIMIT):
            return render(
                request,
                'oauth_authorize.html',
                {**ctx, 'error': _('Too many sign-in attempts. Please wait 15 minutes and try again.')},
            )
        _hit(ip_key)
        user = authenticate(request, username=username, password=q.get('password', ''))
        if not user:
            _hit(user_key)
            return render(
                request,
                'oauth_authorize.html',
                {**ctx, 'username': username, 'error': _('Invalid username or password. Please try again.')},
            )
        if not can_use_ai(user):
            return render(
                request,
                'oauth_authorize.html',
                {
                    **ctx,
                    'username': username,
                    'error': _('Only the owner and project managers can connect AI apps to CMD.'),
                },
            )
        if needs_second_step(user):
            if not send_code(user):
                return render(
                    request,
                    'oauth_authorize.html',
                    {**ctx, 'error': _('Could not send the sign-in code to Telegram. Try again in a minute.')},
                )
            request.session[pending_key] = user.pk
            return render(request, 'oauth_authorize.html', {**ctx, 'step': 'code'})

    ActivityLog.objects.create(
        user=user,
        action_type='SIGN_IN',
        entity_type='User',
        entity_id=user.pk,
        details_json={'two_step': needs_second_step(user), 'via': client.name, 'ip': client_ip(request)},
    )
    code = secrets.token_urlsafe(32)
    AIAuthCode.objects.create(
        code_hash=sha(code),
        client=client,
        user=user,
        redirect_uri=params['redirect_uri'],
        code_challenge=params['code_challenge'],
        expires_at=timezone.now() + CODE_TTL,
    )
    return _back(params['redirect_uri'], code=code, state=params['state'])


def _tokens(connection):
    access, refresh = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
    now = timezone.now()
    connection.access_hash, connection.access_expires = sha(access), now + ACCESS_TTL
    connection.refresh_hash, connection.refresh_expires = sha(refresh), now + REFRESH_TTL
    connection.save()
    return JsonResponse(
        {
            'access_token': access,
            'token_type': 'Bearer',
            'expires_in': int(ACCESS_TTL.total_seconds()),
            'refresh_token': refresh,
            'scope': 'cmd',
        }
    )


@csrf_exempt
@require_POST
def token(request):
    data = request.POST if request.POST else json.loads(request.body or b'{}')
    grant, client_id = data.get('grant_type'), data.get('client_id', '')

    def bad(reason):
        log.warning('OAuth token %s refused: %s (client %s)', grant, reason, client_id[:12])
        return JsonResponse({'error': 'invalid_grant', 'error_description': reason}, status=400)

    if grant == 'authorization_code':
        code = (
            AIAuthCode.objects.filter(code_hash=sha(data.get('code', '')), expires_at__gt=timezone.now())
            .select_related('client')
            .first()
        )
        if not code:
            return bad('unknown or expired code')
        code.delete()
        verifier = data.get('code_verifier', '')
        challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b'=').decode()
        if (
            code.client.client_id != client_id
            or code.redirect_uri != data.get('redirect_uri')
            or not secrets.compare_digest(challenge, code.code_challenge)
            or not can_use_ai(code.user)
        ):
            return bad('client, redirect URI or PKCE verifier does not match')
        return _tokens(AIConnection(user=code.user, client=code.client))
    if grant == 'refresh_token':
        conn = (
            AIConnection.objects.filter(
                refresh_hash=sha(data.get('refresh_token', '')), revoked=False, refresh_expires__gt=timezone.now()
            )
            .select_related('client', 'user')
            .first()
        )
        if not conn:
            return bad('unknown, revoked or expired refresh token')
        if not can_use_ai(conn.user):
            return bad('account deactivated or not allowed to use AI apps')
        return _tokens(conn)
    return JsonResponse({'error': 'unsupported_grant_type'}, status=400)


def connection_for(request):
    header = request.headers.get('Authorization', '')
    if not header.startswith('Bearer '):
        return None
    conn = (
        AIConnection.objects.filter(
            access_hash=sha(header[7:].strip()), revoked=False, access_expires__gt=timezone.now()
        )
        .select_related('user', 'client')
        .first()
    )
    if conn and can_use_ai(conn.user):
        if not conn.last_used_at or timezone.now() - conn.last_used_at > timedelta(minutes=5):
            AIConnection.objects.filter(pk=conn.pk).update(last_used_at=timezone.now())
        return conn
    return None
