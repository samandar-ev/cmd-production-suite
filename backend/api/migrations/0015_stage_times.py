import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('api', '0014_user_language'),
    ]

    operations = [
        migrations.AddField(
            model_name='contentitem',
            name='status_changed_at',
            field=models.DateTimeField(blank=True, db_index=True, null=True),
        ),
        migrations.AddField(
            model_name='task',
            name='completed_at',
            field=models.DateTimeField(blank=True, db_index=True, null=True),
        ),
        migrations.CreateModel(
            name='ContentStatusChange',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
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
                        max_length=30,
                    ),
                ),
                ('changed_at', models.DateTimeField(db_index=True)),
                (
                    'content_item',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE, related_name='status_changes', to='api.contentitem'
                    ),
                ),
            ],
            options={
                'ordering': ['changed_at'],
            },
        ),
    ]
