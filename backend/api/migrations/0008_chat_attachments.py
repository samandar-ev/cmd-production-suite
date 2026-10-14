import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('api', '0007_order_chat'),
    ]

    operations = [
        migrations.AlterField(
            model_name='ordermessage',
            name='body',
            field=models.TextField(blank=True),
        ),
        migrations.CreateModel(
            name='ChatAttachment',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('object_key', models.CharField(max_length=500, unique=True)),
                ('filename', models.CharField(max_length=255)),
                ('content_type', models.CharField(default='application/octet-stream', max_length=127)),
                ('size_bytes', models.BigIntegerField()),
                ('ready', models.BooleanField(default=False)),
                ('deleted', models.BooleanField(default=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                (
                    'task',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE, related_name='chat_attachments', to='api.task'
                    ),
                ),
                (
                    'uploader',
                    models.ForeignKey(
                        null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL
                    ),
                ),
            ],
        ),
        migrations.AddField(
            model_name='ordermessage',
            name='attachment',
            field=models.OneToOneField(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='message',
                to='api.chatattachment',
            ),
        ),
    ]
