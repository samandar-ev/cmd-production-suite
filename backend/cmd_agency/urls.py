from api import mcp, oauth
from django.conf import settings
from django.contrib import admin
from django.http import HttpResponse
from django.urls import include, path, re_path
from django.views.generic import TemplateView

urlpatterns = [path('admin/', admin.site.urls)] if settings.DEBUG else []

urlpatterns += [
    path('health/', lambda request: HttpResponse('ok', content_type='text/plain')),
    path('api/v1/', include('api.urls')),
    path('mcp', mcp.endpoint),
    path('mcp/', mcp.endpoint, name='mcp'),
    re_path(r'^\.well-known/oauth-protected-resource(?:/mcp/?)?$', oauth.protected_resource),
    re_path(r'^\.well-known/oauth-authorization-server(?:/.*)?$', oauth.authorization_server),
    path('oauth/register', oauth.register),
    path('oauth/authorize', oauth.authorize),
    path('oauth/token', oauth.token),
    re_path(r'^.*$', TemplateView.as_view(template_name='index.html')),
]
