from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('api', '0002_user_avatar_url'),
    ]

    operations = [
        migrations.AddField(
            model_name='contentitem',
            name='checklist',
            field=models.JSONField(blank=True, default=list),
        ),
        migrations.AddField(
            model_name='contentitem',
            name='shooting_location',
            field=models.CharField(blank=True, max_length=500),
        ),
    ]
