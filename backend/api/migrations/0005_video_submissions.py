import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


def create_lock_row(apps, schema_editor):
    apps.get_model('api', 'VideoStorageLock').objects.get_or_create(id=1)


class Migration(migrations.Migration):
    dependencies = [
        ('api', '0004_submission_task_optional'),
    ]

    operations = [
        migrations.CreateModel(
            name='VideoStorageLock',
            fields=[
                ('id', models.PositiveSmallIntegerField(default=1, primary_key=True, serialize=False)),
            ],
        ),
        migrations.CreateModel(
            name='VideoSubmission',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('version', models.PositiveIntegerField(blank=True, null=True)),
                ('object_key', models.CharField(max_length=500, unique=True)),
                ('upload_id', models.CharField(blank=True, max_length=1024)),
                ('size_bytes', models.BigIntegerField()),
                ('original_filename', models.CharField(max_length=255)),
                ('editor_note', models.TextField(blank=True)),
                (
                    'status',
                    models.CharField(
                        choices=[
                            ('uploading', 'Uploading'),
                            ('pending', 'Pending Review'),
                            ('approved', 'Approved'),
                            ('rejected', 'Rejected'),
                        ],
                        default='uploading',
                        max_length=20,
                    ),
                ),
                ('review_comment', models.TextField(blank=True)),
                ('deleted', models.BooleanField(default=False)),
                ('stale_flagged_at', models.DateTimeField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('reviewed_at', models.DateTimeField(blank=True, null=True)),
                (
                    'content_item',
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name='video_submissions',
                        to='api.contentitem',
                    ),
                ),
                (
                    'project',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE, related_name='video_submissions', to='api.project'
                    ),
                ),
                (
                    'reviewer',
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name='video_reviews',
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    'uploader',
                    models.ForeignKey(
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name='video_uploads',
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                'ordering': ['-created_at'],
            },
        ),
        migrations.CreateModel(
            name='VideoComment',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('timestamp_seconds', models.FloatField(blank=True, null=True)),
                ('body', models.TextField()),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                (
                    'author',
                    models.ForeignKey(
                        null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL
                    ),
                ),
                (
                    'submission',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE, related_name='comments', to='api.videosubmission'
                    ),
                ),
            ],
            options={
                'ordering': ['created_at'],
            },
        ),
        migrations.AddIndex(
            model_name='videosubmission',
            index=models.Index(fields=['deleted', 'status', 'reviewed_at'], name='video_eviction_idx'),
        ),
        migrations.RunPython(create_lock_row, migrations.RunPython.noop),
    ]
