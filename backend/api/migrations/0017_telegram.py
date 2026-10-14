from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('api', '0016_backfill_stage_times'),
    ]

    operations = [
        migrations.AddField(
            model_name='task',
            name='reminded_due_soon_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='task',
            name='reminded_overdue_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='user',
            name='telegram_chat_id',
            field=models.CharField(blank=True, max_length=32),
        ),
        migrations.AddField(
            model_name='user',
            name='telegram_enabled',
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name='user',
            name='telegram_link_code',
            field=models.CharField(blank=True, db_index=True, max_length=64),
        ),
        migrations.AddField(
            model_name='user',
            name='telegram_link_expires',
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
