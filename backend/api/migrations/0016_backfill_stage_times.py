from django.db import migrations
from django.db.models import Max


def backfill(apps, schema_editor):
    ContentItem = apps.get_model('api', 'ContentItem')
    Change = apps.get_model('api', 'ContentStatusChange')
    Task = apps.get_model('api', 'Task')
    Video = apps.get_model('api', 'VideoSubmission')
    changes = []
    for item in ContentItem.objects.filter(status_changed_at__isnull=True):
        item.status_changed_at = item.updated_at
        item.save(update_fields=['status_changed_at'])
        changes.append(Change(content_item=item, status=item.status, changed_at=item.updated_at))
    Change.objects.bulk_create(changes)
    approved = dict(
        Video.objects.filter(status='approved', task__isnull=False)
        .values('task')
        .annotate(at=Max('reviewed_at'))
        .values_list('task', 'at')
    )
    for task in Task.objects.filter(status='completed', completed_at__isnull=True):
        task.completed_at = approved.get(task.id) or task.updated_at
        task.save(update_fields=['completed_at'])


class Migration(migrations.Migration):
    dependencies = [('api', '0015_stage_times')]
    operations = [migrations.RunPython(backfill, migrations.RunPython.noop)]
