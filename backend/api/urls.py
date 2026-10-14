from django.urls import include, path
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenRefreshView

from . import mcp, telegram
from .finance import AccountViewSet, CategoryViewSet, FinanceViewSet, RecurringViewSet, TransactionViewSet
from .security import LoginView, logout, two_step
from .video_views import VideoSubmissionViewSet
from .views import (
    ActivityLogViewSet,
    ClientViewSet,
    CommentViewSet,
    ContentItemViewSet,
    ContractViewSet,
    DashboardViewSet,
    NotificationViewSet,
    OrderChatViewSet,
    ProjectViewSet,
    PublishRecordViewSet,
    RevisionViewSet,
    SubmissionRecordViewSet,
    TaskChecklistItemViewSet,
    TaskViewSet,
    TemplateViewSet,
    UserViewSet,
)
from .workspace_views import CalendarViewSet, EventViewSet, PageViewSet, TodoViewSet

router = DefaultRouter()
router.register(r'users', UserViewSet, basename='user')
router.register(r'clients', ClientViewSet, basename='client')
router.register(r'projects', ProjectViewSet, basename='project')
router.register(r'contracts', ContractViewSet, basename='contract')
router.register(r'templates', TemplateViewSet, basename='template')
router.register(r'content-items', ContentItemViewSet, basename='contentitem')
router.register(r'tasks', TaskViewSet, basename='task')
router.register(r'task-checklist-items', TaskChecklistItemViewSet, basename='taskchecklistitem')
router.register(r'submissions', SubmissionRecordViewSet, basename='submissionrecord')
router.register(r'revisions', RevisionViewSet, basename='revision')
router.register(r'comments', CommentViewSet, basename='comment')
router.register(r'notifications', NotificationViewSet, basename='notification')
router.register(r'activity-logs', ActivityLogViewSet, basename='activitylog')
router.register(r'publish-records', PublishRecordViewSet, basename='publishrecord')
router.register(r'dashboards', DashboardViewSet, basename='dashboard')
router.register(r'chats', OrderChatViewSet, basename='chat')
router.register(r'workspace-pages', PageViewSet, basename='workspacepage')
router.register(r'workspace-todos', TodoViewSet, basename='workspacetodo')
router.register(r'calendar-events', EventViewSet, basename='calendarevent')
router.register(r'calendar', CalendarViewSet, basename='calendar')
router.register(r'finance/accounts', AccountViewSet, basename='financeaccount')
router.register(r'finance/categories', CategoryViewSet, basename='financecategory')
router.register(r'finance/transactions', TransactionViewSet, basename='transaction')
router.register(r'finance/recurring', RecurringViewSet, basename='recurringtransaction')
router.register(r'finance', FinanceViewSet, basename='finance')
router.register(r'video-submissions', VideoSubmissionViewSet, basename='videosubmission')

urlpatterns = [
    path('telegram/webhook/', telegram.webhook, name='telegram_webhook'),
    path('telegram/', telegram.info, name='telegram_info'),
    path('telegram/connect/', telegram.connect_link, name='telegram_connect'),
    path('telegram/test/', telegram.test_message, name='telegram_test'),
    path('auth/login/', LoginView.as_view(), name='token_obtain_pair'),
    path('auth/logout/', logout, name='logout'),
    path('auth/two-step/', two_step, name='two_step'),
    path('ai/approvals/', mcp.approvals, name='ai_approvals'),
    path('ai/approvals/<int:pk>/decide/', mcp.decide_view, name='ai_decide'),
    path('ai/connections/', mcp.connections, name='ai_connections'),
    path('ai/connections/<int:pk>/revoke/', mcp.revoke, name='ai_revoke'),
    path('auth/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('', include(router.urls)),
]
