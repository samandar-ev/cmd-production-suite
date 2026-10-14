import { useMemo, useState } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import { Plus, Search, ChevronRight } from 'lucide-react';
import api, { errorText, list } from '../lib/api';
import { useAuth, isManager, nameOf } from '../lib/auth';
import { PROJECT_STATUS, STAGES, stageOf } from '../lib/stages';
import { day } from '../lib/format';
import { Avatar, Dialog, Empty, PageHeader, Spinner } from '../ui';
import { useLoad, useToast } from '../lib/hooks';
import { tr } from '../lib/i18n';

async function load(manager) {
  const [projects, items] = await Promise.all([
    api.get('projects/').then(list),
    manager ? api.get('content-items/').then(list) : [],
  ]);
  return { projects, items };
}

export function StageStrip({ items }) {
  const live = items.filter(i => i.status !== 'completed');
  if (!live.length) return <span className="text-[13px] text-mist">{tr('No content yet')}</span>;
  const n = STAGES.map(s => ({ ...s, n: live.filter(i => stageOf(i.status).key === s.key).length }));
  return (
    <span className="flex items-center gap-2" title={n.map(s => `${s.label}: ${s.n}`).join(', ')}>
      <span className="flex h-2 w-28 rounded-full overflow-hidden bg-haze gap-px">
        {n
          .filter(s => s.n)
          .map(s => (
            <span key={s.key} style={{ flex: s.n, background: s.color }} />
          ))}
      </span>
      <span className="text-[13px] text-graphite num">{live.length}</span>
    </span>
  );
}

export default function Projects() {
  const user = useAuth(s => s.user);
  const manager = isManager(user);
  const navigate = useNavigate();
  const [params, setParams] = useSearchParams();
  const status = params.get('status') || 'active';
  const [q, setQ] = useState('');
  const { data, reload } = useLoad(() => load(manager), [manager]);

  const rows = useMemo(() => {
    if (!data) return [];
    const s = q.trim().toLowerCase();
    return data.projects
      .filter(p => (manager ? p.status === status : true))
      .filter(p => !s || `${p.name} ${p.client_name}`.toLowerCase().includes(s));
  }, [data, status, q, manager]);

  if (!data)
    return (
      <>
        <PageHeader title={tr('Projects')} />
        <Spinner />
      </>
    );
  const count = k => data.projects.filter(p => p.status === k).length;

  return (
    <>
      <PageHeader
        title={tr('Projects')}
        sub={manager ? tr('{n} active', { n: count('active') }) : tr('Projects you’re working on')}
        actions={
          manager && (
            <button onClick={() => setParams({ status, new: '1' })} className="btn btn-primary">
              <Plus /> {tr('New project')}
            </button>
          )
        }
      />
      {manager && (
        <div className="flex flex-wrap items-center gap-2 mb-4">
          <div className="seg scroll-x max-w-full" role="group" aria-label={tr('Status')}>
            {PROJECT_STATUS.filter(([k]) => k === 'active' || count(k)).map(([k, l]) => (
              <button key={k} aria-pressed={status === k} onClick={() => setParams({ status: k })}>
                {l} <span className="num text-mist">{count(k)}</span>
              </button>
            ))}
          </div>
          <label className="relative flex-1 min-w-[180px] max-w-xs ml-auto">
            <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-mist" />
            <input
              value={q}
              onChange={e => setQ(e.target.value)}
              className="field pl-9"
              placeholder={tr('Find a project')}
              aria-label={tr('Find a project')}
            />
          </label>
        </div>
      )}
      <section className="panel overflow-hidden">
        {rows.length === 0 ? (
          <Empty title={q ? tr('No project matches “{q}”', { q }) : tr('No projects here')}>
            {manager && !q && tr('Start one with “New project”.')}
          </Empty>
        ) : (
          <ul className="divide-y divide-hairline">
            {rows.map(p => (
              <li key={p.id}>
                <Link
                  to={`/projects/${p.id}`}
                  className="grid sm:grid-cols-[1fr_auto_auto] items-center gap-x-6 gap-y-1.5 px-4 sm:px-5 py-4 hover:bg-haze"
                >
                  <span className="min-w-0">
                    <span className="block font-semibold truncate">{p.name}</span>
                    <span className="block text-[13px] text-graphite truncate">
                      {p.client_name}
                      {p.end_date ? `, ${tr('until {date}', { date: day(p.end_date) })}` : ''}
                    </span>
                  </span>
                  {manager && <StageStrip items={data.items.filter(i => i.project === p.id)} />}
                  <span className="flex items-center gap-2 text-[13px] text-graphite">
                    <Avatar name={p.project_manager_name} size={22} />
                    {p.project_manager_name || tr('No manager')}
                    <ChevronRight size={16} className="text-mist hidden sm:block" />
                  </span>
                </Link>
              </li>
            ))}
          </ul>
        )}
      </section>
      {params.get('new') === '1' && (
        <ProjectForm
          onClose={() => setParams({ status })}
          onSaved={p => {
            reload();
            navigate(`/projects/${p.id}`);
          }}
        />
      )}
    </>
  );
}

export function ProjectForm({ project, onClose, onSaved }) {
  const toast = useToast();
  const owner = useAuth(s => s.user)?.role === 'OWNER';
  const { data } = useLoad(() => Promise.all([api.get('clients/').then(list), api.get('users/').then(list)]), []);
  const [form, setForm] = useState(() => ({
    name: project?.name || '',
    client: project?.client || '',
    project_manager: project?.project_manager || '',
    status: project?.status || 'active',
    start_date: project?.start_date || '',
    end_date: project?.end_date || '',
    service_fee: project?.service_fee ?? '',
    goals: project?.goals || '',
    deliverables_summary: project?.deliverables_summary || '',
  }));
  const [newClient, setNewClient] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const set = k => e => setForm(f => ({ ...f, [k]: e.target.value }));
  const save = async e => {
    e.preventDefault();
    setBusy(true);
    setError('');
    try {
      let client = form.client;
      if (newClient) client = (await api.post('clients/', newClient)).data.id;
      const body = {
        ...form,
        client,
        project_manager: form.project_manager || null,
        start_date: form.start_date || null,
        end_date: form.end_date || null,
        service_fee: form.service_fee === '' ? null : form.service_fee,
      };
      if (!owner) delete body.service_fee;
      const { data: saved } = project
        ? await api.patch(`projects/${project.id}/`, body)
        : await api.post('projects/', body);
      toast(project ? tr('Project updated') : tr('Project created'));
      onClose();
      onSaved?.(saved);
    } catch (err) {
      setError(errorText(err));
    } finally {
      setBusy(false);
    }
  };
  const [clients, users] = data || [[], []];
  return (
    <Dialog
      title={project ? tr('Edit project') : tr('New project')}
      onClose={onClose}
      wide
      footer={
        <>
          <button onClick={onClose} className="btn btn-ghost">
            {tr('Cancel')}
          </button>
          <button
            form="pf"
            disabled={busy || !form.name.trim() || (!form.client && !newClient?.client_name)}
            className="btn btn-primary"
          >
            {busy ? tr('Saving…') : project ? tr('Save changes') : tr('Create project')}
          </button>
        </>
      }
    >
      <form id="pf" onSubmit={save} className="grid sm:grid-cols-2 gap-4">
        {error && (
          <p role="alert" className="text-tally sm:col-span-2">
            {error}
          </p>
        )}
        <div className="sm:col-span-2">
          <label className="label" htmlFor="pf-n">
            {tr('Project name')}
          </label>
          <input
            id="pf-n"
            className="field"
            value={form.name}
            onChange={set('name')}
            placeholder={tr('e.g. Autumn menu launch')}
            required
          />
        </div>
        <div className="sm:col-span-2">
          <label className="label" htmlFor="pf-c">
            {tr('Client')}
          </label>
          {newClient ? (
            <div className="grid sm:grid-cols-2 gap-3 p-3 rounded-[10px] bg-haze">
              <input
                className="field"
                placeholder={tr('Company name')}
                aria-label={tr('Company name')}
                value={newClient.client_name}
                onChange={e => setNewClient(c => ({ ...c, client_name: e.target.value }))}
              />
              <input
                className="field"
                placeholder={tr('Contact person')}
                aria-label={tr('Contact person')}
                value={newClient.contact_person}
                onChange={e => setNewClient(c => ({ ...c, contact_person: e.target.value }))}
              />
              <button
                type="button"
                onClick={() => setNewClient(null)}
                className="btn btn-ghost btn-sm justify-self-start"
              >
                {tr('Choose an existing client instead')}
              </button>
            </div>
          ) : (
            <div className="flex gap-2">
              <select id="pf-c" className="field" value={form.client} onChange={set('client')}>
                <option value="">{tr('Choose a client…')}</option>
                {clients.map(c => (
                  <option key={c.id} value={c.id}>
                    {c.client_name}
                  </option>
                ))}
              </select>
              {owner && (
                <button
                  type="button"
                  onClick={() => setNewClient({ client_name: '', contact_person: '' })}
                  className="btn btn-quiet shrink-0"
                >
                  <Plus /> {tr('New')}
                </button>
              )}
            </div>
          )}
        </div>
        <div>
          <label className="label" htmlFor="pf-pm">
            {tr('Project manager')}
          </label>
          <select id="pf-pm" className="field" value={form.project_manager} onChange={set('project_manager')}>
            <option value="">{tr('Nobody yet')}</option>
            {users
              .filter(u => ['OWNER', 'PROJECT_MANAGER'].includes(u.role) && u.is_active)
              .map(u => (
                <option key={u.id} value={u.id}>
                  {nameOf(u)}
                </option>
              ))}
          </select>
        </div>
        <div>
          <label className="label" htmlFor="pf-s">
            {tr('Status')}
          </label>
          <select id="pf-s" className="field" value={form.status} onChange={set('status')}>
            {PROJECT_STATUS.map(([k, l]) => (
              <option key={k} value={k}>
                {l}
              </option>
            ))}
          </select>
        </div>
        <div>
          <label className="label" htmlFor="pf-sd">
            {tr('Starts')}
          </label>
          <input id="pf-sd" type="date" className="field" value={form.start_date || ''} onChange={set('start_date')} />
        </div>
        <div>
          <label className="label" htmlFor="pf-ed">
            {tr('Ends')}
          </label>
          <input id="pf-ed" type="date" className="field" value={form.end_date || ''} onChange={set('end_date')} />
        </div>
        {owner && (
          <div>
            <label className="label" htmlFor="pf-f">
              {tr('Agreed fee, USD')}
            </label>
            <input
              id="pf-f"
              type="number"
              min="0"
              step="1"
              className="field num"
              value={form.service_fee}
              onChange={set('service_fee')}
              placeholder="0"
            />
          </div>
        )}
        <div className="sm:col-span-2">
          <label className="label" htmlFor="pf-g">
            {tr('Goals')}
          </label>
          <textarea
            id="pf-g"
            rows={2}
            className="field"
            value={form.goals}
            onChange={set('goals')}
            placeholder={tr('What the client wants to achieve')}
          />
        </div>
        <div className="sm:col-span-2">
          <label className="label" htmlFor="pf-d">
            {tr('What we deliver')}
          </label>
          <textarea
            id="pf-d"
            rows={2}
            className="field"
            value={form.deliverables_summary}
            onChange={set('deliverables_summary')}
            placeholder={tr('e.g. 8 reels and 4 stories a month')}
          />
        </div>
      </form>
    </Dialog>
  );
}
