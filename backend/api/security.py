import hashlib
import secrets
from datetime import timedelta

from django.core.cache import cache
from django.utils import timezone
from django.utils.translation import gettext as _
from django.utils.translation import override
from rest_framework import permissions, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.exceptions import AuthenticationFailed, ValidationError
from rest_framework.response import Response
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken, OutstandingToken
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView

from . import telegram
from .models import ActivityLog, User

WINDOW = 15 * 60
IP_LIMIT, USER_LIMIT = 20, 8
CODE_TTL, CODE_TRIES, CODE_RESEND = timedelta(minutes=5), 5, timedelta(seconds=30)


def _over(key, limit):
    return cache.get(key, 0) >= limit


def _hit(key):
    cache.set(key, cache.get(key, 0) + 1, WINDOW)


def client_ip(request):
    return request.headers.get('CF-Connecting-IP') or request.META.get('REMOTE_ADDR', '')


def _code_hash(user, code):
    return hashlib.sha256(f'{user.pk}:{code}'.encode()).hexdigest()


def needs_second_step(user):
    return user.two_factor_enabled and bool(user.telegram_chat_id) and telegram.enabled()


def send_code(user):
    now = timezone.now()
    if user.login_code_expires and user.login_code_expires - CODE_TTL + CODE_RESEND > now:
        return True
    code = f'{secrets.randbelow(10**6):06d}'
    with override(user.language or 'en'):
        text = _(
            '🔐 Your CMD sign-in code: <code>%(code)s</code>\nIt expires in 5 minutes. If this wasn’t you, change your password.'
        ) % {'code': code}
    if not telegram.send(user.telegram_chat_id, text):
        return False
    User.objects.filter(pk=user.pk).update(
        login_code_hash=_code_hash(user, code), login_code_expires=now + CODE_TTL, login_code_tries=0
    )
    return True


def check_code(user, code):
    if not (user.login_code_hash and user.login_code_expires and user.login_code_expires > timezone.now()):
        return False
    if user.login_code_tries >= CODE_TRIES:
        return False
    if secrets.compare_digest(user.login_code_hash, _code_hash(user, str(code).strip())):
        User.objects.filter(pk=user.pk).update(login_code_hash='', login_code_expires=None, login_code_tries=0)
        return True
    User.objects.filter(pk=user.pk).update(login_code_tries=user.login_code_tries + 1)
    return False


class LoginSerializer(TokenObtainPairSerializer):
    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        token['role'] = user.role
        return token


class LoginView(TokenObtainPairView):
    serializer_class = LoginSerializer

    def post(self, request, *args, **kwargs):
        ip_key = f'login:ip:{client_ip(request)}'
        user_key = 'login:user:' + str(request.data.get('username', '')).strip().lower()
        if _over(ip_key, IP_LIMIT) or _over(user_key, USER_LIMIT):
            return Response(
                {'error': _('Too many sign-in attempts. Please wait 15 minutes and try again.')},
                status=status.HTTP_429_TOO_MANY_REQUESTS,
            )
        _hit(ip_key)
        serializer = self.get_serializer(data=request.data)
        try:
            serializer.is_valid(raise_exception=True)
        except (AuthenticationFailed, ValidationError):
            _hit(user_key)
            raise
        user = serializer.user
        if needs_second_step(user):
            code = request.data.get('code')
            if not code:
                if not send_code(user):
                    return Response(
                        {'error': _('Could not send the sign-in code to Telegram. Try again in a minute.')}, status=503
                    )
                return Response({'code_required': True}, status=status.HTTP_202_ACCEPTED)
            user.refresh_from_db(fields=['login_code_hash', 'login_code_expires', 'login_code_tries'])
            if not check_code(user, code):
                _hit(user_key)
                return Response(
                    {
                        'error': _('Wrong or expired code. Check Telegram, or go back and request a new one.'),
                        'code_required': True,
                    },
                    status=status.HTTP_401_UNAUTHORIZED,
                )
        cache.delete(user_key)
        ActivityLog.objects.create(
            user=user,
            action_type='SIGN_IN',
            entity_type='User',
            entity_id=user.pk,
            details_json={'two_step': needs_second_step(user), 'ip': client_ip(request)},
        )
        return Response(serializer.validated_data)


@api_view(['POST'])
def two_step(request):
    user, on = request.user, bool(request.data.get('enabled'))
    if on:
        if not (user.telegram_chat_id and telegram.enabled()):
            return Response({'error': _('Connect Telegram first: the sign-in codes are sent there.')}, status=400)
        with override(user.language or 'en'):
            telegram.send(
                user.telegram_chat_id,
                _('🔐 Two-step sign-in is on. From now on you will get a code here each time you sign in.'),
            )
    elif user.two_factor_enabled and not user.check_password(str(request.data.get('password', ''))):
        return Response({'error': _('Wrong password.')}, status=400)
    User.objects.filter(pk=user.pk).update(two_factor_enabled=on)
    ActivityLog.objects.create(
        user=user,
        action_type='TWO_STEP_ON' if on else 'TWO_STEP_OFF',
        entity_type='User',
        entity_id=user.pk,
        details_json={},
    )
    result = {'two_factor_enabled': on}
    if on:
        revoke_all_tokens(user)
        refresh = RefreshToken.for_user(user)
        refresh['role'] = user.role
        result['tokens'] = {'refresh': str(refresh), 'access': str(refresh.access_token)}
    return Response(result)


@api_view(['POST'])
@permission_classes([permissions.AllowAny])
def logout(request):
    try:
        RefreshToken(request.data.get('refresh', '')).blacklist()
    except Exception:
        pass
    return Response(status=204)


def revoke_all_tokens(user):
    for token in OutstandingToken.objects.filter(user=user, expires_at__gt=timezone.now()):
        BlacklistedToken.objects.get_or_create(token=token)


class PermissionsPolicyMiddleware:
    POLICY = (
        'camera=(), microphone=(), geolocation=(), payment=(), usb=(), magnetometer=(), gyroscope=(), accelerometer=()'
    )

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        response.setdefault('Permissions-Policy', self.POLICY)
        return response
