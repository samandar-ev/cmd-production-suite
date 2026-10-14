import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('api', '0006_submission_any_file'),
    ]

    operations = [
        migrations.CreateModel(
            name='OrderChatRead',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('last_read_at', models.DateTimeField()),
                (
                    'task',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE, related_name='chat_reads', to='api.task'
                    ),
                ),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'unique_together': {('task', 'user')},
            },
        ),
        migrations.CreateModel(
            name='OrderMessage',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('body', models.TextField()),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                (
                    'sender',
                    models.ForeignKey(
                        null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL
                    ),
                ),
                (
                    'task',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE, related_name='messages', to='api.task'
                    ),
                ),
            ],
            options={
                'ordering': ['created_at'],
                'indexes': [models.Index(fields=['task', 'created_at'], name='api_orderme_task_id_2904b1_idx')],
            },
        ),
    ]
