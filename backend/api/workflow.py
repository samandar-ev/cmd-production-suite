from django.db import transaction
from django.utils.translation import gettext as _
from rest_framework import serializers
from rest_framework.exceptions import ValidationError

from .models import ContentItem, Task, TaskStage, TaskStatus, UserRole
from .models import ContentItemStatus as CS

WORKFLOWS = {
    'shoot_edit': [TaskStage.SHOOT, TaskStage.EDIT],
    'edit_only': [TaskStage.EDIT],
    'shoot_only': [TaskStage.SHOOT],
}
STAGE_ROLE = {TaskStage.SHOOT: UserRole.VIDEOGRAPHER, TaskStage.EDIT: UserRole.EDITOR}
STAGE_ORDER = {TaskStage.SHOOT: 0, TaskStage.EDIT: 1, TaskStage.OTHER: 2}
DONE = (TaskStatus.COMPLETED, TaskStatus.CANCELLED)


def is_blocked(task):
    dep = task.depends_on
    return bool(dep and dep.status != TaskStatus.COMPLETED)


def production_tasks(item):
    tasks = [
        t
        for t in item.tasks.exclude(status=TaskStatus.CANCELLED).select_related('assigned_to')
        if t.stage in (TaskStage.SHOOT, TaskStage.EDIT)
    ]
    return sorted(tasks, key=lambda t: (STAGE_ORDER[t.stage], t.id))


@transaction.atomic
def start_production(item, by, data):
    workflow = data.get('workflow')
    if workflow not in WORKFLOWS:
        raise ValidationError({'workflow': _('Choose “Shoot → Edit”, “Edit only” or “Shoot only”.')})
    if production_tasks(item):
        raise ValidationError({'error': _('Production has already started for this content item.')})

    from .models import User

    steps, created, previous = WORKFLOWS[workflow], [], None
    for stage in steps:
        person_id = data.get('videographer' if stage == TaskStage.SHOOT else 'editor')
        person = User.objects.filter(pk=person_id, role=STAGE_ROLE[stage], is_active=True).first()
        if person is None:
            who = 'videographer' if stage == TaskStage.SHOOT else 'editor'
            raise ValidationError(
                {
                    who: _('Choose an active videographer for the shoot step.')
                    if stage == TaskStage.SHOOT
                    else _('Choose an active editor for the edit step.')
                }
            )
        raw_due = data.get(f'{stage}_due')
        if not raw_due:
            raise ValidationError(
                {
                    f'{stage}_due': _('Set a deadline for the shoot step.')
                    if stage == TaskStage.SHOOT
                    else _('Set a deadline for the edit step.')
                }
            )
        try:
            due = serializers.DateTimeField().to_internal_value(raw_due)
        except ValidationError:
            raise ValidationError({f'{stage}_due': _('Invalid date.')}) from None
        if previous and due <= previous.due_date:
            raise ValidationError({f'{stage}_due': _('The edit deadline must be after the shoot deadline.')})
        task = Task.objects.create(
            project=item.project,
            content_item=item,
            stage=stage,
            depends_on=previous,
            title=(_('Shoot: %(title)s') if stage == TaskStage.SHOOT else _('Edit: %(title)s')) % {'title': item.title},
            description=data.get(f'{stage}_brief') or '',
            task_type=stage.capitalize(),
            assigned_to=person,
            assigned_by=by,
            due_date=due,
            priority=data.get('priority') or 'Medium',
        )
        created.append(task)
        previous = task
        setattr(item, 'assigned_videographer' if stage == TaskStage.SHOOT else 'assigned_editor', person)
    item.save()
    refresh_item_status(item)
    return created


def refresh_item_status(item):
    if item is None:
        return
    item = ContentItem.objects.get(pk=item.pk)
    if item.status in (CS.PUBLISHED, CS.COMPLETED):
        return
    tasks = production_tasks(item)
    if not tasks:
        return
    current = next((t for t in tasks if t.status not in DONE), None)
    if current is None:
        new = CS.APPROVED
    else:
        latest = current.file_submissions.exclude(status='uploading').order_by('-created_at').first()
        if current.status == TaskStatus.WAITING_FOR_REVIEW:
            new = CS.UNDER_REVIEW
        elif latest and latest.status == 'rejected':
            new = CS.REVISION_REQUESTED
        elif current.stage == TaskStage.SHOOT:
            new = CS.SHOOTING if current.status == TaskStatus.IN_PROGRESS else CS.READY_FOR_SHOOTING
        else:
            new = CS.EDITING if current.status == TaskStatus.IN_PROGRESS else CS.READY_FOR_EDITING
    if item.status != new:
        ContentItem.set_status(item.pk, new)


def unlocked_by(task):
    return [t for t in task.dependents.exclude(status__in=DONE) if not is_blocked(t)]
