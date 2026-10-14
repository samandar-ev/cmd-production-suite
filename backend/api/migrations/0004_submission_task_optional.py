import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('api', '0003_contentitem_checklist_contentitem_shooting_location'),
    ]

    operations = [
        migrations.AlterField(
            model_name='submissionrecord',
            name='task',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name='submissions',
                to='api.task',
            ),
        ),
    ]
