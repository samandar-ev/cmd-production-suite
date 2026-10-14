from django.db import migrations


def section(title, text):
    return f'## {title}\n{text.strip()}\n\n' if text and str(text).strip() else ''


def bullets(items):
    return '\n'.join(f'- {x}' for x in items or [] if str(x).strip())


def strategies_to_pages(apps, schema_editor):
    Strategy = apps.get_model('api', 'Strategy')
    WorkspacePage = apps.get_model('api', 'WorkspacePage')
    for s in Strategy.objects.all():
        body = '# Content Strategy\n\n' + ''.join(
            [
                section('Business goal', s.business_goal),
                section('Target audience', s.audience),
                section('Platforms', bullets(s.platforms)),
                section('Posting frequency', s.posting_frequency),
                section('Best posting times', bullets(s.posting_times)),
                section('Content pillars', bullets(s.content_pillars)),
                section('KPIs', s.kpi_notes),
                section('Notes', s.notes),
            ]
        )
        WorkspacePage.objects.create(
            project_id=s.project_id,
            created_by_id=s.created_by_id,
            updated_by_id=s.created_by_id,
            title=s.title or 'Content Strategy',
            icon='🎯',
            body=body.rstrip() + '\n',
        )


class Migration(migrations.Migration):
    dependencies = [
        ('api', '0010_workspace_calendar'),
    ]

    operations = [
        migrations.RunPython(strategies_to_pages, migrations.RunPython.noop),
        migrations.DeleteModel(name='Strategy'),
    ]
