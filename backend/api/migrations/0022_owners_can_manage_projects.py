import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('api', '0021_handover'),
    ]

    operations = [
        migrations.AlterField(
            model_name='project',
            name='project_manager',
            field=models.ForeignKey(
                limit_choices_to={'role__in': ['OWNER', 'PROJECT_MANAGER']},
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='managed_projects',
                to=settings.AUTH_USER_MODEL,
            ),
        ),
    ]
