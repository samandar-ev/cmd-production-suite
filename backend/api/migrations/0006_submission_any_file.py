import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('api', '0005_video_submissions'),
    ]

    operations = [
        migrations.AddField(
            model_name='videosubmission',
            name='content_type',
            field=models.CharField(default='application/octet-stream', max_length=127),
        ),
        migrations.AddField(
            model_name='videosubmission',
            name='task',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='file_submissions',
                to='api.task',
            ),
        ),
    ]
