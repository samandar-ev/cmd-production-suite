import { left } from './format';
import { tr } from './i18n';

export const STAGES = [
  { key: 'plan', label: tr('Plan'), color: 'var(--color-plan)' },
  { key: 'shoot', label: tr('Shoot'), color: 'var(--color-shoot)' },
  { key: 'edit', label: tr('Edit'), color: 'var(--color-edit)' },
  { key: 'review', label: tr('Review'), color: 'var(--color-review)' },
  { key: 'publish', label: tr('Publish'), color: 'var(--color-publish)' },
];

const MAP = {
  planned: ['plan', 0.25],
  scripting: ['plan', 0.65],
  ready_for_shooting: ['shoot', 0.15],
  shooting: ['shoot', 0.6],
  ready_for_editing: ['edit', 0.15],
  editing: ['edit', 0.6],
  revision_requested: ['edit', 0.75],
  under_review: ['review', 0.5],
  approved: ['review', 1],
  published: ['publish', 1],
  completed: ['publish', 1],
};

export const STATUS_TEXT = {
  planned: tr('Planned'),
  scripting: tr('Writing the script'),
  ready_for_shooting: tr('Ready to shoot'),
  shooting: tr('Shooting'),
  ready_for_editing: tr('Ready to edit'),
  editing: tr('Editing'),
  revision_requested: tr('Changes requested'),
  under_review: tr('Waiting for review'),
  approved: tr('Approved — ready to publish'),
  published: tr('Published'),
  completed: tr('Done'),
};

export const stageOf = status => STAGES.find(s => s.key === (MAP[status]?.[0] || 'plan'));

export const progressOf = status => {
  const [key, within] = MAP[status] || ['plan', 0.1];
  const i = STAGES.findIndex(s => s.key === key);
  return (i + within) / STAGES.length;
};

export const currentStep = item =>
  (item.production || []).find(s => !['completed', 'cancelled'].includes(s.status)) || null;

export const lateOf = item => {
  const s = currentStep(item);
  return !!(s?.due_date && !s.is_blocked && left(s.due_date).late);
};

export const PROJECT_STATUS = [
  ['active', tr('Active')],
  ['draft', tr('Draft')],
  ['on_hold', tr('On hold')],
  ['completed', tr('Completed')],
  ['archived', tr('Archived')],
  ['cancelled', tr('Cancelled')],
];
export const PROJECT_STATUS_TEXT = Object.fromEntries(PROJECT_STATUS);

export const ORDER_TEXT = {
  not_started: tr('New'),
  in_progress: tr('In progress'),
  waiting_for_review: tr('Sent for review'),
  completed: tr('Done'),
  overdue: tr('Late'),
  rejected: tr('Changes requested'),
  cancelled: tr('Cancelled'),
};
