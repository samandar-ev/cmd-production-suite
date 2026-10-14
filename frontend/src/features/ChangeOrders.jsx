import { useEffect, useMemo, useState } from 'react';
import { Lock, Bell } from 'lucide-react';
import api, { errorText, list } from '../lib/api';
import { nameOf } from '../lib/auth';
import { ORDER_TEXT, STAGES } from '../lib/stages';
import { Dialog, Spinner } from '../ui';
import { useToast } from '../lib/hooks';
import { tr } from '../lib/i18n';

const DONE = ['completed', 'cancelled'];
const ROLES = { shoot: ['VIDEOGRAPHER'], edit: ['EDITOR'], other: ['VIDEOGRAPHER', 'EDITOR'] };
const pad = n => String(n).padStart(2, '0');
const toInput = d =>
  d
    ? `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`
    : '';
const at = days => {
  const d = new Date();
  d.setDate(d.getDate() + days);
  d.setHours(18, 0, 0, 0);
  return toInput(d);
};
const QUICK = [
  [tr('Today 18:00'), 0],
  [tr('Tomorrow'), 1],
  [tr('In 3 days'), 3],
  [tr('In a week'), 7],
];

export default function ChangeOrders({ taskIds, onClose, onSaved }) {
  const toast = useToast();
  const [orders, setOrders] = useState(null);
  const [people, setPeople] = useState([]);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    Promise.all([
      Promise.all(taskIds.map(id => api.get(`tasks/${id}/`).then(r => r.data))),
      api.get('users/').then(list),
    ])
      .then(([tasks, users]) => {
        setPeople(users.filter(u => u.is_active));
        setOrders(
          tasks
            .filter(t => !DONE.includes(t.status))
            .map(t => ({
              task: t,
              form: {
                who: t.assigned_to ? String(t.assigned_to) : '',
                due: t.due_date ? toInput(new Date(t.due_date)) : '',
                title: t.title,
                description: t.description || '',
              },
            })),
        );
      })
      .catch(err => setError(errorText(err)));
  }, [taskIds]);

  const set = (i, patch) => setOrders(os => os.map((o, k) => (k === i ? { ...o, form: { ...o.form, ...patch } } : o)));
  const changes = useMemo(
    () =>
      (orders || [])
        .map(({ task, form }) => {
          const body = {};
          if (form.who !== (task.assigned_to ? String(task.assigned_to) : ''))
            body.assigned_to = form.who ? Number(form.who) : null;
          if (form.due !== (task.due_date ? toInput(new Date(task.due_date)) : ''))
            body.due_date = form.due ? new Date(form.due).toISOString() : null;
          if (form.title.trim() && form.title.trim() !== task.title) body.title = form.title.trim();
          if (form.description !== (task.description || '')) body.description = form.description;
          return { task, body };
        })
        .filter(c => Object.keys(c.body).length),
    [orders],
  );

  const person = id => nameOf(people.find(u => String(u.id) === String(id)));
  const heads = changes.flatMap(({ task, body }) =>
    'assigned_to' in body
      ? [
          body.assigned_to && tr('{name} gets “{title}”.', { name: person(body.assigned_to), title: task.title }),
          task.assigned_to && tr('{name} is told it’s no longer theirs.', { name: task.assigned_to_name }),
        ].filter(Boolean)
      : 'due_date' in body && task.assigned_to
        ? [tr('{name} is told about the new deadline.', { name: task.assigned_to_name })]
        : [],
  );

  const save = async () => {
    setSaving(true);
    setError('');
    try {
      for (const { task, body } of changes) await api.patch(`tasks/${task.id}/`, body);
      toast(tr('Changes saved — people have been notified'));
      onSaved?.();
      onClose();
    } catch (err) {
      setError(errorText(err));
    } finally {
      setSaving(false);
    }
  };

  return (
    <Dialog
      title={tr('Change order')}
      sub={orders?.[0] && [orders[0].task.project_name, orders[0].task.content_item_title].filter(Boolean).join(', ')}
      onClose={onClose}
      footer={
        <>
          <button onClick={onClose} className="btn btn-ghost">
            {tr('Cancel')}
          </button>
          <button onClick={save} disabled={saving || !changes.length} className="btn btn-primary">
            {saving ? tr('Saving…') : tr('Save changes')}
          </button>
        </>
      }
    >
      {error && (
        <p role="alert" className="text-tally mb-3">
          {error}
        </p>
      )}
      {!orders ? (
        <Spinner />
      ) : orders.length === 0 ? (
        <p className="text-graphite">{tr('Every order here is finished — nothing to change.')}</p>
      ) : (
        <div className="space-y-6">
          {orders.map(({ task, form }, i) => {
            const stage = STAGES.find(s => s.key === task.stage);
            const candidates = people.filter(
              u => (ROLES[task.stage] || ROLES.other).includes(u.role) || String(u.id) === form.who,
            );
            return (
              <section
                key={task.id}
                className={orders.length > 1 ? 'pl-4 border-l-[3px]' : ''}
                style={orders.length > 1 ? { borderColor: stage?.color || 'var(--color-hairline)' } : {}}
              >
                <div className="flex items-baseline justify-between gap-3 mb-3">
                  <h3 className="font-semibold">{stage?.label || task.title}</h3>
                  <span className="text-[13px] text-graphite">
                    {task.is_blocked ? tr('Up next') : ORDER_TEXT[task.status]}
                  </span>
                </div>
                {task.is_blocked && (
                  <p className="text-[13px] text-graphite mb-3 flex items-center gap-1.5">
                    <Lock size={13} /> {tr('Starts when the previous step is approved.')}
                  </p>
                )}
                <label className="label" htmlFor={`w${task.id}`}>
                  {tr('Who does it')}
                </label>
                <select
                  id={`w${task.id}`}
                  className="field"
                  value={form.who}
                  onChange={e => set(i, { who: e.target.value })}
                >
                  <option value="">{tr('Nobody yet')}</option>
                  {candidates.map(u => (
                    <option key={u.id} value={u.id}>
                      {nameOf(u)}
                      {String(u.id) === String(task.assigned_to) ? ` (${tr('now')})` : ''}
                    </option>
                  ))}
                </select>
                <label className="label mt-4" htmlFor={`d${task.id}`}>
                  {tr('Deadline')}
                </label>
                <input
                  id={`d${task.id}`}
                  type="datetime-local"
                  className="field"
                  value={form.due}
                  onChange={e => set(i, { due: e.target.value })}
                />
                <div className="flex flex-wrap gap-1.5 mt-2">
                  {QUICK.map(([label, days]) => (
                    <button
                      key={label}
                      type="button"
                      onClick={() => set(i, { due: at(days) })}
                      aria-pressed={form.due === at(days)}
                      className={`btn btn-sm ${form.due === at(days) ? 'btn-primary' : 'btn-quiet'}`}
                    >
                      {label}
                    </button>
                  ))}
                  {form.due && (
                    <button type="button" onClick={() => set(i, { due: '' })} className="btn btn-sm btn-ghost">
                      {tr('No deadline')}
                    </button>
                  )}
                </div>
                <details className="mt-4">
                  <summary className="text-[14px] font-semibold text-graphite cursor-pointer hover:text-ink">
                    {tr('Title and instructions')}
                  </summary>
                  <label className="label mt-3" htmlFor={`t${task.id}`}>
                    {tr('Title')}
                  </label>
                  <input
                    id={`t${task.id}`}
                    className="field"
                    value={form.title}
                    onChange={e => set(i, { title: e.target.value })}
                  />
                  <label className="label mt-3" htmlFor={`i${task.id}`}>
                    {tr('Instructions')}
                  </label>
                  <textarea
                    id={`i${task.id}`}
                    rows={3}
                    className="field"
                    value={form.description}
                    onChange={e => set(i, { description: e.target.value })}
                  />
                </details>
              </section>
            );
          })}
          {heads.length > 0 && (
            <ul className="rounded-[10px] bg-haze px-4 py-3 space-y-1 text-[14px]">
              {heads.map(h => (
                <li key={h} className="flex gap-2">
                  <Bell size={14} className="mt-1 shrink-0 text-graphite" />
                  {h}
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </Dialog>
  );
}
