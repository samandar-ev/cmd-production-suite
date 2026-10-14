import { useEffect, useMemo, useRef, useState } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import { Plus, Search, PencilLine, ListTodo } from 'lucide-react';
import api, { errorText, list } from '../lib/api';
import { STAGES, STATUS_TEXT, currentStep, lateOf, progressOf, stageOf, ORDER_TEXT } from '../lib/stages';
import { Avatar, Dialog, Due, Empty, PageHeader, Spinner } from '../ui';
import { useLoad, useToast } from '../lib/hooks';
import ChangeOrders from '../features/ChangeOrders';
import NewContent from '../features/NewContent';
import { tr, trn } from '../lib/i18n';

async function loadBoard() {
  const [items, projects, users, tasks] = await Promise.all([
    api.get('content-items/').then(list),
    api.get('projects/').then(list),
    api.get('users/').then(list),
    api.get('tasks/').then(list),
  ]);
  return { items, projects, users, other: tasks.filter(t => !t.content_item) };
}

const WIDE = 880;

export function Track({ item, onChange }) {
  const navigate = useNavigate();
  const p = progressOf(item.status);
  const here = stageOf(item.status);
  const step = currentStep(item);
  const late = lateOf(item);
  const done = ['published', 'completed'].includes(item.status);
  const hereIdx = STAGES.findIndex(s => s.key === here.key);
  const row = useRef(null);
  const [wide, setWide] = useState(false);
  useEffect(() => {
    const ro = new ResizeObserver(([e]) => setWide(e.contentRect.width >= WIDE));
    ro.observe(row.current);
    return () => ro.disconnect();
  }, []);

  return (
    <li
      ref={row}
      className="group relative grid @[880px]:grid-cols-[minmax(220px,280px)_1fr] gap-x-6 gap-y-2.5 py-4 @[880px]:py-3 px-4 sm:px-5 border-b border-hairline last:border-0 hover:bg-haze/60 cursor-pointer"
      onClick={() => navigate(`/content/${item.id}`)}
    >
      <div className="min-w-0 flex items-start justify-between gap-3 @[880px]:block">
        <div className="min-w-0">
          <Link
            to={`/content/${item.id}`}
            onClick={e => e.stopPropagation()}
            className="block font-semibold truncate hover:underline underline-offset-2"
          >
            {item.title}
          </Link>
          <p className="text-[13px] text-graphite truncate">
            {item.client_name}, {item.platform} {item.content_type && tr(item.content_type).toLowerCase()}
          </p>
        </div>
        {step && (
          <button
            onClick={e => {
              e.stopPropagation();
              onChange(item);
            }}
            className="btn btn-ghost btn-sm -mr-2 @[880px]:hidden"
          >
            <PencilLine /> {tr('Change')}
          </button>
        )}
      </div>

      <div className={`relative min-w-0 ${wide ? 'h-11' : 'pt-6'}`}>
        <div className="absolute inset-0 grid grid-cols-5">
          {STAGES.map((s, i) => (
            <span key={s.key} className={`border-l border-hairline/80 ${i === hereIdx ? 'bg-haze' : ''}`} />
          ))}
        </div>
        <div
          className="absolute left-0 top-1.5 h-3.5 flex rounded-[4px] overflow-hidden"
          style={{ width: `${p * 100}%` }}
        >
          {STAGES.slice(0, hereIdx + 1).map((s, i) => (
            <span
              key={s.key}
              className="h-full shrink-0"
              style={{
                background: s.color,
                opacity: i < hereIdx && !done ? 0.42 : 1,
                width: `${((i < hereIdx ? 1 / STAGES.length : p - hereIdx / STAGES.length) / p) * 100}%`,
              }}
            />
          ))}
        </div>
        <span
          className={`absolute top-0 h-6 w-[2px] rounded-full ${late ? 'bg-tally' : 'bg-ink'}`}
          style={{ left: `calc(${p * 100}% - 1px)` }}
        />
        <div
          className={`text-[13px] flex items-center gap-x-2 gap-y-0.5 ${wide ? `whitespace-nowrap absolute top-6 ${p > 0.62 ? 'flex-row-reverse' : ''}` : 'relative flex-wrap'}`}
          style={wide ? (p > 0.62 ? { right: `${(1 - p) * 100}%` } : { left: `${p * 100}%` }) : {}}
        >
          {step ? (
            <>
              <Avatar name={step.assignee} size={18} />
              <span className="font-medium">{step.assignee || tr('Nobody yet')}</span>
              {step.is_blocked ? (
                <span className="text-mist">{tr('waiting for the previous step')}</span>
              ) : (
                <Due date={step.due_date} done={step.status === 'waiting_for_review'} />
              )}
            </>
          ) : (
            <span className="text-graphite">{STATUS_TEXT[item.status]}</span>
          )}
        </div>
      </div>

      {step && (
        <button
          onClick={e => {
            e.stopPropagation();
            onChange(item);
          }}
          className="hidden @[880px]:inline-flex btn btn-quiet btn-sm absolute right-5 mt-1 opacity-0 group-hover:opacity-100 focus:opacity-100"
        >
          <PencilLine /> {tr('Change')}
        </button>
      )}
    </li>
  );
}

function BoardColumn({ stage, items }) {
  return (
    <section className="w-[78vw] sm:w-64 shrink-0 xl:w-auto xl:shrink snap-start min-w-0">
      <h3 className="flex items-center gap-2 text-[14px] font-semibold mb-3 px-1">
        <span className="w-3 h-3 rounded-[3px]" style={{ background: stage.color }} />
        {stage.label}
        <span className="text-mist font-normal num">{items.length}</span>
      </h3>
      <ul className="space-y-2">
        {items.map(item => {
          const step = currentStep(item);
          return (
            <li key={item.id}>
              <Link to={`/content/${item.id}`} className="block panel p-3.5 hover:border-mist">
                <p className="font-semibold leading-snug">{item.title}</p>
                <p className="text-[13px] text-graphite mt-0.5">{item.client_name}</p>
                <p className="text-[13px] mt-2.5 text-graphite">{STATUS_TEXT[item.status]}</p>
                {step && (
                  <div className="flex items-center gap-2 mt-2">
                    <Avatar name={step.assignee} size={18} />
                    <Due date={step.due_date} />
                  </div>
                )}
              </Link>
            </li>
          );
        })}
        {items.length === 0 && (
          <li className="text-[13px] text-mist px-1 py-6 text-center border border-dashed border-hairline rounded-[10px]">
            {tr('Nothing here')}
          </li>
        )}
      </ul>
    </section>
  );
}

export default function Production() {
  const [params, setParams] = useSearchParams();
  const { data, reload } = useLoad(loadBoard, []);
  const [changing, setChanging] = useState(null);
  const view = params.get('view') === 'board' ? 'board' : 'timeline';
  const stage = params.get('stage') || '';
  const project = params.get('project') || '';
  const who = params.get('who') || '';
  const q = params.get('q') || '';
  const lateOnly = params.get('late') === '1';
  const setParam = (k, v) => {
    const n = new URLSearchParams(params);
    v ? n.set(k, v) : n.delete(k);
    setParams(n, { replace: true });
  };

  const items = useMemo(() => {
    if (!data) return [];
    const s = q.trim().toLowerCase();
    return data.items
      .filter(i => i.status !== 'completed')
      .filter(i => !stage || stageOf(i.status).key === stage)
      .filter(i => !project || String(i.project) === project)
      .filter(i => !who || (i.production || []).some(st => st.assignee === who))
      .filter(i => !lateOnly || lateOf(i))
      .filter(i => !s || `${i.title} ${i.client_name} ${i.project_name}`.toLowerCase().includes(s))
      .sort((a, b) => lateOf(b) - lateOf(a) || progressOf(a.status) - progressOf(b.status));
  }, [data, stage, project, who, q, lateOnly]);

  if (!data)
    return (
      <>
        <PageHeader title={tr('Production')} />
        <Spinner />
      </>
    );
  const people = [
    ...new Set(data.items.flatMap(i => (i.production || []).map(s => s.assignee)).filter(Boolean)),
  ].sort();
  const lateCount = data.items.filter(lateOf).length;
  const filtered = stage || project || who || q || lateOnly;

  return (
    <>
      <PageHeader
        title={tr('Production')}
        sub={[
          trn(
            data.items.filter(i => !['published', 'completed'].includes(i.status)).length,
            '{n} piece in progress',
            '{n} pieces in progress',
          ),
          lateCount ? tr('{n} late', { n: lateCount }) : null,
        ]
          .filter(Boolean)
          .join(', ')}
        actions={
          <>
            <div className="seg" role="group" aria-label={tr('View')}>
              <button aria-pressed={view === 'timeline'} onClick={() => setParam('view', '')}>
                {tr('Timeline')}
              </button>
              <button aria-pressed={view === 'board'} onClick={() => setParam('view', 'board')}>
                {tr('Board')}
              </button>
            </div>
            <button onClick={() => setParam('new', '1')} className="btn btn-primary">
              <Plus /> {tr('New content')}
            </button>
          </>
        }
      />

      <div className="flex flex-wrap items-center gap-2 mb-4">
        <label className="relative flex-1 min-w-[200px] max-w-xs">
          <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-mist" />
          <input
            value={q}
            onChange={e => setParam('q', e.target.value)}
            placeholder={tr('Find content')}
            className="field pl-9"
            aria-label={tr('Find content')}
          />
        </label>
        <select
          value={project}
          onChange={e => setParam('project', e.target.value)}
          className="field w-auto"
          aria-label={tr('Project')}
        >
          <option value="">{tr('All projects')}</option>
          {data.projects.map(p => (
            <option key={p.id} value={p.id}>
              {p.name}
            </option>
          ))}
        </select>
        <select
          value={who}
          onChange={e => setParam('who', e.target.value)}
          className="field w-auto"
          aria-label={tr('Person')}
        >
          <option value="">{tr('Everyone')}</option>
          {people.map(n => (
            <option key={n}>{n}</option>
          ))}
        </select>
        <button
          onClick={() => setParam('late', lateOnly ? '' : '1')}
          aria-pressed={lateOnly}
          className={`btn ${lateOnly ? 'btn-danger' : 'btn-quiet'}`}
        >
          {tr('Late')}
          {lateCount ? ` (${lateCount})` : ''}
        </button>
        {filtered && (
          <button
            onClick={() => setParams({ ...(view === 'board' ? { view: 'board' } : {}) }, { replace: true })}
            className="btn btn-ghost"
          >
            {tr('Clear filters')}
          </button>
        )}
      </div>

      {view === 'timeline' ? (
        <section className="panel overflow-hidden @container">
          <div className="hidden @[880px]:grid grid-cols-[minmax(220px,280px)_1fr] gap-x-6 px-5 py-3 border-b border-hairline bg-haze/50">
            <span className="text-[13px] font-semibold text-graphite">
              {trn(items.length, '{n} item', '{n} items')}
            </span>
            <div className="grid grid-cols-5">
              {STAGES.map(s => (
                <button
                  key={s.key}
                  onClick={() => setParam('stage', stage === s.key ? '' : s.key)}
                  aria-pressed={stage === s.key}
                  className={`flex items-center gap-1.5 min-w-0 text-[13px] font-semibold pl-2 text-left ${stage && stage !== s.key ? 'text-mist' : 'text-ink'}`}
                >
                  <span className="w-3 h-3 rounded-[3px] shrink-0" style={{ background: s.color }} />
                  <span className="truncate" title={s.label}>
                    {s.label}
                  </span>
                </button>
              ))}
            </div>
          </div>
          <div className="@[880px]:hidden flex gap-1.5 px-4 py-3 border-b border-hairline scroll-x">
            {STAGES.map(s => (
              <button
                key={s.key}
                onClick={() => setParam('stage', stage === s.key ? '' : s.key)}
                aria-pressed={stage === s.key}
                className={`btn btn-sm shrink-0 ${stage === s.key ? 'btn-primary' : 'btn-quiet'}`}
              >
                <span className="w-2.5 h-2.5 rounded-[2px]" style={{ background: s.color }} />
                {s.label}
              </button>
            ))}
          </div>
          {items.length === 0 ? (
            <Empty
              title={filtered ? tr('Nothing matches these filters') : tr('No content yet')}
              action={
                !filtered && (
                  <button onClick={() => setParam('new', '1')} className="btn btn-primary">
                    <Plus /> {tr('New content')}
                  </button>
                )
              }
            >
              {filtered
                ? tr('Try another stage or person, or clear the filters.')
                : tr('Add the first piece of content to start planning.')}
            </Empty>
          ) : (
            <ul className="relative">
              {items.map(i => (
                <Track key={i.id} item={i} onChange={setChanging} />
              ))}
            </ul>
          )}
        </section>
      ) : (
        <div className="flex xl:grid xl:grid-cols-5 gap-3 scroll-x snap-x snap-mandatory xl:snap-none -mx-4 px-4 sm:mx-0 sm:px-0 pb-2">
          {STAGES.map(s => (
            <BoardColumn key={s.key} stage={s} items={items.filter(i => stageOf(i.status).key === s.key)} />
          ))}
        </div>
      )}

      <section className="mt-8">
        <div className="flex flex-wrap items-end justify-between gap-3 mb-3">
          <div>
            <h2 className="text-[17px] font-semibold flex items-center gap-2">
              <ListTodo size={18} /> {tr('Other orders')}
            </h2>
            <p className="text-graphite text-[14px]">
              {tr('One-off jobs that aren’t tied to a piece of content, like a location scout.')}
            </p>
          </div>
          <button onClick={() => setParam('order', 'new')} className="btn btn-quiet">
            <Plus /> {tr('New order')}
          </button>
        </div>
        {data.other.length > 0 && (
          <ul className="panel divide-y divide-hairline">
            {data.other.map(t => (
              <li key={t.id} className="flex flex-wrap items-center gap-x-4 gap-y-1 px-4 sm:px-5 py-3">
                <Link to={`/orders/${t.id}`} className="flex-1 min-w-[200px]">
                  <span className="block font-semibold hover:underline underline-offset-2">{t.title}</span>
                  <span className="block text-[13px] text-graphite">
                    {t.project_name}, {t.assigned_to_name || tr('nobody yet')}
                  </span>
                </Link>
                <span className="text-[13px] text-graphite">{ORDER_TEXT[t.status]}</span>
                <Due date={t.due_date} done={['completed', 'waiting_for_review'].includes(t.status)} />
                {!['completed', 'cancelled'].includes(t.status) && (
                  <button
                    onClick={() => setChanging({ production: [{ task: t.id, status: t.status }] })}
                    className="btn btn-quiet btn-sm"
                  >
                    <PencilLine /> {tr('Change')}
                  </button>
                )}
              </li>
            ))}
          </ul>
        )}
      </section>

      {changing && (
        <ChangeOrders
          taskIds={(changing.production || [])
            .filter(s => !['completed', 'cancelled'].includes(s.status))
            .map(s => s.task)}
          onClose={() => setChanging(null)}
          onSaved={reload}
        />
      )}
      {params.get('order') === 'new' && (
        <NewOrder projects={data.projects} users={data.users} onClose={() => setParam('order', '')} onSaved={reload} />
      )}
      {params.get('new') === '1' && (
        <NewContent projects={data.projects} preset={project} onClose={() => setParam('new', '')} />
      )}
    </>
  );
}

function NewOrder({ projects, users, onClose, onSaved }) {
  const toast = useToast();
  const [form, setForm] = useState({
    title: '',
    project: projects.find(p => p.status === 'active')?.id || '',
    assigned_to: '',
    due_date: '',
    description: '',
  });
  const [error, setError] = useState('');
  const set = k => e => setForm(f => ({ ...f, [k]: e.target.value }));
  const save = async e => {
    e.preventDefault();
    setError('');
    try {
      await api.post('tasks/', {
        ...form,
        task_type: 'Other',
        stage: 'other',
        assigned_to: form.assigned_to || null,
        due_date: form.due_date ? new Date(form.due_date).toISOString() : null,
      });
      toast(tr('Order created — they’ve been notified'));
      onSaved();
      onClose();
    } catch (err) {
      setError(errorText(err));
    }
  };
  return (
    <Dialog
      title={tr('New order')}
      sub={tr('A one-off job for one person.')}
      onClose={onClose}
      footer={
        <>
          <button onClick={onClose} className="btn btn-ghost">
            {tr('Cancel')}
          </button>
          <button form="no" disabled={!form.title.trim() || !form.project} className="btn btn-primary">
            {tr('Create order')}
          </button>
        </>
      }
    >
      <form id="no" onSubmit={save} className="space-y-4">
        {error && (
          <p role="alert" className="text-tally">
            {error}
          </p>
        )}
        <div>
          <label className="label" htmlFor="no-t">
            {tr('What needs doing')}
          </label>
          <input
            id="no-t"
            className="field"
            value={form.title}
            onChange={set('title')}
            placeholder={tr('e.g. Scout a location for the Atlas shoot')}
            required
          />
        </div>
        <div className="grid sm:grid-cols-2 gap-3">
          <div>
            <label className="label" htmlFor="no-p">
              {tr('Project')}
            </label>
            <select id="no-p" className="field" value={form.project} onChange={set('project')}>
              {projects
                .filter(p => p.status !== 'archived')
                .map(p => (
                  <option key={p.id} value={p.id}>
                    {p.name}
                  </option>
                ))}
            </select>
          </div>
          <div>
            <label className="label" htmlFor="no-w">
              {tr('Who')}
            </label>
            <select id="no-w" className="field" value={form.assigned_to} onChange={set('assigned_to')}>
              <option value="">{tr('Nobody yet')}</option>
              {users
                .filter(u => u.is_active && ['VIDEOGRAPHER', 'EDITOR'].includes(u.role))
                .map(u => (
                  <option key={u.id} value={u.id}>
                    {u.full_name || u.username}
                  </option>
                ))}
            </select>
          </div>
        </div>
        <div>
          <label className="label" htmlFor="no-d">
            {tr('Deadline')}
          </label>
          <input id="no-d" type="datetime-local" className="field" value={form.due_date} onChange={set('due_date')} />
        </div>
        <div>
          <label className="label" htmlFor="no-i">
            {tr('Instructions')} <span className="font-normal text-mist">{tr('(optional)')}</span>
          </label>
          <textarea id="no-i" rows={3} className="field" value={form.description} onChange={set('description')} />
        </div>
      </form>
    </Dialog>
  );
}
