import django.contrib.auth.models
import django.contrib.auth.validators
import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ('auth', '0012_alter_user_first_name_max_length'),
    ]

    operations = [
        migrations.CreateModel(
            name='Client',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('client_name', models.CharField(max_length=255)),
                ('brand_name', models.CharField(blank=True, max_length=255)),
                ('contact_person', models.CharField(max_length=255)),
                ('phone', models.CharField(blank=True, max_length=20)),
                ('email', models.EmailField(blank=True, max_length=254)),
                ('niche', models.CharField(blank=True, max_length=100)),
                ('target_audience_notes', models.TextField(blank=True)),
                ('social_links', models.JSONField(blank=True, default=dict)),
                ('brand_notes', models.TextField(blank=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
        ),
        migrations.CreateModel(
            name='User',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('password', models.CharField(max_length=128, verbose_name='password')),
                ('last_login', models.DateTimeField(blank=True, null=True, verbose_name='last login')),
                (
                    'is_superuser',
                    models.BooleanField(
                        default=False,
                        help_text='Designates that this user has all permissions without explicitly assigning them.',
                        verbose_name='superuser status',
                    ),
                ),
                (
                    'username',
                    models.CharField(
                        error_messages={'unique': 'A user with that username already exists.'},
                        help_text='Required. 150 characters or fewer. Letters, digits and @/./+/-/_ only.',
                        max_length=150,
                        unique=True,
                        validators=[django.contrib.auth.validators.UnicodeUsernameValidator()],
                        verbose_name='username',
                    ),
                ),
                ('first_name', models.CharField(blank=True, max_length=150, verbose_name='first name')),
                ('last_name', models.CharField(blank=True, max_length=150, verbose_name='last name')),
                ('email', models.EmailField(blank=True, max_length=254, verbose_name='email address')),
                (
                    'is_staff',
                    models.BooleanField(
                        default=False,
                        help_text='Designates whether the user can log into this admin site.',
                        verbose_name='staff status',
                    ),
                ),
                (
                    'is_active',
                    models.BooleanField(
                        default=True,
                        help_text='Designates whether this user should be treated as active. Unselect this instead of deleting accounts.',
                        verbose_name='active',
                    ),
                ),
                ('date_joined', models.DateTimeField(default=django.utils.timezone.now, verbose_name='date joined')),
                ('phone', models.CharField(blank=True, max_length=20)),
                (
                    'role',
                    models.CharField(
                        choices=[
                            ('OWNER', 'Owner / Admin'),
                            ('PROJECT_MANAGER', 'Project Manager'),
                            ('VIDEOGRAPHER', 'Videographer'),
                            ('EDITOR', 'Video Editor'),
                        ],
                        default='OWNER',
                        max_length=20,
                    ),
                ),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                (
                    'groups',
                    models.ManyToManyField(
                        blank=True,
                        help_text='The groups this user belongs to. A user will get all permissions granted to each of their groups.',
                        related_name='user_set',
                        related_query_name='user',
                        to='auth.group',
                        verbose_name='groups',
                    ),
                ),
                (
                    'user_permissions',
                    models.ManyToManyField(
                        blank=True,
                        help_text='Specific permissions for this user.',
                        related_name='user_set',
                        related_query_name='user',
                        to='auth.permission',
                        verbose_name='user permissions',
                    ),
                ),
            ],
            options={
                'verbose_name': 'user',
                'verbose_name_plural': 'users',
                'abstract': False,
            },
            managers=[
                ('objects', django.contrib.auth.models.UserManager()),
            ],
        ),
        migrations.CreateModel(
            name='ActivityLog',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('action_type', models.CharField(max_length=100)),
                ('entity_type', models.CharField(max_length=50)),
                ('entity_id', models.IntegerField()),
                ('details_json', models.JSONField(default=dict)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                (
                    'user',
                    models.ForeignKey(
                        null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL
                    ),
                ),
            ],
        ),
        migrations.CreateModel(
            name='Comment',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('entity_type', models.CharField(max_length=50)),
                ('entity_id', models.IntegerField()),
                ('message', models.TextField()),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('author', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.CreateModel(
            name='Notification',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(max_length=255)),
                ('message', models.TextField()),
                ('type', models.CharField(max_length=50)),
                ('is_read', models.BooleanField(default=False)),
                ('related_entity_type', models.CharField(blank=True, max_length=50, null=True)),
                ('related_entity_id', models.IntegerField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                (
                    'recipient_user',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='notifications',
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
        ),
        migrations.CreateModel(
            name='Project',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=255)),
                ('start_date', models.DateField(blank=True, null=True)),
                ('end_date', models.DateField(blank=True, null=True)),
                ('service_fee', models.DecimalField(blank=True, decimal_places=2, max_digits=10, null=True)),
                ('goals', models.TextField(blank=True)),
                ('target_platforms', models.JSONField(blank=True, default=list)),
                ('deliverables_summary', models.TextField(blank=True)),
                (
                    'status',
                    models.CharField(
                        choices=[
                            ('draft', 'Draft'),
                            ('active', 'Active'),
                            ('on_hold', 'On Hold'),
                            ('completed', 'Completed'),
                            ('archived', 'Archived'),
                            ('cancelled', 'Cancelled'),
                        ],
                        default='draft',
                        max_length=20,
                    ),
                ),
                ('notes', models.TextField(blank=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                (
                    'client',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE, related_name='projects', to='api.client'
                    ),
                ),
                (
                    'owner',
                    models.ForeignKey(
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name='owned_projects',
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    'project_manager',
                    models.ForeignKey(
                        limit_choices_to={'role': 'PROJECT_MANAGER'},
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name='managed_projects',
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
        ),
        migrations.CreateModel(
            name='Contract',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('contract_number', models.CharField(max_length=100, unique=True)),
                ('template_name', models.CharField(blank=True, max_length=255)),
                ('generated_pdf_path_or_reference', models.CharField(blank=True, max_length=500)),
                ('terms_and_conditions', models.TextField(blank=True)),
                ('signed_contract_path_or_reference', models.CharField(blank=True, max_length=500)),
                (
                    'status',
                    models.CharField(
                        choices=[
                            ('draft', 'Draft'),
                            ('generated', 'Generated'),
                            ('sent', 'Sent'),
                            ('signed', 'Signed'),
                            ('uploaded', 'Uploaded'),
                        ],
                        default='draft',
                        max_length=20,
                    ),
                ),
                ('issued_date', models.DateField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                (
                    'uploaded_by',
                    models.ForeignKey(
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name='uploaded_contracts',
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    'project',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE, related_name='contracts', to='api.project'
                    ),
                ),
            ],
        ),
        migrations.CreateModel(
            name='ContentItem',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(max_length=255)),
                ('content_type', models.CharField(max_length=100)),
                ('platform', models.CharField(max_length=100)),
                ('objective', models.TextField(blank=True)),
                ('script_scenario', models.TextField(blank=True)),
                ('target_publish_date', models.DateTimeField(blank=True, null=True)),
                (
                    'status',
                    models.CharField(
                        choices=[
                            ('planned', 'Planned'),
                            ('scripting', 'Scripting'),
                            ('ready_for_shooting', 'Ready for Shooting'),
                            ('shooting', 'Shooting'),
                            ('ready_for_editing', 'Ready for Editing'),
                            ('editing', 'Editing'),
                            ('under_review', 'Under Review'),
                            ('revision_requested', 'Revision Requested'),
                            ('approved', 'Approved'),
                            ('published', 'Published'),
                            ('completed', 'Completed'),
                        ],
                        default='planned',
                        max_length=30,
                    ),
                ),
                ('revision_count', models.IntegerField(default=0)),
                ('publish_url', models.URLField(blank=True)),
                ('notes', models.TextField(blank=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                (
                    'assigned_editor',
                    models.ForeignKey(
                        blank=True,
                        limit_choices_to={'role': 'EDITOR'},
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name='assigned_edits',
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    'assigned_videographer',
                    models.ForeignKey(
                        blank=True,
                        limit_choices_to={'role': 'VIDEOGRAPHER'},
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name='assigned_shoots',
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    'created_by',
                    models.ForeignKey(
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name='created_content_items',
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    'project',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE, related_name='content_items', to='api.project'
                    ),
                ),
            ],
        ),
        migrations.CreateModel(
            name='PublishRecord',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('platform', models.CharField(max_length=100)),
                ('publish_datetime', models.DateTimeField()),
                ('post_url', models.URLField(blank=True)),
                ('caption_notes', models.TextField(blank=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                (
                    'content_item',
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE, related_name='publish_record', to='api.contentitem'
                    ),
                ),
                (
                    'published_by',
                    models.ForeignKey(
                        null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL
                    ),
                ),
            ],
        ),
        migrations.CreateModel(
            name='Task',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(max_length=255)),
                ('description', models.TextField(blank=True)),
                ('task_type', models.CharField(max_length=50)),
                ('due_date', models.DateTimeField(blank=True, null=True)),
                ('priority', models.CharField(default='Medium', max_length=20)),
                (
                    'status',
                    models.CharField(
                        choices=[
                            ('not_started', 'Not Started'),
                            ('in_progress', 'In Progress'),
                            ('waiting_for_review', 'Waiting for Review'),
                            ('completed', 'Completed'),
                            ('overdue', 'Overdue'),
                            ('rejected', 'Rejected'),
                            ('cancelled', 'Cancelled'),
                        ],
                        default='not_started',
                        max_length=30,
                    ),
                ),
                ('completion_note', models.TextField(blank=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                (
                    'assigned_by',
                    models.ForeignKey(
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name='created_tasks',
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    'assigned_to',
                    models.ForeignKey(
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name='assigned_tasks',
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    'content_item',
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name='tasks',
                        to='api.contentitem',
                    ),
                ),
                (
                    'project',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE, related_name='tasks', to='api.project'
                    ),
                ),
            ],
        ),
        migrations.CreateModel(
            name='SubmissionRecord',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('submission_type', models.CharField(max_length=50)),
                ('messenger_platform', models.CharField(max_length=50)),
                ('submission_note', models.TextField()),
                ('external_link', models.URLField(blank=True, null=True)),
                ('version_label', models.CharField(blank=True, max_length=50)),
                ('submitted_at', models.DateTimeField(auto_now_add=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                (
                    'content_item',
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='submissions',
                        to='api.contentitem',
                    ),
                ),
                (
                    'submitted_by',
                    models.ForeignKey(
                        null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL
                    ),
                ),
                (
                    'task',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE, related_name='submissions', to='api.task'
                    ),
                ),
            ],
        ),
        migrations.CreateModel(
            name='Revision',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('revision_number', models.IntegerField()),
                ('reason', models.TextField()),
                ('comments', models.TextField(blank=True)),
                ('correction_deadline', models.DateTimeField(blank=True, null=True)),
                (
                    'status',
                    models.CharField(
                        choices=[
                            ('requested', 'Requested'),
                            ('in_progress', 'In Progress'),
                            ('resubmitted', 'Resubmitted'),
                            ('approved', 'Approved'),
                            ('closed', 'Closed'),
                        ],
                        default='requested',
                        max_length=20,
                    ),
                ),
                ('resolved_at', models.DateTimeField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                (
                    'assigned_to',
                    models.ForeignKey(
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name='assigned_revisions',
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    'content_item',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE, related_name='revisions', to='api.contentitem'
                    ),
                ),
                (
                    'requested_by',
                    models.ForeignKey(
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name='requested_revisions',
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    'task',
                    models.ForeignKey(
                        null=True, on_delete=django.db.models.deletion.CASCADE, related_name='revisions', to='api.task'
                    ),
                ),
            ],
        ),
        migrations.CreateModel(
            name='TaskChecklistItem',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('text', models.CharField(max_length=255)),
                ('is_completed', models.BooleanField(default=False)),
                ('order_index', models.IntegerField(default=0)),
                (
                    'task',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE, related_name='checklist_items', to='api.task'
                    ),
                ),
            ],
        ),
        migrations.CreateModel(
            name='Template',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=255)),
                ('type', models.CharField(max_length=50)),
                ('content_json_or_text', models.TextField()),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                (
                    'created_by',
                    models.ForeignKey(
                        null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL
                    ),
                ),
            ],
        ),
        migrations.CreateModel(
            name='Strategy',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(max_length=255)),
                ('business_goal', models.TextField(blank=True)),
                ('audience', models.TextField(blank=True)),
                ('content_pillars', models.JSONField(blank=True, default=list)),
                ('posting_frequency', models.CharField(blank=True, max_length=255)),
                ('platforms', models.JSONField(blank=True, default=list)),
                ('posting_times', models.JSONField(blank=True, default=list)),
                ('kpi_notes', models.TextField(blank=True)),
                ('notes', models.TextField(blank=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                (
                    'created_by',
                    models.ForeignKey(
                        null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL
                    ),
                ),
                (
                    'project',
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE, related_name='strategy', to='api.project'
                    ),
                ),
                (
                    'template_used',
                    models.ForeignKey(
                        blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='api.template'
                    ),
                ),
            ],
        ),
    ]
