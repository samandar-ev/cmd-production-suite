import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


def move_old_notes(apps, schema_editor):
    import json

    Project = apps.get_model('api', 'Project')
    Page = apps.get_model('api', 'WorkspacePage')
    Todo = apps.get_model('api', 'WorkspaceTodo')
    for p in Project.objects.exclude(notes=''):
        try:
            data = json.loads(p.notes) if p.notes.strip().startswith('{') else {'notes': p.notes, 'todos': []}
        except ValueError:
            data = {'notes': p.notes, 'todos': []}
        if (data.get('notes') or '').strip():
            Page.objects.create(project=p, created_by=p.owner, title='Notes', icon='📝', body=data['notes'])
        for i, t in enumerate(data.get('todos') or []):
            if (t.get('text') or '').strip():
                Todo.objects.create(
                    project=p,
                    created_by=p.owner,
                    title=t['text'][:500],
                    completed=bool(t.get('completed')),
                    order_index=i,
                )


class Migration(migrations.Migration):
    dependencies = [
        ('api', '0009_production_stages'),
    ]

    operations = [
        migrations.CreateModel(
            name='CalendarEvent',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(max_length=255)),
                ('notes', models.TextField(blank=True)),
                ('location', models.CharField(blank=True, max_length=255)),
                ('start', models.DateTimeField()),
                ('end', models.DateTimeField()),
                ('all_day', models.BooleanField(default=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                (
                    'attendees',
                    models.ManyToManyField(blank=True, related_name='calendar_events', to=settings.AUTH_USER_MODEL),
                ),
                (
                    'created_by',
                    models.ForeignKey(
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name='created_events',
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    'project',
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='events',
                        to='api.project',
                    ),
                ),
            ],
            options={
                'ordering': ['start'],
            },
        ),
        migrations.CreateModel(
            name='WorkspacePage',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(default='Untitled', max_length=255)),
                ('icon', models.CharField(blank=True, default='📄', max_length=16)),
                ('body', models.TextField(blank=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                (
                    'created_by',
                    models.ForeignKey(
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name='workspace_pages',
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    'project',
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='pages',
                        to='api.project',
                    ),
                ),
                (
                    'updated_by',
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name='+',
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                'ordering': ['-updated_at'],
            },
        ),
        migrations.CreateModel(
            name='WorkspaceTodo',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(max_length=500)),
                ('notes', models.TextField(blank=True)),
                ('section', models.CharField(blank=True, max_length=100)),
                ('due_date', models.DateField(blank=True, null=True)),
                (
                    'priority',
                    models.PositiveSmallIntegerField(choices=[(1, 'P1'), (2, 'P2'), (3, 'P3'), (4, 'P4')], default=4),
                ),
                ('completed', models.BooleanField(default=False)),
                ('completed_at', models.DateTimeField(blank=True, null=True)),
                ('order_index', models.IntegerField(default=0)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                (
                    'assignee',
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name='assigned_todos',
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    'created_by',
                    models.ForeignKey(
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name='created_todos',
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    'project',
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='todos',
                        to='api.project',
                    ),
                ),
            ],
            options={
                'ordering': ['completed', 'order_index', 'id'],
            },
        ),
        migrations.RunPython(move_old_notes, migrations.RunPython.noop),
    ]
