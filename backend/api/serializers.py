from django.utils.translation import gettext as _
from rest_framework import serializers

from . import telegram
from .models import (
    ActivityLog,
    Client,
    Comment,
    ContentItem,
    Contract,
    Notification,
    Project,
    PublishRecord,
    Revision,
    SubmissionRecord,
    Task,
    TaskChecklistItem,
    Template,
    User,
    UserRole,
)


def unread_count(task, user):
    from .models import OrderChatRead

    read = OrderChatRead.objects.filter(task=task, user=user).values_list('last_read_at', flat=True).first()
    msgs = task.messages.exclude(sender=user)
    return (msgs.filter(created_at__gt=read) if read else msgs).count()


def display_name(user):
    if not user:
        return None
    return user.get_full_name() or user.username


class UserSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, required=False, allow_blank=True)
    full_name = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            'id',
            'username',
            'email',
            'first_name',
            'last_name',
            'full_name',
            'phone',
            'role',
            'avatar_url',
            'language',
            'telegram_chat_id',
            'telegram_enabled',
            'two_factor_enabled',
            'is_active',
            'password',
            'created_at',
            'updated_at',
        ]
        extra_kwargs = {'email': {'required': False, 'allow_blank': True}}
        read_only_fields = ['two_factor_enabled']

    def get_full_name(self, obj):
        return display_name(obj)

    def validate_telegram_chat_id(self, value):
        value = (value or '').strip()
        if value and not value.lstrip('-').isdigit():
            raise serializers.ValidationError(
                _('Chat ID is a number. The person gets it by pressing Start in the bot.')
            )
        return value

    def validate(self, data):
        if not self.instance and not data.get('password'):
            raise serializers.ValidationError({'password': _('Password is required.')})
        if not self.instance and not (data.get('first_name') or '').strip():
            raise serializers.ValidationError({'first_name': _('Name is required.')})
        return data

    def create(self, validated_data):
        user = User.objects.create_user(**validated_data)
        telegram.send_welcome(user)
        return user

    def update(self, instance, validated_data):
        password = validated_data.pop('password', None)
        old_chat = instance.telegram_chat_id
        instance = super().update(instance, validated_data)
        if password:
            instance.set_password(password)
            instance.save()
            from .security import revoke_all_tokens

            revoke_all_tokens(instance)
        if instance.telegram_chat_id != old_chat:
            if instance.two_factor_enabled:
                User.objects.filter(pk=instance.pk).update(two_factor_enabled=False)
                instance.two_factor_enabled = False
            telegram.send_welcome(instance)
        return instance


class ClientSerializer(serializers.ModelSerializer):
    project_count = serializers.SerializerMethodField()
    active_project_count = serializers.SerializerMethodField()

    class Meta:
        model = Client
        fields = '__all__'

    def _projects(self, obj):
        request = self.context.get('request')
        qs = obj.projects.all()
        if request and request.user.role != UserRole.OWNER:
            from django.db.models import Q

            qs = qs.filter(Q(project_manager=request.user) | Q(owner=request.user))
        return qs

    def get_project_count(self, obj):
        return self._projects(obj).exclude(status='archived').count()

    def get_active_project_count(self, obj):
        return self._projects(obj).filter(status='active').count()


class ProjectSerializer(serializers.ModelSerializer):
    client_name = serializers.CharField(source='client.client_name', read_only=True)
    project_manager_name = serializers.SerializerMethodField()
    owner = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = Project
        fields = '__all__'

    def get_project_manager_name(self, obj):
        return display_name(obj.project_manager)

    def _is_owner(self):
        request = self.context.get('request')
        return bool(request and request.user.role == UserRole.OWNER)

    def to_representation(self, obj):
        data = super().to_representation(obj)
        if not self._is_owner():
            data.pop('service_fee', None)
        return data

    def validate(self, data):
        if not self._is_owner():
            data.pop('service_fee', None)
        start = data.get('start_date', getattr(self.instance, 'start_date', None))
        end = data.get('end_date', getattr(self.instance, 'end_date', None))
        if start and end and start > end:
            raise serializers.ValidationError(_('End date must be after start date.'))
        if data.get('service_fee') is not None and data['service_fee'] < 0:
            raise serializers.ValidationError(_('Service fee cannot be negative.'))
        pm = data.get('project_manager')
        if pm and pm.role not in (UserRole.PROJECT_MANAGER, UserRole.OWNER):
            raise serializers.ValidationError(_('The project manager must be a project manager or an owner.'))
        return data


class ProjectOrderSerializer(serializers.ModelSerializer):
    client_name = serializers.CharField(source='client.client_name', read_only=True)
    project_manager_name = serializers.SerializerMethodField()

    class Meta:
        model = Project
        fields = [
            'id',
            'name',
            'client_name',
            'status',
            'start_date',
            'end_date',
            'project_manager',
            'project_manager_name',
        ]

    def get_project_manager_name(self, obj):
        return display_name(obj.project_manager)


class ContractSerializer(serializers.ModelSerializer):
    project_name = serializers.CharField(source='project.name', read_only=True)
    client_name = serializers.CharField(source='project.client.client_name', read_only=True)

    class Meta:
        model = Contract
        fields = '__all__'


class TemplateSerializer(serializers.ModelSerializer):
    created_by_name = serializers.SerializerMethodField()

    class Meta:
        model = Template
        fields = '__all__'
        read_only_fields = ['created_by']

    def get_created_by_name(self, obj):
        return display_name(obj.created_by) if obj.created_by else None


class ContentItemSerializer(serializers.ModelSerializer):
    project_name = serializers.CharField(source='project.name', read_only=True)
    client_name = serializers.CharField(source='project.client.client_name', read_only=True)
    videographer_name = serializers.SerializerMethodField()
    editor_name = serializers.SerializerMethodField()
    production = serializers.SerializerMethodField()

    class Meta:
        model = ContentItem
        fields = '__all__'
        read_only_fields = ['created_by', 'revision_count', 'status', 'status_changed_at']

    def get_videographer_name(self, obj):
        return display_name(obj.assigned_videographer)

    def get_production(self, obj):
        from .workflow import is_blocked, production_tasks

        out = []
        for t in production_tasks(obj):
            latest = t.file_submissions.exclude(status='uploading').order_by('-created_at').first()
            out.append(
                {
                    'task': t.id,
                    'stage': t.stage,
                    'status': t.status,
                    'assignee': display_name(t.assigned_to),
                    'due_date': t.due_date,
                    'is_blocked': is_blocked(t),
                    'latest_submission': {'id': latest.id, 'status': latest.status, 'version': latest.version}
                    if latest
                    else None,
                }
            )
        return out

    def get_editor_name(self, obj):
        return display_name(obj.assigned_editor)

    def validate(self, data):
        if data.get('assigned_videographer'):
            if data['assigned_videographer'].role != UserRole.VIDEOGRAPHER:
                raise serializers.ValidationError(_('The assigned videographer must have the Videographer role.'))
        if data.get('assigned_editor'):
            if data['assigned_editor'].role != UserRole.EDITOR:
                raise serializers.ValidationError(_('The assigned editor must have the Editor role.'))
        return data


class TaskChecklistItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = TaskChecklistItem
        fields = '__all__'


class TaskSerializer(serializers.ModelSerializer):
    checklist_items = TaskChecklistItemSerializer(many=True, read_only=True)
    project_name = serializers.CharField(source='project.name', read_only=True)
    content_item_title = serializers.CharField(source='content_item.title', read_only=True, default=None)
    assigned_to_name = serializers.SerializerMethodField()
    project_manager_name = serializers.SerializerMethodField()
    is_overdue = serializers.SerializerMethodField()
    content_item_platform = serializers.CharField(source='content_item.platform', read_only=True, default=None)
    content_item_type = serializers.CharField(source='content_item.content_type', read_only=True, default=None)
    content_item_script = serializers.CharField(source='content_item.script_scenario', read_only=True, default=None)
    content_item_location = serializers.CharField(source='content_item.shooting_location', read_only=True, default=None)
    latest_submission = serializers.SerializerMethodField()
    unread_messages = serializers.SerializerMethodField()
    is_blocked = serializers.SerializerMethodField()
    waiting_for = serializers.SerializerMethodField()
    input_files = serializers.SerializerMethodField()

    class Meta:
        model = Task
        fields = '__all__'
        read_only_fields = ['assigned_by', 'status', 'completed_at']

    def get_assigned_to_name(self, obj):
        return display_name(obj.assigned_to)

    def get_project_manager_name(self, obj):
        return display_name(obj.project.project_manager)

    def get_latest_submission(self, obj):
        sub = obj.file_submissions.exclude(status='uploading').order_by('-created_at').first()
        return {'id': sub.id, 'status': sub.status, 'version': sub.version} if sub else None

    def get_is_blocked(self, obj):
        from .workflow import is_blocked

        return is_blocked(obj)

    def get_waiting_for(self, obj):
        dep = obj.depends_on
        if not dep or dep.status == 'completed':
            return None
        return {'id': dep.id, 'stage': dep.stage, 'assignee': display_name(dep.assigned_to)}

    def get_input_files(self, obj):
        if not obj.depends_on_id:
            return []
        subs = obj.depends_on.file_submissions.filter(status='approved', deleted=False).order_by('-created_at')
        return [
            {
                'id': s.id,
                'filename': s.original_filename,
                'size_bytes': s.size_bytes,
                'uploader': display_name(s.uploader),
                'delivery': s.delivery,
                'handover_media': s.handover_media,
                'handover_to_name': display_name(s.handover_to) if s.handover_to else None,
                'handover_at': s.handover_at,
            }
            for s in subs
        ]

    def get_unread_messages(self, obj):
        request = self.context.get('request')
        return unread_count(obj, request.user) if request else 0

    def get_is_overdue(self, obj):
        from django.utils import timezone

        if obj.status == 'overdue':
            return True
        return bool(obj.due_date and obj.due_date < timezone.now() and obj.status in ('not_started', 'in_progress'))

    def validate(self, data):
        item = data.get('content_item')
        project = data.get('project', getattr(self.instance, 'project', None))
        if item and project and item.project_id != project.id:
            raise serializers.ValidationError(_('The content item does not belong to the selected project.'))
        return data


class SubmissionRecordSerializer(serializers.ModelSerializer):
    submitted_by_name = serializers.SerializerMethodField()

    class Meta:
        model = SubmissionRecord
        fields = '__all__'
        read_only_fields = ['submitted_by']

    def get_submitted_by_name(self, obj):
        return display_name(obj.submitted_by)

    def validate(self, data):
        if not data.get('submission_note'):
            raise serializers.ValidationError(_('The submission note cannot be empty.'))
        return data


class RevisionSerializer(serializers.ModelSerializer):
    requested_by_name = serializers.SerializerMethodField()
    assigned_to_name = serializers.SerializerMethodField()

    class Meta:
        model = Revision
        fields = '__all__'
        read_only_fields = ['requested_by']

    def get_requested_by_name(self, obj):
        return display_name(obj.requested_by)

    def get_assigned_to_name(self, obj):
        return display_name(obj.assigned_to)


class CommentSerializer(serializers.ModelSerializer):
    author_name = serializers.SerializerMethodField()
    author_role = serializers.CharField(source='author.role', read_only=True)

    class Meta:
        model = Comment
        fields = '__all__'
        read_only_fields = ['author']

    def get_author_name(self, obj):
        return display_name(obj.author)


class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = '__all__'
        read_only_fields = ['recipient_user', 'title', 'message', 'type', 'related_entity_type', 'related_entity_id']


class ActivityLogSerializer(serializers.ModelSerializer):
    user_name = serializers.SerializerMethodField()

    class Meta:
        model = ActivityLog
        fields = '__all__'

    def get_user_name(self, obj):
        return display_name(obj.user)


class PublishRecordSerializer(serializers.ModelSerializer):
    class Meta:
        model = PublishRecord
        fields = '__all__'


class OrderMessageSerializer(serializers.ModelSerializer):
    sender_name = serializers.SerializerMethodField()
    sender_role = serializers.CharField(source='sender.role', read_only=True, default=None)
    attachment = serializers.SerializerMethodField()

    class Meta:
        from .models import OrderMessage

        model = OrderMessage
        fields = ['id', 'task', 'sender', 'sender_name', 'sender_role', 'body', 'attachment', 'created_at']
        read_only_fields = ['task', 'sender']

    def get_sender_name(self, obj):
        return display_name(obj.sender)

    def get_attachment(self, obj):
        a = obj.attachment
        if a is None:
            return None
        data = {
            'id': a.id,
            'filename': a.filename,
            'content_type': a.content_type,
            'size_bytes': a.size_bytes,
            'deleted': a.deleted,
            'view_url': None,
            'download_url': None,
        }
        if not a.deleted:
            from . import video_storage

            try:
                data['view_url'] = video_storage.file_url(a.object_key, a.content_type, a.filename)
                data['download_url'] = video_storage.file_url(a.object_key, a.content_type, a.filename, download=True)
            except Exception:
                pass
        return data
