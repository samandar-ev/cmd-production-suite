import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('api', '0008_chat_attachments'),
    ]

    operations = [
        migrations.AddField(
            model_name='task',
            name='depends_on',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='dependents',
                to='api.task',
            ),
        ),
        migrations.AddField(
            model_name='task',
            name='stage',
            field=models.CharField(
                choices=[('shoot', 'Shoot'), ('edit', 'Edit'), ('other', 'Other')], default='other', max_length=10
            ),
        ),
    ]
