import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { Check, Plus, Trash2, LayoutTemplate } from 'lucide-react';
import api, { errorText, list } from '../lib/api';
import { ago, day } from '../lib/format';
import { Dialog, Empty, PageHeader, Spinner } from '../ui';
import { useToast, useConfirm } from '../lib/hooks';
import { TodoDialog } from './Calendar';
import NoteEditor from '../features/NoteEditor';
import { PAGE_TEMPLATES } from '../lib/pageTemplates';
import { useAuth } from '../lib/auth';
import { tr } from '../lib/i18n';

const ymd = d =>
  `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
const PRIO = { 1: 'var(--color-tally)', 2: 'var(--color-shoot)', 3: 'var(--color-review)', 4: 'transparent' };

export default function Workspace() {
  const [params, setParams] = useSearchParams();
  const tab = params.get('tab') === 'notes' ? 'notes' : 'todos';
  return (
    <>
      <PageHeader
        title={tr('Notes & to-dos')}
        sub={tr('The small things that aren’t an order: reminders, ideas, meeting notes.')}
        actions={
          <div className="seg" role="group" aria-label={tr('Section')}>
            <button aria-pressed={tab === 'todos'} onClick={() => setParams({})}>
              {tr('To-dos')}
            </button>
            <button aria-pressed={tab === 'notes'} onClick={() => setParams({ tab: 'notes' })}>
              {tr('Notes')}
            </button>
          </div>
        }
      />
      {tab === 'todos' ? <Todos /> : <Notes />}
    </>
  );
}

function Todos() {
  const [todos, setTodos] = useState(null);
  const [view, setView] = useState('today');
  const [title, setTitle] = useState('');
  const [due, setDue] = useState(() => ymd(new Date()));
  const [editing, setEditing] = useState(null);
  const load = useCallback(
    () =>
      api
        .get('workspace-todos/', { params: { view: 'mine' } })
        .then(list)
        .then(setTodos)
        .catch(() => setTodos([])),
    [],
  );
  useEffect(() => {
    load();
  }, [load]);
  const today = ymd(new Date());

  const groups = useMemo(() => {
    const open = (todos || []).filter(t => !t.completed);
    if (view === 'today')
      return [
        [tr('Late'), open.filter(t => t.due_date && t.due_date < today), true],
        [tr('Today'), open.filter(t => t.due_date === today)],
      ];
    if (view === 'upcoming') {
      const m = {};
      open
        .filter(t => t.due_date > today)
        .sort((a, b) => a.due_date.localeCompare(b.due_date))
        .forEach(t => (m[t.due_date] ||= []).push(t));
      return Object.entries(m).map(([d, ts]) => [day(d), ts]);
    }
    return [
      [tr('No date'), open.filter(t => !t.due_date)],
      [tr('Done'), (todos || []).filter(t => t.completed).slice(0, 15)],
    ];
  }, [todos, view, today]);

  const add = async e => {
    e.preventDefault();
    if (!title.trim()) return;
    await api.post('workspace-todos/', { title: title.trim(), due_date: due || null }).catch(() => {});
    setTitle('');
    load();
  };
  const toggle = async t => {
    setTodos(ts => ts.map(x => (x.id === t.id ? { ...x, completed: !x.completed } : x)));
    await api.patch(`workspace-todos/${t.id}/`, { completed: !t.completed }).catch(load);
  };

  return (
    <div className="max-w-3xl">
      <div className="seg mb-5" role="group" aria-label={tr('Show')}>
        {[
          ['today', tr('Today')],
          ['upcoming', tr('Upcoming')],
          ['all', tr('No date & done')],
        ].map(([k, l]) => (
          <button
            key={k}
            aria-pressed={view === k}
            onClick={() => {
              setView(k);
              const d = new Date();
              if (k === 'upcoming') d.setDate(d.getDate() + 1);
              setDue(k === 'all' ? '' : ymd(d));
            }}
          >
            {l}
          </button>
        ))}
      </div>
      <form onSubmit={add} className="flex flex-wrap sm:flex-nowrap gap-2 mb-6">
        <input
          value={title}
          onChange={e => setTitle(e.target.value)}
          className="field h-12 flex-1 min-w-0 basis-full sm:basis-auto"
          placeholder={tr('Add a to-do')}
          aria-label={tr('New to-do')}
        />
        <label className="relative flex-1 sm:flex-none">
          <span className="sr-only">{tr('Due date')}</span>
          <input
            type="date"
            value={due}
            onChange={e => setDue(e.target.value)}
            className="field h-12 sm:w-44"
            aria-label={tr('Due date')}
          />
        </label>
        {due && (
          <button type="button" onClick={() => setDue('')} className="btn btn-ghost h-12" title={tr('No date')}>
            {tr('No date')}
          </button>
        )}
        <button disabled={!title.trim()} className="btn btn-primary h-12">
          <Plus /> {tr('Add')}
        </button>
      </form>
      {todos === null ? (
        <Spinner />
      ) : groups.every(([, ts]) => ts.length === 0) ? (
        <p className="panel p-8 text-center text-graphite">
          {view === 'today' ? tr('Nothing for today. Add one above, or enjoy it.') : tr('Nothing here.')}
        </p>
      ) : (
        groups.map(
          ([label, ts, late]) =>
            ts.length > 0 && (
              <section key={label} className="mb-6">
                <h2 className={`text-[14px] font-semibold mb-2 ${late ? 'text-tally' : 'text-graphite'}`}>{label}</h2>
                <ul className="panel divide-y divide-hairline overflow-hidden">
                  {ts.map(t => (
                    <li key={t.id} className="flex items-center gap-3 px-4 py-3">
                      <button
                        onClick={() => toggle(t)}
                        aria-pressed={t.completed}
                        aria-label={`${t.completed ? tr('Reopen') : tr('Complete')}: ${t.title}`}
                        className={`w-5 h-5 rounded-full border-2 flex items-center justify-center shrink-0 ${t.completed ? 'bg-ink border-ink text-paper' : ''}`}
                        style={
                          !t.completed
                            ? {
                                borderColor:
                                  PRIO[t.priority] === 'transparent' ? 'var(--color-mist)' : PRIO[t.priority],
                              }
                            : {}
                        }
                      >
                        {t.completed && <Check size={12} strokeWidth={3} />}
                      </button>
                      <button onClick={() => setEditing(t.id)} className="min-w-0 flex-1 text-left">
                        <span className={`block truncate ${t.completed ? 'line-through text-mist' : ''}`}>
                          {t.title}
                        </span>
                        {(t.project_name || t.assignee_name) && (
                          <span className="block text-[13px] text-graphite truncate">
                            {[t.project_name, t.assignee_name && `for ${t.assignee_name}`].filter(Boolean).join(', ')}
                          </span>
                        )}
                      </button>
                    </li>
                  ))}
                </ul>
              </section>
            ),
        )
      )}
      {editing && <TodoDialog id={editing} onClose={() => setEditing(null)} onSaved={load} />}
    </div>
  );
}

function Notes() {
  const toast = useToast();
  const confirm = useConfirm();
  const me = useAuth(st => st.user);
  const [pages, setPages] = useState(null);
  const [openId, setOpenId] = useState(null);
  const [draft, setDraft] = useState(null);
  const [picking, setPicking] = useState(false);
  const [saveAs, setSaveAs] = useState(false);
  const timer = useRef(null);
  const load = useCallback(
    () =>
      api
        .get('workspace-pages/')
        .then(list)
        .then(ps => {
          setPages(ps);
          return ps;
        })
        .catch(() => setPages([])),
    [],
  );
  useEffect(() => {
    load();
  }, [load]);
  const openNote = p => {
    setOpenId(p?.id ?? null);
    setDraft(p ? { title: p.title, body: p.body } : null);
  };

  const create = async ({ title, body, project }) => {
    try {
      const { data } = await api.post('workspace-pages/', { title, body, project: project || null });
      await load();
      openNote(data);
      setPicking(false);
    } catch (err) {
      toast(errorText(err), 'error');
    }
  };
  const edit = patch => {
    setDraft(d => ({ ...d, ...patch }));
    clearTimeout(timer.current);
    timer.current = setTimeout(
      () =>
        api
          .patch(`workspace-pages/${openId}/`, patch)
          .then(load)
          .catch(() => {}),
      700,
    );
  };
  const remove = async () => {
    if (
      !(await confirm({
        title: tr('Delete this note?'),
        body: tr('It can’t be brought back.'),
        action: tr('Delete note'),
        danger: true,
      }))
    )
      return;
    await api.delete(`workspace-pages/${openId}/`).catch(() => {});
    openNote(null);
    load();
  };
  const open = pages?.find(p => p.id === openId);

  if (!pages) return <Spinner />;
  return (
    <div className="grid md:grid-cols-[280px_1fr] gap-6 items-start">
      <section className={`panel overflow-hidden ${openId ? 'hidden md:block' : ''}`}>
        <div className="p-3 border-b border-hairline">
          <button onClick={() => setPicking(true)} className="btn btn-primary w-full">
            <Plus /> {tr('New note')}
          </button>
        </div>
        {pages.length === 0 ? (
          <p className="p-5 text-[14px] text-graphite">
            {tr('No notes yet. Start from a template — meeting notes, shoot plans, briefs.')}
          </p>
        ) : (
          <ul className="max-h-[65vh] overflow-y-auto">
            {pages.map(p => (
              <li key={p.id}>
                <button
                  onClick={() => openNote(p)}
                  className={`w-full text-left flex gap-3 px-4 py-3 ${p.id === openId ? 'bg-haze' : 'hover:bg-haze/60'}`}
                >
                  <span className="w-5 text-center shrink-0" aria-hidden>
                    {p.icon || '📄'}
                  </span>
                  <span className="min-w-0">
                    <span className="block font-medium truncate">{p.title}</span>
                    <span className="block text-[12px] text-mist truncate">
                      {p.project_name || tr('Private')}, {ago(p.updated_at)}
                    </span>
                  </span>
                </button>
              </li>
            ))}
          </ul>
        )}
      </section>
      <section className={`panel p-5 sm:p-8 min-h-[60vh] min-w-0 ${openId ? '' : 'hidden md:block'}`}>
        {!draft ? (
          <Empty
            title={tr('Pick a note or start a new one')}
            action={
              <button onClick={() => setPicking(true)} className="btn btn-quiet">
                <Plus /> {tr('New note')}
              </button>
            }
          >
            {tr('Notes save as you type. Project notes are shared with that project’s team.')}
          </Empty>
        ) : (
          <>
            <div className="flex flex-wrap items-center justify-between gap-2 mb-2">
              <button onClick={() => openNote(null)} className="btn btn-ghost btn-sm -ml-3 md:hidden">
                {tr('All notes')}
              </button>
              <span className="text-[12px] text-mist">
                {open?.project_name ? tr('Shared with {name}', { name: open.project_name }) : tr('Private')}
                {tr(', saves automatically')}
              </span>
              <span className="flex gap-1 ml-auto">
                <button onClick={() => setSaveAs(true)} className="btn btn-ghost btn-sm">
                  <LayoutTemplate size={15} /> {tr('Save as template')}
                </button>
                <button onClick={remove} className="btn-icon" aria-label={tr('Delete note')}>
                  <Trash2 size={16} />
                </button>
              </span>
            </div>
            <textarea
              rows={1}
              value={draft.title}
              onChange={e => edit({ title: e.target.value.replace(/\n/g, ' ') })}
              onKeyDown={e => e.key === 'Enter' && e.preventDefault()}
              className="w-full display text-[26px] leading-tight font-semibold bg-transparent outline-none mb-3 resize-none [field-sizing:content]"
              aria-label={tr('Title')}
            />
            <NoteEditor key={openId} value={draft.body} onChange={body => edit({ body })} />
          </>
        )}
      </section>
      {picking && <TemplatePicker me={me} onPick={create} onClose={() => setPicking(false)} />}
      {saveAs && (
        <SaveTemplate
          body={draft.body}
          title={draft.title}
          onClose={() => setSaveAs(false)}
          onSaved={() => toast(tr('Saved as a template — the whole team can use it'))}
        />
      )}
    </div>
  );
}

const TemplateCard = ({ icon, name, description, onClick, extra }) => (
  <div className="relative">
    <button
      onClick={onClick}
      className="w-full h-full text-left rounded-[12px] border border-hairline p-4 hover:border-ink transition-colors"
    >
      <span className="text-[20px]" aria-hidden>
        {icon}
      </span>
      <span className="block font-semibold mt-1.5">{name}</span>
      {description && <span className="block text-[13px] text-graphite mt-0.5 line-clamp-2">{description}</span>}
    </button>
    {extra}
  </div>
);

function TemplatePicker({ me, onPick, onClose }) {
  const confirm = useConfirm();
  const [custom, setCustom] = useState(null);
  const [projects, setProjects] = useState([]);
  const [where, setWhere] = useState('');
  const load = useCallback(
    () =>
      api
        .get('templates/', { params: { type: 'note' } })
        .then(list)
        .then(setCustom)
        .catch(() => setCustom([])),
    [],
  );
  useEffect(() => {
    load();
    api
      .get('projects/')
      .then(list)
      .then(ps => setProjects(ps.filter(p => p.status === 'active')))
      .catch(() => {});
  }, [load]);
  const remove = async t => {
    if (
      !(await confirm({
        title: tr('Delete the “{name}” template?', { name: t.name }),
        body: tr('Notes made from it stay as they are.'),
        action: tr('Delete template'),
        danger: true,
      }))
    )
      return;
    await api.delete(`templates/${t.id}/`).catch(() => {});
    load();
  };
  return (
    <Dialog title={tr('New note')} sub={tr('Start blank or from a template.')} onClose={onClose} wide>
      <label className="label" htmlFor="tp-w">
        {tr('Who can see it')}
      </label>
      <select id="tp-w" className="field mb-5" value={where} onChange={e => setWhere(e.target.value)}>
        <option value="">{tr('Only me')}</option>
        {projects.map(p => (
          <option key={p.id} value={p.id}>
            {tr('Team of {name}', { name: p.name })}
          </option>
        ))}
      </select>
      <div className="grid sm:grid-cols-2 gap-2.5">
        <TemplateCard
          icon="📄"
          name={tr('Blank note')}
          description={tr('An empty page.')}
          onClick={() => onPick({ title: tr('Untitled note'), body: '', project: where })}
        />
        {PAGE_TEMPLATES.map(t => (
          <TemplateCard
            key={t.id}
            icon={t.icon}
            name={t.name}
            description={t.description}
            onClick={() => onPick({ title: t.name, body: t.body.replace(/^# .*\n+/, ''), project: where })}
          />
        ))}
      </div>
      <h3 className="font-semibold mt-6 mb-2">{tr('Your team’s templates')}</h3>
      {custom === null ? (
        <Spinner />
      ) : custom.length === 0 ? (
        <p className="text-[14px] text-graphite">{tr('None yet. Open any note and choose “Save as template”.')}</p>
      ) : (
        <div className="grid sm:grid-cols-2 gap-2.5">
          {custom.map(t => (
            <TemplateCard
              key={t.id}
              icon="⭐"
              name={t.name}
              description={tr('By {name}', { name: t.created_by_name || tr('someone') })}
              onClick={() => onPick({ title: t.name, body: t.content_json_or_text, project: where })}
              extra={
                (t.created_by === me.id || me.role === 'OWNER') && (
                  <button
                    onClick={() => remove(t)}
                    className="btn-icon w-8 h-8 absolute top-2 right-2"
                    aria-label={tr('Delete template {name}', { name: t.name })}
                  >
                    <Trash2 size={14} />
                  </button>
                )
              }
            />
          ))}
        </div>
      )}
    </Dialog>
  );
}

function SaveTemplate({ title, body, onClose, onSaved }) {
  const toast = useToast();
  const [name, setName] = useState(title || '');
  const save = async e => {
    e.preventDefault();
    try {
      await api.post('templates/', { name: name.trim(), type: 'note', content_json_or_text: body });
      onSaved();
      onClose();
    } catch (err) {
      toast(errorText(err), 'error');
    }
  };
  return (
    <Dialog
      title={tr('Save as template')}
      sub={tr('Your team will find it under “New note”.')}
      onClose={onClose}
      footer={
        <>
          <button onClick={onClose} className="btn btn-ghost">
            {tr('Cancel')}
          </button>
          <button form="st" disabled={!name.trim()} className="btn btn-primary">
            {tr('Save template')}
          </button>
        </>
      }
    >
      <form id="st" onSubmit={save}>
        <label className="label" htmlFor="st-n">
          {tr('Template name')}
        </label>
        <input id="st-n" className="field" value={name} onChange={e => setName(e.target.value)} autoFocus />
      </form>
    </Dialog>
  );
}
