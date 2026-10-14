import { useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { ChevronRight, PencilLine, Plus, Eye, EyeOff, Trash2, Archive, ArchiveRestore } from 'lucide-react';
import api, { errorText, list } from '../lib/api';
import { useAuth, isManager } from '../lib/auth';
import { ORDER_TEXT, PROJECT_STATUS_TEXT as STATUS_TEXT, STAGES } from '../lib/stages';
import { day, money } from '../lib/format';
import { Avatar, Due, Empty, Spinner } from '../ui';
import { useConfirm, useLoad, useToast } from '../lib/hooks';
import { Track } from './Production';
import { ProjectForm, StageStrip } from './Projects';
import ChangeOrders from '../features/ChangeOrders';
import NewContent from '../features/NewContent';
import { tr } from '../lib/i18n';

async function load(id, manager) {
  const [project, tasks, items] = await Promise.all([
    api.get(`projects/${id}/`).then(r => r.data),
    api.get('tasks/', { params: { project: id } }).then(list),
    manager ? api.get('content-items/', { params: { project: id } }).then(list) : [],
  ]);
  return { project, tasks, items };
}

export default function ProjectPage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const toast = useToast();
  const user = useAuth(s => s.user);
  const manager = isManager(user);
  const { data, reload, error } = useLoad(() => load(id, manager), [id, manager]);
  const [editing, setEditing] = useState(false);
  const [changing, setChanging] = useState(null);
  const [showFee, setShowFee] = useState(false);
  const [adding, setAdding] = useState(false);
  const confirm = useConfirm();
  if (error) return <p className="text-tally">{tr('This project doesn’t exist or isn’t shared with you.')}</p>;
  if (!data) return <Spinner />;
  const { project: p, tasks, items } = data;
  const mine = manager ? tasks : tasks.filter(t => t.assigned_to === user.id);
  const openOrders = mine.filter(t => !['completed', 'cancelled'].includes(t.status));

  const setStatus = async (status, message) => {
    await api
      .patch(`projects/${id}/`, { status })
      .then(() => {
        toast(message);
        reload();
      })
      .catch(err => toast(errorText(err), 'error'));
  };
  const archive = async () => {
    if (
      await confirm({
        title: tr('Archive “{name}”?', { name: p.name }),
        body: tr(
          'It leaves the active lists but keeps all its content, orders, files and history. You can restore it any time.',
        ),
        action: tr('Archive project'),
      })
    )
      setStatus('archived', tr('Project archived'));
  };
  const remove = async () => {
    if (
      !(await confirm({
        title: tr('Delete “{name}” forever?', { name: p.name }),
        body: tr('All of its content, orders, messages and files are deleted. This can’t be undone.'),
        action: tr('Delete forever'),
        danger: true,
      }))
    )
      return;
    await api
      .delete(`projects/${id}/`)
      .then(() => {
        toast(tr('Project deleted'));
        navigate('/projects?status=archived');
      })
      .catch(err => toast(errorText(err), 'error'));
  };
  const archived = p.status === 'archived';

  return (
    <>
      <nav className="flex items-center gap-1.5 text-[14px] text-graphite mb-4" aria-label={tr('Breadcrumb')}>
        <Link to="/projects" className="hover:text-ink">
          {tr('Projects')}
        </Link>
        <ChevronRight size={14} />
        <span className="truncate">{p.client_name}</span>
      </nav>
      <header className="flex flex-wrap items-end justify-between gap-4 mb-6">
        <div className="min-w-0">
          <h1 className="display text-[26px] sm:text-[31px] leading-tight font-semibold">{p.name}</h1>
          <p className="text-graphite mt-1.5">
            {p.client_name}, {STATUS_TEXT[p.status] || p.status}
            {p.end_date ? `, ${tr('until {date}', { date: day(p.end_date) })}` : ''}
          </p>
        </div>
        {manager && (
          <div className="flex gap-2">
            <button onClick={() => setEditing(true)} className="btn btn-quiet">
              <PencilLine /> {tr('verb|Edit')}
            </button>
            {!archived && (
              <button onClick={() => setAdding(true)} className="btn btn-primary">
                <Plus /> {tr('New content')}
              </button>
            )}
          </div>
        )}
      </header>

      <div className="grid lg:grid-cols-[1fr_320px] gap-6 items-start">
        <div className="space-y-6 min-w-0">
          {manager && (
            <section className="panel overflow-hidden">
              <div className="flex items-center justify-between px-5 py-4 border-b border-hairline">
                <h2 className="text-[17px] font-semibold">{tr('Content')}</h2>
                <StageStrip items={items} />
              </div>
              {items.length === 0 ? (
                <Empty title={tr('No content yet')}>{tr('Add the first reel, video or post for this project.')}</Empty>
              ) : (
                <ul className="relative @container">
                  {items.map(i => (
                    <Track key={i.id} item={i} onChange={setChanging} />
                  ))}
                </ul>
              )}
            </section>
          )}
          <section>
            <h2 className="text-[17px] font-semibold mb-3">
              {manager ? tr('Open orders') : tr('Your orders')}{' '}
              <span className="text-graphite font-normal num">{openOrders.length}</span>
            </h2>
            {openOrders.length === 0 ? (
              <p className="panel p-6 text-graphite">
                {manager ? tr('No open orders.') : tr('Nothing open for you here right now.')}
              </p>
            ) : (
              <ul className="panel divide-y divide-hairline overflow-hidden">
                {openOrders.map(t => {
                  const st = STAGES.find(s => s.key === t.stage);
                  return (
                    <li key={t.id}>
                      <Link
                        to={`/orders/${t.id}`}
                        className="flex items-center gap-3.5 px-4 sm:px-5 py-3.5 hover:bg-haze"
                      >
                        <span
                          className="w-1 self-stretch rounded-full"
                          style={{ background: st?.color || 'var(--color-mist)' }}
                        />
                        <span className="min-w-0 flex-1">
                          <span className="block font-semibold truncate">{t.title}</span>
                          <span className="block text-[13px] text-graphite">
                            {manager ? `${t.assigned_to_name || tr('Nobody yet')}, ` : ''}
                            {t.is_blocked ? tr('up next') : ORDER_TEXT[t.status].toLowerCase()}
                          </span>
                        </span>
                        <Due date={t.due_date} done={t.status === 'waiting_for_review'} className="hidden sm:inline" />
                      </Link>
                    </li>
                  );
                })}
              </ul>
            )}
          </section>
        </div>

        <aside className="space-y-6 min-w-0">
          <section className="panel p-5">
            <h2 className="text-[17px] font-semibold mb-4">{tr('About')}</h2>
            <dl className="space-y-3 text-[14px]">
              <div className="flex items-center justify-between gap-3">
                <dt className="text-graphite">{tr('Manager')}</dt>
                <dd className="flex items-center gap-2 font-medium">
                  <Avatar name={p.project_manager_name} size={22} />
                  {p.project_manager_name || tr('Nobody yet')}
                </dd>
              </div>
              <div className="flex justify-between gap-3">
                <dt className="text-graphite">{tr('Dates')}</dt>
                <dd className="font-medium num">
                  {p.start_date ? day(p.start_date) : '—'} – {p.end_date ? day(p.end_date) : '—'}
                </dd>
              </div>
              {user.role === 'OWNER' && (
                <div className="flex justify-between items-center gap-3">
                  <dt className="text-graphite">{tr('Fee')}</dt>
                  <dd className="flex items-center gap-1 font-semibold num">
                    {showFee ? money(p.service_fee) : '••••'}
                    <button
                      onClick={() => setShowFee(v => !v)}
                      className="btn-icon w-8 h-8"
                      aria-label={showFee ? tr('Hide fee') : tr('Show fee')}
                    >
                      {showFee ? <EyeOff size={15} /> : <Eye size={15} />}
                    </button>
                  </dd>
                </div>
              )}
            </dl>
            {p.goals && (
              <>
                <h3 className="font-semibold mt-5 mb-1">{tr('Goals')}</h3>
                <p className="text-[14px] text-graphite whitespace-pre-line">{p.goals}</p>
              </>
            )}
            {p.deliverables_summary && (
              <>
                <h3 className="font-semibold mt-4 mb-1">{tr('What we deliver')}</h3>
                <p className="text-[14px] text-graphite whitespace-pre-line">{p.deliverables_summary}</p>
              </>
            )}
          </section>
          {manager && !archived && (
            <button onClick={archive} className="btn btn-ghost w-full">
              <Archive /> {tr('Archive project')}
            </button>
          )}
          {manager && archived && (
            <section className="panel p-5">
              <p className="font-semibold">{tr('Archived')}</p>
              <p className="text-[14px] text-graphite mt-1">
                {user.role === 'OWNER'
                  ? tr('Kept for the record. Restore it to work on it again, or delete it for good.')
                  : tr('Kept for the record. Restore it to work on it again.')}
              </p>
              <div className="flex flex-wrap gap-2 mt-4">
                <button onClick={() => setStatus('active', tr('Project restored'))} className="btn btn-quiet">
                  <ArchiveRestore /> {tr('Restore')}
                </button>
                {user.role === 'OWNER' && (
                  <button onClick={remove} className="btn btn-ghost text-tally">
                    <Trash2 /> {tr('Delete forever')}
                  </button>
                )}
              </div>
            </section>
          )}
        </aside>
      </div>

      {adding && <NewContent projects={[p]} preset={p.id} onClose={() => setAdding(false)} />}
      {editing && <ProjectForm project={p} onClose={() => setEditing(false)} onSaved={reload} />}
      {changing && (
        <ChangeOrders
          taskIds={(changing.production || [])
            .filter(s => !['completed', 'cancelled'].includes(s.status))
            .map(s => s.task)}
          onClose={() => setChanging(null)}
          onSaved={reload}
        />
      )}
    </>
  );
}
