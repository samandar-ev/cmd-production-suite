import { useCallback, useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { ChevronLeft, ChevronRight, Plus, Trash2 } from 'lucide-react';
import api, { errorText, list } from '../lib/api';
import { useAuth, isManager, nameOf } from '../lib/auth';
import { STAGES } from '../lib/stages';
import { time } from '../lib/format';
import { Dialog, PageHeader, Spinner } from '../ui';
import { useToast, useConfirm } from '../lib/hooks';
import { locale as loc, tr } from '../lib/i18n';

const ymd = d =>
  `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
const pad = n => String(n).padStart(2, '0');
const local = d => `${ymd(d)}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
const color = it =>
  it.type === 'order'
    ? STAGES.find(s => s.key === it.stage)?.color || 'var(--color-plan)'
    : it.type === 'publish'
      ? 'var(--color-publish)'
      : it.type === 'event'
        ? 'var(--color-ink)'
        : 'var(--color-mist)';
const KINDS = [
  ['order', tr('Orders')],
  ['publish', tr('Publishing')],
  ['event', tr('Events')],
  ['todo', tr('To-dos')],
];

export default function Calendar() {
  const navigate = useNavigate();
  const user = useAuth(s => s.user);
  const [month, setMonth] = useState(() => {
    const d = new Date();
    d.setDate(1);
    d.setHours(0, 0, 0, 0);
    return d;
  });
  const [items, setItems] = useState(null);
  const [hidden, setHidden] = useState([]);
  const [editing, setEditing] = useState(null);

  const days = useMemo(() => {
    const first = new Date(month);
    const shift = (first.getDay() + 6) % 7;
    first.setDate(first.getDate() - shift);
    return Array.from({ length: 42 }, (_, i) => {
      const d = new Date(first);
      d.setDate(first.getDate() + i);
      return d;
    });
  }, [month]);
  const load = useCallback(() => {
    api
      .get('calendar/', { params: { start: ymd(days[0]), end: ymd(days[41]), tz: -new Date().getTimezoneOffset() } })
      .then(r => setItems(r.data))
      .catch(() => setItems([]));
  }, [days]);
  useEffect(() => {
    load();
  }, [load]);

  const byDay = useMemo(() => {
    const m = {};
    (items || [])
      .filter(i => !hidden.includes(i.type))
      .forEach(i => {
        const k = ymd(new Date(i.start));
        (m[k] ||= []).push(i);
      });
    Object.values(m).forEach(arr =>
      arr.sort((a, b) => (a.all_day === b.all_day ? new Date(a.start) - new Date(b.start) : a.all_day ? -1 : 1)),
    );
    return m;
  }, [items, hidden]);

  const open = it => {
    if (it.type === 'event') return setEditing({ kind: 'event', id: it.ref });
    if (it.type === 'todo') return setEditing({ kind: 'todo', id: it.ref });
    if (it.link)
      navigate(
        it.type === 'order'
          ? `/orders/${it.ref}`
          : it.type === 'publish' && isManager(user)
            ? `/content/${it.ref}`
            : '/',
      );
  };
  const today = ymd(new Date());
  const step = n =>
    setMonth(m => {
      const d = new Date(m);
      d.setMonth(d.getMonth() + n);
      return d;
    });
  const agenda = days.filter(d => d.getMonth() === month.getMonth() && byDay[ymd(d)]?.length);

  return (
    <>
      <PageHeader
        title={month.toLocaleDateString(loc(), { month: 'long', year: 'numeric' }).replace(/^./, c => c.toUpperCase())}
        actions={
          <>
            <div className="flex items-center gap-1">
              <button onClick={() => step(-1)} className="btn-icon" aria-label={tr('Previous month')}>
                <ChevronLeft size={18} />
              </button>
              <button
                onClick={() => {
                  const d = new Date();
                  d.setDate(1);
                  d.setHours(0, 0, 0, 0);
                  setMonth(d);
                }}
                className="btn btn-quiet btn-sm"
              >
                {tr('Today')}
              </button>
              <button onClick={() => step(1)} className="btn-icon" aria-label={tr('Next month')}>
                <ChevronRight size={18} />
              </button>
            </div>
            <button onClick={() => setEditing({ kind: 'todo' })} className="btn btn-quiet">
              <Plus /> {tr('To-do')}
            </button>
            <button onClick={() => setEditing({ kind: 'event' })} className="btn btn-primary">
              <Plus /> {tr('Event')}
            </button>
          </>
        }
      />

      <div className="flex flex-wrap gap-1.5 mb-4" role="group" aria-label={tr('Show')}>
        {KINDS.map(([k, l]) => (
          <button
            key={k}
            onClick={() => setHidden(h => (h.includes(k) ? h.filter(x => x !== k) : [...h, k]))}
            aria-pressed={!hidden.includes(k)}
            className={`btn btn-sm ${hidden.includes(k) ? 'btn-ghost text-mist line-through' : 'btn-quiet'}`}
          >
            <span
              className="w-2.5 h-2.5 rounded-[3px]"
              style={{ background: k === 'order' ? 'var(--color-shoot)' : color({ type: k }) }}
            />
            {l}
          </button>
        ))}
      </div>

      {items === null ? (
        <Spinner />
      ) : (
        <>
          <section className="hidden md:block panel overflow-hidden">
            <div className="grid grid-cols-7 border-b border-hairline bg-haze/50">
              {days.slice(0, 7).map(d => (
                <span key={d} className="px-3 py-2 text-[12px] font-semibold text-graphite">
                  {d.toLocaleDateString(loc(), { weekday: 'short' })}
                </span>
              ))}
            </div>
            <div className="grid grid-cols-7">
              {days.map((d, i) => {
                const k = ymd(d);
                const its = byDay[k] || [];
                const out = d.getMonth() !== month.getMonth();
                return (
                  <div
                    key={k}
                    className={`min-h-[118px] p-1.5 border-hairline ${i % 7 ? 'border-l' : ''} ${i >= 7 ? 'border-t' : ''} ${out ? 'bg-haze/40' : ''}`}
                  >
                    <span
                      className={`inline-flex items-center justify-center w-7 h-7 rounded-full text-[13px] num ${k === today ? 'bg-tally text-paper font-semibold' : out ? 'text-mist' : 'text-graphite'}`}
                    >
                      {d.getDate()}
                    </span>
                    <ul className="space-y-0.5 mt-0.5">
                      {its.slice(0, 3).map(it => (
                        <li key={it.id}>
                          <button
                            onClick={() => open(it)}
                            title={it.title}
                            className={`w-full text-left flex items-center gap-1.5 rounded-[5px] px-1.5 py-0.5 text-[12px] hover:bg-haze ${it.completed || it.status === 'completed' ? 'line-through text-mist' : ''}`}
                          >
                            <span className="w-1 h-3.5 rounded-full shrink-0" style={{ background: color(it) }} />
                            {!it.all_day && <span className="num text-mist shrink-0">{time(it.start)}</span>}
                            <span className="truncate">{it.title}</span>
                          </button>
                        </li>
                      ))}
                      {its.length > 3 && (
                        <li className="text-[12px] text-graphite px-1.5">{tr('+{n} more', { n: its.length - 3 })}</li>
                      )}
                    </ul>
                  </div>
                );
              })}
            </div>
          </section>

          <section className="md:hidden space-y-4">
            {agenda.length === 0 && <p className="panel p-6 text-graphite">{tr('Nothing this month.')}</p>}
            {agenda.map(d => (
              <div key={d}>
                <h2 className={`text-[14px] font-semibold mb-1.5 ${ymd(d) === today ? 'text-tally' : 'text-graphite'}`}>
                  {d.toLocaleDateString(loc(), { weekday: 'long', day: 'numeric', month: 'long' })}
                </h2>
                <ul className="panel divide-y divide-hairline">
                  {byDay[ymd(d)].map(it => (
                    <li key={it.id}>
                      <button onClick={() => open(it)} className="w-full text-left flex items-center gap-3 px-4 py-3">
                        <span className="w-1 self-stretch rounded-full" style={{ background: color(it) }} />
                        <span className="text-[13px] text-graphite num w-11 shrink-0">
                          {it.all_day ? tr('All day') : time(it.start)}
                        </span>
                        <span
                          className={`min-w-0 flex-1 truncate font-medium ${it.completed ? 'line-through text-mist' : ''}`}
                        >
                          {it.title}
                        </span>
                      </button>
                    </li>
                  ))}
                </ul>
              </div>
            ))}
          </section>
        </>
      )}
      {editing?.kind === 'event' && <EventDialog id={editing.id} onClose={() => setEditing(null)} onSaved={load} />}
      {editing?.kind === 'todo' && <TodoDialog id={editing.id} onClose={() => setEditing(null)} onSaved={load} />}
    </>
  );
}

function EventDialog({ id, onClose, onSaved }) {
  const toast = useToast();
  const confirm = useConfirm();
  const [form, setForm] = useState(null);
  const [people, setPeople] = useState([]);
  const [projects, setProjects] = useState([]);
  const [error, setError] = useState('');
  useEffect(() => {
    const start = new Date();
    start.setMinutes(0, 0, 0);
    start.setHours(start.getHours() + 1);
    const end = new Date(start);
    end.setHours(end.getHours() + 1);
    Promise.all([
      api
        .get('users/')
        .then(list)
        .catch(() => []),
      api
        .get('projects/')
        .then(list)
        .catch(() => []),
      id ? api.get(`calendar-events/${id}/`).then(r => r.data) : null,
    ]).then(([u, p, ev]) => {
      setPeople(u.filter(x => x.is_active));
      setProjects(p);
      setForm(
        ev
          ? { ...ev, start: local(new Date(ev.start)), end: local(new Date(ev.end)) }
          : {
              title: '',
              start: local(start),
              end: local(end),
              all_day: false,
              project: '',
              location: '',
              notes: '',
              attendees: [],
            },
      );
    });
  }, [id]);
  if (!form) return null;
  const set = k => e => setForm(f => ({ ...f, [k]: e.target.type === 'checkbox' ? e.target.checked : e.target.value }));
  const save = async e => {
    e.preventDefault();
    setError('');
    const body = {
      ...form,
      project: form.project || null,
      start: new Date(form.start).toISOString(),
      end: new Date(form.end).toISOString(),
    };
    try {
      id ? await api.patch(`calendar-events/${id}/`, body) : await api.post('calendar-events/', body);
      toast(id ? tr('Event updated') : tr('Event added — guests are notified'));
      onSaved();
      onClose();
    } catch (err) {
      setError(errorText(err));
    }
  };
  const remove = async () => {
    if (
      !(await confirm({
        title: tr('Delete this event?'),
        body: tr('Guests are not told; let them know if it’s cancelled.'),
        action: tr('Delete event'),
        danger: true,
      }))
    )
      return;
    await api
      .delete(`calendar-events/${id}/`)
      .then(() => {
        onSaved();
        onClose();
      })
      .catch(err => setError(errorText(err)));
  };
  const toggle = uid =>
    setForm(f => ({
      ...f,
      attendees: f.attendees.includes(uid) ? f.attendees.filter(x => x !== uid) : [...f.attendees, uid],
    }));
  return (
    <Dialog
      title={id ? tr('Event') : tr('New event')}
      onClose={onClose}
      footer={
        <>
          {id && (
            <button onClick={remove} className="btn btn-ghost text-tally mr-auto">
              <Trash2 /> {tr('Delete')}
            </button>
          )}
          <button onClick={onClose} className="btn btn-ghost">
            {tr('Cancel')}
          </button>
          <button form="ev" disabled={!form.title.trim()} className="btn btn-primary">
            {id ? tr('Save') : tr('Add event')}
          </button>
        </>
      }
    >
      <form id="ev" onSubmit={save} className="space-y-4">
        {error && (
          <p role="alert" className="text-tally">
            {error}
          </p>
        )}
        <div>
          <label className="label" htmlFor="ev-t">
            {tr('What')}
          </label>
          <input
            id="ev-t"
            className="field"
            value={form.title}
            onChange={set('title')}
            placeholder={tr('e.g. Shoot at Peak Form Gym')}
            required
          />
        </div>
        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="label" htmlFor="ev-s">
              {tr('Starts')}
            </label>
            <input id="ev-s" type="datetime-local" className="field" value={form.start} onChange={set('start')} />
          </div>
          <div>
            <label className="label" htmlFor="ev-e">
              {tr('Ends')}
            </label>
            <input id="ev-e" type="datetime-local" className="field" value={form.end} onChange={set('end')} />
          </div>
        </div>
        <div className="grid sm:grid-cols-2 gap-3">
          <div>
            <label className="label" htmlFor="ev-p">
              {tr('Project')}
            </label>
            <select id="ev-p" className="field" value={form.project || ''} onChange={set('project')}>
              <option value="">{tr('Personal')}</option>
              {projects.map(p => (
                <option key={p.id} value={p.id}>
                  {p.name}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="label" htmlFor="ev-l">
              {tr('Where')}
            </label>
            <input
              id="ev-l"
              className="field"
              value={form.location}
              onChange={set('location')}
              placeholder={tr('Address or link')}
            />
          </div>
        </div>
        <div>
          <span className="label">{tr('Who’s coming')}</span>
          <div className="flex flex-wrap gap-1.5">
            {people.map(u => (
              <button
                type="button"
                key={u.id}
                onClick={() => toggle(u.id)}
                aria-pressed={form.attendees.includes(u.id)}
                className={`btn btn-sm ${form.attendees.includes(u.id) ? 'btn-primary' : 'btn-quiet'}`}
              >
                {nameOf(u)}
              </button>
            ))}
          </div>
        </div>
        <div>
          <label className="label" htmlFor="ev-n">
            {tr('Notes')}
          </label>
          <textarea id="ev-n" rows={2} className="field" value={form.notes} onChange={set('notes')} />
        </div>
      </form>
    </Dialog>
  );
}

export function TodoDialog({ id, onClose, onSaved, preset = {} }) {
  const toast = useToast();
  const [form, setForm] = useState(null);
  const [projects, setProjects] = useState([]);
  const [people, setPeople] = useState([]);
  const [blank] = useState(() => ({
    title: '',
    due_date: ymd(new Date()),
    project: '',
    assignee: '',
    priority: 4,
    notes: '',
    ...preset,
  }));
  useEffect(() => {
    Promise.all([
      api
        .get('projects/')
        .then(list)
        .catch(() => []),
      api
        .get('users/')
        .then(list)
        .catch(() => []),
      id ? api.get(`workspace-todos/${id}/`).then(r => r.data) : null,
    ]).then(([p, u, t]) => {
      setProjects(p);
      setPeople(u.filter(x => x.is_active));
      setForm(t || blank);
    });
  }, [id, blank]);
  if (!form) return null;
  const set = k => e => setForm(f => ({ ...f, [k]: e.target.value }));
  const save = async e => {
    e.preventDefault();
    const body = {
      ...form,
      project: form.project || null,
      assignee: form.assignee || null,
      due_date: form.due_date || null,
    };
    try {
      id ? await api.patch(`workspace-todos/${id}/`, body) : await api.post('workspace-todos/', body);
      toast(id ? tr('To-do updated') : tr('To-do added'));
      onSaved();
      onClose();
    } catch (err) {
      toast(errorText(err), 'error');
    }
  };
  const remove = async () => {
    await api.delete(`workspace-todos/${id}/`).catch(() => {});
    onSaved();
    onClose();
  };
  return (
    <Dialog
      title={id ? tr('To-do') : tr('New to-do')}
      onClose={onClose}
      footer={
        <>
          {id && (
            <button onClick={remove} className="btn btn-ghost text-tally mr-auto">
              <Trash2 /> {tr('Delete')}
            </button>
          )}
          <button onClick={onClose} className="btn btn-ghost">
            {tr('Cancel')}
          </button>
          <button form="td" disabled={!form.title.trim()} className="btn btn-primary">
            {id ? tr('Save') : tr('Add to-do')}
          </button>
        </>
      }
    >
      <form id="td" onSubmit={save} className="space-y-4">
        <div>
          <label className="label" htmlFor="td-t">
            {tr('What needs doing')}
          </label>
          <input id="td-t" className="field" value={form.title} onChange={set('title')} required />
        </div>
        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="label" htmlFor="td-d">
              {tr('Due')}
            </label>
            <input id="td-d" type="date" className="field" value={form.due_date || ''} onChange={set('due_date')} />
          </div>
          <div>
            <label className="label" htmlFor="td-pr">
              {tr('Priority')}
            </label>
            <select id="td-pr" className="field" value={form.priority} onChange={set('priority')}>
              <option value={1}>{tr('Urgent')}</option>
              <option value={2}>{tr('High')}</option>
              <option value={3}>{tr('Medium')}</option>
              <option value={4}>{tr('Low')}</option>
            </select>
          </div>
        </div>
        <div className="grid sm:grid-cols-2 gap-3">
          <div>
            <label className="label" htmlFor="td-p">
              {tr('Project')}
            </label>
            <select id="td-p" className="field" value={form.project || ''} onChange={set('project')}>
              <option value="">{tr('Personal')}</option>
              {projects.map(p => (
                <option key={p.id} value={p.id}>
                  {p.name}
                </option>
              ))}
            </select>
          </div>
          {form.project && (
            <div>
              <label className="label" htmlFor="td-a">
                {tr('For')}
              </label>
              <select id="td-a" className="field" value={form.assignee || ''} onChange={set('assignee')}>
                <option value="">{tr('Me')}</option>
                {people.map(u => (
                  <option key={u.id} value={u.id}>
                    {nameOf(u)}
                  </option>
                ))}
              </select>
            </div>
          )}
        </div>
        <div>
          <label className="label" htmlFor="td-n">
            {tr('Notes')}
          </label>
          <textarea id="td-n" rows={2} className="field" value={form.notes || ''} onChange={set('notes')} />
        </div>
      </form>
    </Dialog>
  );
}
