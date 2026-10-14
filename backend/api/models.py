from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy, gettext_noop


class UserRole(models.TextChoices):
    OWNER = 'OWNER', gettext_lazy('Owner / Admin')
    PROJECT_MANAGER = 'PROJECT_MANAGER', gettext_lazy('Project Manager')
    VIDEOGRAPHER = 'VIDEOGRAPHER', gettext_lazy('Videographer')
    EDITOR = 'EDITOR', gettext_lazy('Video Editor')


class User(AbstractUser):
    phone = models.CharField(max_length=20, blank=True)
    role = models.CharField(max_length=20, choices=UserRole.choices, default=UserRole.OWNER)
    avatar_url = models.TextField(blank=True)
    language = models.CharField(
        max_length=5, choices=[('en', gettext_lazy('English')), ('ru', 'Русский')], default='en'
    )
    telegram_chat_id = models.CharField(max_length=32, blank=True)
    telegram_enabled = models.BooleanField(default=True)
    telegram_link_code = models.CharField(max_length=64, blank=True, db_index=True)
    telegram_link_expires = models.DateTimeField(null=True, blank=True)
    two_factor_enabled = models.BooleanField(default=False)
    login_code_hash = models.CharField(max_length=64, blank=True)
    login_code_expires = models.DateTimeField(null=True, blank=True)
    login_code_tries = models.PositiveSmallIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.username


class Client(models.Model):
    client_name = models.CharField(max_length=255)
    brand_name = models.CharField(max_length=255, blank=True)
    contact_person = models.CharField(max_length=255)
    phone = models.CharField(max_length=20, blank=True)
    email = models.EmailField(blank=True)
    niche = models.CharField(max_length=100, blank=True)
    target_audience_notes = models.TextField(blank=True)
    social_links = models.JSONField(default=dict, blank=True)
    brand_notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.client_name


class ProjectStatus(models.TextChoices):
    DRAFT = 'draft', gettext_lazy('Draft')
    ACTIVE = 'active', gettext_lazy('Active')
    ON_HOLD = 'on_hold', gettext_lazy('On Hold')
    COMPLETED = 'completed', gettext_lazy('Completed')
    ARCHIVED = 'archived', gettext_lazy('Archived')
    CANCELLED = 'cancelled', gettext_lazy('Cancelled')


class Project(models.Model):
    client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name='projects')
    name = models.CharField(max_length=255)
    owner = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='owned_projects')
    project_manager = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='managed_projects',
        limit_choices_to={'role__in': [UserRole.OWNER, UserRole.PROJECT_MANAGER]},
    )
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    service_fee = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    goals = models.TextField(blank=True)
    target_platforms = models.JSONField(default=list, blank=True)
    deliverables_summary = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=ProjectStatus.choices, default=ProjectStatus.DRAFT)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name


class ContractStatus(models.TextChoices):
    DRAFT = 'draft', gettext_lazy('Draft')
    GENERATED = 'generated', gettext_lazy('Generated')
    SENT = 'sent', gettext_lazy('Sent')
    SIGNED = 'signed', gettext_lazy('Signed')
    UPLOADED = 'uploaded', gettext_lazy('Uploaded')


class Contract(models.Model):
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='contracts')
    contract_number = models.CharField(max_length=100, unique=True)
    template_name = models.CharField(max_length=255, blank=True)
    generated_pdf_path_or_reference = models.CharField(max_length=500, blank=True)
    terms_and_conditions = models.TextField(blank=True)
    signed_contract_path_or_reference = models.CharField(max_length=500, blank=True)
    status = models.CharField(max_length=20, choices=ContractStatus.choices, default=ContractStatus.DRAFT)
    issued_date = models.DateField(null=True, blank=True)
    uploaded_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='uploaded_contracts')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class Template(models.Model):
    name = models.CharField(max_length=255)
    type = models.CharField(max_length=50)
    content_json_or_text = models.TextField()
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class ContentItemStatus(models.TextChoices):
    PLANNED = 'planned', gettext_lazy('Planned')
    SCRIPTING = 'scripting', gettext_lazy('Scripting')
    READY_FOR_SHOOTING = 'ready_for_shooting', gettext_lazy('Ready for Shooting')
    SHOOTING = 'shooting', gettext_lazy('Shooting')
    READY_FOR_EDITING = 'ready_for_editing', gettext_lazy('Ready for Editing')
    EDITING = 'editing', gettext_lazy('Editing')
    UNDER_REVIEW = 'under_review', gettext_lazy('Under Review')
    REVISION_REQUESTED = 'revision_requested', gettext_lazy('Revision Requested')
    APPROVED = 'approved', gettext_lazy('Approved')
    PUBLISHED = 'published', gettext_lazy('Published')
    COMPLETED = 'completed', gettext_lazy('Completed')


class ContentItem(models.Model):
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='content_items')
    title = models.CharField(max_length=255)
    content_type = models.CharField(max_length=100)
    platform = models.CharField(max_length=100)
    objective = models.TextField(blank=True)
    script_scenario = models.TextField(blank=True)
    target_publish_date = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=30, choices=ContentItemStatus.choices, default=ContentItemStatus.PLANNED)
    assigned_videographer = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='assigned_shoots',
        limit_choices_to={'role': UserRole.VIDEOGRAPHER},
    )
    assigned_editor = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='assigned_edits',
        limit_choices_to={'role': UserRole.EDITOR},
    )
    revision_count = models.IntegerField(default=0)
    publish_url = models.URLField(blank=True)
    notes = models.TextField(blank=True)
    shooting_location = models.CharField(max_length=500, blank=True)
    checklist = models.JSONField(default=list, blank=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='created_content_items')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    status_changed_at = models.DateTimeField(null=True, blank=True, db_index=True)

    @classmethod
    def from_db(cls, db, field_names, values):
        obj = super().from_db(db, field_names, values)
        obj._loaded_status = obj.__dict__.get('status')
        return obj

    def save(self, *args, **kwargs):
        moved = self._state.adding or self.status != getattr(self, '_loaded_status', self.status)
        if moved:
            self.status_changed_at = timezone.now()
            if kwargs.get('update_fields') is not None:
                kwargs['update_fields'] = {*kwargs['update_fields'], 'status_changed_at'}
        super().save(*args, **kwargs)
        if moved:
            ContentStatusChange.objects.create(content_item=self, status=self.status, changed_at=self.status_changed_at)
            self._loaded_status = self.status

    @classmethod
    def set_status(cls, pk, status):
        now = timezone.now()
        if cls.objects.filter(pk=pk).exclude(status=status).update(status=status, status_changed_at=now):
            ContentStatusChange.objects.create(content_item_id=pk, status=status, changed_at=now)


class ContentStatusChange(models.Model):
    content_item = models.ForeignKey(ContentItem, on_delete=models.CASCADE, related_name='status_changes')
    status = models.CharField(max_length=30, choices=ContentItemStatus.choices)
    changed_at = models.DateTimeField(db_index=True)

    class Meta:
        ordering = ['changed_at']


class TaskStatus(models.TextChoices):
    NOT_STARTED = 'not_started', gettext_lazy('Not Started')
    IN_PROGRESS = 'in_progress', gettext_lazy('In Progress')
    WAITING_FOR_REVIEW = 'waiting_for_review', gettext_lazy('Waiting for Review')
    COMPLETED = 'completed', gettext_lazy('Completed')
    OVERDUE = 'overdue', gettext_lazy('Overdue')
    REJECTED = 'rejected', gettext_lazy('Rejected')
    CANCELLED = 'cancelled', gettext_lazy('Cancelled')


class TaskStage(models.TextChoices):
    SHOOT = 'shoot', gettext_lazy('Shoot')
    EDIT = 'edit', gettext_lazy('Edit')
    OTHER = 'other', gettext_lazy('Other')


class Task(models.Model):
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='tasks')
    stage = models.CharField(max_length=10, choices=TaskStage.choices, default=TaskStage.OTHER)
    depends_on = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True, related_name='dependents')
    content_item = models.ForeignKey(
        ContentItem, on_delete=models.SET_NULL, null=True, blank=True, related_name='tasks'
    )
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    task_type = models.CharField(max_length=50)
    assigned_to = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='assigned_tasks')
    assigned_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='created_tasks')
    due_date = models.DateTimeField(null=True, blank=True)
    priority = models.CharField(max_length=20, default='Medium')
    status = models.CharField(max_length=30, choices=TaskStatus.choices, default=TaskStatus.NOT_STARTED)
    completion_note = models.TextField(blank=True)
    completed_at = models.DateTimeField(null=True, blank=True, db_index=True)
    reminded_due_soon_at = models.DateTimeField(null=True, blank=True)
    reminded_overdue_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


PRIORITY_LABELS = [gettext_noop('Low'), gettext_noop('Medium'), gettext_noop('High'), gettext_noop('Urgent')]


class TaskChecklistItem(models.Model):
    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name='checklist_items')
    text = models.CharField(max_length=255)
    is_completed = models.BooleanField(default=False)
    order_index = models.IntegerField(default=0)


class SubmissionRecord(models.Model):
    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name='submissions', null=True, blank=True)
    content_item = models.ForeignKey(
        ContentItem, on_delete=models.CASCADE, related_name='submissions', null=True, blank=True
    )
    submitted_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    submission_type = models.CharField(max_length=50)
    messenger_platform = models.CharField(max_length=50)
    submission_note = models.TextField()
    external_link = models.URLField(blank=True, null=True)
    version_label = models.CharField(max_length=50, blank=True)
    submitted_at = models.DateTimeField(auto_now_add=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class RevisionStatus(models.TextChoices):
    REQUESTED = 'requested', gettext_lazy('Requested')
    IN_PROGRESS = 'in_progress', gettext_lazy('In Progress')
    RESUBMITTED = 'resubmitted', gettext_lazy('Resubmitted')
    APPROVED = 'approved', gettext_lazy('Approved')
    CLOSED = 'closed', gettext_lazy('Closed')


class Revision(models.Model):
    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name='revisions', null=True)
    content_item = models.ForeignKey(ContentItem, on_delete=models.CASCADE, related_name='revisions')
    revision_number = models.IntegerField()
    requested_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='requested_revisions')
    assigned_to = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='assigned_revisions')
    reason = models.TextField()
    comments = models.TextField(blank=True)
    correction_deadline = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=RevisionStatus.choices, default=RevisionStatus.REQUESTED)
    resolved_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class Comment(models.Model):
    entity_type = models.CharField(max_length=50)
    entity_id = models.IntegerField()
    author = models.ForeignKey(User, on_delete=models.CASCADE)
    message = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class Notification(models.Model):
    recipient_user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
    title = models.CharField(max_length=255)
    message = models.TextField()
    type = models.CharField(max_length=50)
    is_read = models.BooleanField(default=False)
    related_entity_type = models.CharField(max_length=50, blank=True, null=True)
    related_entity_id = models.IntegerField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)


class ActivityLog(models.Model):
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    action_type = models.CharField(max_length=100)
    entity_type = models.CharField(max_length=50)
    entity_id = models.IntegerField()
    details_json = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)


class PublishRecord(models.Model):
    content_item = models.OneToOneField(ContentItem, on_delete=models.CASCADE, related_name='publish_record')
    platform = models.CharField(max_length=100)
    publish_datetime = models.DateTimeField()
    post_url = models.URLField(blank=True)
    caption_notes = models.TextField(blank=True)
    published_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


HANDOVER_MEDIA = [
    ('hard_drive', gettext_lazy('Hard drive')),
    ('ssd', gettext_lazy('SSD')),
    ('memory_card', gettext_lazy('Memory card')),
    ('usb', gettext_lazy('USB flash drive')),
    ('other', gettext_lazy('Other')),
]


class VideoStatus(models.TextChoices):
    UPLOADING = 'uploading', gettext_lazy('Uploading')
    PENDING = 'pending', gettext_lazy('Pending Review')
    APPROVED = 'approved', gettext_lazy('Approved')
    REJECTED = 'rejected', gettext_lazy('Rejected')


class VideoSubmission(models.Model):
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='video_submissions')
    content_item = models.ForeignKey(
        ContentItem, on_delete=models.SET_NULL, null=True, blank=True, related_name='video_submissions'
    )
    version = models.PositiveIntegerField(null=True, blank=True)
    uploader = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='video_uploads')
    reviewer = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='video_reviews')
    object_key = models.CharField(max_length=500, unique=True)
    upload_id = models.CharField(max_length=1024, blank=True)
    size_bytes = models.BigIntegerField()
    original_filename = models.CharField(max_length=255)
    content_type = models.CharField(max_length=127, default='application/octet-stream')
    task = models.ForeignKey(Task, on_delete=models.SET_NULL, null=True, blank=True, related_name='file_submissions')
    editor_note = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=VideoStatus.choices, default=VideoStatus.UPLOADING)
    review_comment = models.TextField(blank=True)
    deleted = models.BooleanField(default=False)
    stale_flagged_at = models.DateTimeField(null=True, blank=True)
    delivery = models.CharField(
        max_length=12,
        default='upload',
        choices=[('upload', gettext_lazy('Uploaded')), ('in_person', gettext_lazy('Handed over in person'))],
    )
    handover_media = models.CharField(max_length=20, blank=True, choices=HANDOVER_MEDIA)
    handover_to = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name='received_handovers'
    )
    handover_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        indexes = [models.Index(fields=['deleted', 'status', 'reviewed_at'], name='video_eviction_idx')]
        ordering = ['-created_at']


class VideoComment(models.Model):
    submission = models.ForeignKey(VideoSubmission, on_delete=models.CASCADE, related_name='comments')
    author = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    timestamp_seconds = models.FloatField(null=True, blank=True)
    body = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']


class VideoStorageLock(models.Model):
    id = models.PositiveSmallIntegerField(primary_key=True, default=1)


class OrderMessage(models.Model):
    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name='messages')
    sender = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    body = models.TextField(blank=True)
    attachment = models.OneToOneField(
        'ChatAttachment', on_delete=models.SET_NULL, null=True, blank=True, related_name='message'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']
        indexes = [models.Index(fields=['task', 'created_at'])]


class OrderChatRead(models.Model):
    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name='chat_reads')
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    last_read_at = models.DateTimeField()

    class Meta:
        unique_together = [('task', 'user')]


class ChatAttachment(models.Model):
    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name='chat_attachments')
    uploader = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    object_key = models.CharField(max_length=500, unique=True)
    filename = models.CharField(max_length=255)
    content_type = models.CharField(max_length=127, default='application/octet-stream')
    size_bytes = models.BigIntegerField()
    ready = models.BooleanField(default=False)
    deleted = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)


class WorkspacePage(models.Model):
    project = models.ForeignKey(Project, on_delete=models.CASCADE, null=True, blank=True, related_name='pages')
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='workspace_pages')
    title = models.CharField(max_length=255, default='Untitled')
    icon = models.CharField(max_length=16, blank=True, default='📄')
    body = models.TextField(blank=True)
    updated_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='+')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-updated_at']


class WorkspaceTodo(models.Model):
    PRIORITIES = [(1, 'P1'), (2, 'P2'), (3, 'P3'), (4, 'P4')]
    project = models.ForeignKey(Project, on_delete=models.CASCADE, null=True, blank=True, related_name='todos')
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='created_todos')
    assignee = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='assigned_todos')
    title = models.CharField(max_length=500)
    notes = models.TextField(blank=True)
    section = models.CharField(max_length=100, blank=True)
    due_date = models.DateField(null=True, blank=True)
    priority = models.PositiveSmallIntegerField(choices=PRIORITIES, default=4)
    completed = models.BooleanField(default=False)
    completed_at = models.DateTimeField(null=True, blank=True)
    order_index = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['completed', 'order_index', 'id']


class CalendarEvent(models.Model):
    project = models.ForeignKey(Project, on_delete=models.CASCADE, null=True, blank=True, related_name='events')
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='created_events')
    attendees = models.ManyToManyField(User, blank=True, related_name='calendar_events')
    title = models.CharField(max_length=255)
    notes = models.TextField(blank=True)
    location = models.CharField(max_length=255, blank=True)
    start = models.DateTimeField()
    end = models.DateTimeField()
    all_day = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['start']


class FinanceAccount(models.Model):
    KINDS = [
        ('bank', gettext_lazy('Bank')),
        ('cash', gettext_lazy('Cash')),
        ('card', gettext_lazy('Card')),
        ('other', gettext_lazy('Other')),
    ]
    name = models.CharField(max_length=100)
    kind = models.CharField(max_length=10, choices=KINDS, default='bank')
    opening_balance = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    archived = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['archived', 'name']


class FinanceCategory(models.Model):
    GROUPS = [
        ('revenue', gettext_lazy('Revenue')),
        ('other_income', gettext_lazy('Other income')),
        ('direct', gettext_lazy('Direct costs')),
        ('payroll', gettext_lazy('Payroll')),
        ('operating', gettext_lazy('Operating expenses')),
        ('tax', gettext_lazy('Taxes')),
    ]
    INCOME_GROUPS = ('revenue', 'other_income')
    name = models.CharField(max_length=100)
    group = models.CharField(max_length=20, choices=GROUPS)
    monthly_budget = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    archived = models.BooleanField(default=False)

    class Meta:
        ordering = ['group', 'name']

    @property
    def type(self):
        return 'income' if self.group in self.INCOME_GROUPS else 'expense'


class TxType(models.TextChoices):
    INCOME = 'income', gettext_lazy('Income')
    EXPENSE = 'expense', gettext_lazy('Expense')
    TRANSFER = 'transfer', gettext_lazy('Transfer')


class RecurringTransaction(models.Model):
    FREQUENCIES = [
        ('weekly', gettext_lazy('Weekly')),
        ('monthly', gettext_lazy('Monthly')),
        ('quarterly', gettext_lazy('Quarterly')),
        ('yearly', gettext_lazy('Yearly')),
    ]
    type = models.CharField(max_length=10, choices=[c for c in TxType.choices if c[0] != 'transfer'])
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    account = models.ForeignKey(FinanceAccount, on_delete=models.PROTECT, related_name='+')
    category = models.ForeignKey(FinanceCategory, on_delete=models.PROTECT, related_name='+')
    project = models.ForeignKey(Project, on_delete=models.SET_NULL, null=True, blank=True, related_name='+')
    counterparty = models.CharField(max_length=255, blank=True)
    description = models.CharField(max_length=255, blank=True)
    frequency = models.CharField(max_length=10, choices=FREQUENCIES, default='monthly')
    next_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['next_date']


class Transaction(models.Model):
    type = models.CharField(max_length=10, choices=TxType.choices)
    date = models.DateField()
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    account = models.ForeignKey(FinanceAccount, on_delete=models.PROTECT, related_name='transactions')
    to_account = models.ForeignKey(
        FinanceAccount, on_delete=models.PROTECT, null=True, blank=True, related_name='transfers_in'
    )
    category = models.ForeignKey(
        FinanceCategory, on_delete=models.PROTECT, null=True, blank=True, related_name='transactions'
    )
    project = models.ForeignKey(Project, on_delete=models.SET_NULL, null=True, blank=True, related_name='transactions')
    client = models.ForeignKey(Client, on_delete=models.SET_NULL, null=True, blank=True, related_name='transactions')
    counterparty = models.CharField(max_length=255, blank=True)
    description = models.CharField(max_length=255, blank=True)
    reference = models.CharField(max_length=100, blank=True)
    status = models.CharField(
        max_length=10, choices=[('paid', gettext_lazy('Paid')), ('pending', gettext_lazy('Pending'))], default='paid'
    )
    paid_date = models.DateField(null=True, blank=True)
    due_date = models.DateField(null=True, blank=True)
    recurring = models.ForeignKey(
        RecurringTransaction, on_delete=models.SET_NULL, null=True, blank=True, related_name='occurrences'
    )
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='+')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-date', '-id']
        indexes = [models.Index(fields=['type', 'date']), models.Index(fields=['status', 'due_date'])]


class OAuthClient(models.Model):
    client_id = models.CharField(max_length=64, unique=True)
    name = models.CharField(max_length=200)
    redirect_uris = models.JSONField(default=list)
    created_at = models.DateTimeField(auto_now_add=True)


class AIAuthCode(models.Model):
    code_hash = models.CharField(max_length=64, unique=True)
    client = models.ForeignKey(OAuthClient, on_delete=models.CASCADE)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    redirect_uri = models.TextField()
    code_challenge = models.CharField(max_length=128)
    expires_at = models.DateTimeField()


class AIConnection(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='ai_connections')
    client = models.ForeignKey(OAuthClient, on_delete=models.CASCADE)
    access_hash = models.CharField(max_length=64, unique=True)
    access_expires = models.DateTimeField()
    refresh_hash = models.CharField(max_length=64, unique=True)
    refresh_expires = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)
    last_used_at = models.DateTimeField(null=True, blank=True)
    revoked = models.BooleanField(default=False)


class AIApproval(models.Model):
    PENDING, APPROVED, DENIED, USED = 'pending', 'approved', 'denied', 'used'
    connection = models.ForeignKey(AIConnection, on_delete=models.CASCADE, related_name='approvals')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='ai_approvals')
    kind = models.CharField(max_length=20)
    method = models.CharField(max_length=10)
    path = models.CharField(max_length=500)
    request_hash = models.CharField(max_length=64)
    summary = models.TextField()
    status = models.CharField(max_length=10, default=PENDING)
    created_at = models.DateTimeField(auto_now_add=True)
    decided_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']
