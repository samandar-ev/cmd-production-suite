import { useCallback, useEffect, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import {
  ChevronRight,
  PencilLine,
  Send,
  Trash2,
  ExternalLink,
  Lock,
  Clapperboard,
  HardDrive,
  FileVideo,
} from 'lucide-react';
import api, { errorText, list } from '../lib/api';
import { nameOf } from '../lib/auth';
import { STAGES, STATUS_TEXT, progressOf, stageOf, ORDER_TEXT } from '../lib/stages';
import { ago, stamp, when } from '../lib/format';
import { Avatar, Dialog, Due, Spinner } from '../ui';
import { useToast, useConfirm } from '../lib/hooks';
import ChangeOrders from '../features/ChangeOrders';
import { tr } from '../lib/i18n';

const pad = n => String(n).padStart(2, '0');
const toInput = d =>
  d
    ? `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`
    : '';

export function BigTrack({ status }) {
  const p = progressOf(status);
  const here = stageOf(status);
  const idx = STAGES.findIndex(s => s.key === here.key);
  const done = ['published', 'completed'].includes(status);
  return (
    <div className="relative pt-3">
      <div className="grid grid-cols-5 gap-1">
        {STAGES.map((s, i) => {
          const fill = i < idx || done ? 1 : i === idx ? p * STAGES.length - idx : 0;
          return (
            <div key={s.key}>
              <div className="h-3 rounded-[4px] bg-haze overflow-hidden border border-hairline/60">
                <div
                  className="h-full"
                  style={{ width: `${fill * 100}%`, background: s.color, opacity: i < idx && !done ? 0.45 : 1 }}
                />
              </div>
              <p className={`mt-2 text-[13px] ${i === idx ? 'font-semibold text-ink' : 'text-mist'}`}>{s.label}</p>
            </div>
          );
        })}
      </div>
      {!done && (
        <span
          aria-hidden
          className="absolute top-0 h-9 w-[2px] rounded-full bg-tally"
          style={{ left: `calc(${p * 100}% - 1px)` }}
        />
      )}
    </div>
  );
}

const WORKFLOWS = [
  { key: 'shoot_edit', label: tr('Shoot, then edit'), stages: ['shoot', 'edit'] },
  { key: 'edit_only', label: tr('Edit only'), stages: ['edit'], hint: tr('The footage already exists.') },
  { key: 'shoot_only', label: tr('Shoot only'), stages: ['shoot'], hint: tr('Photos or raw footage, no editing.') },
];

function PlanProduction({ item, people, onDone }) {
  const toast = useToast();
  const [plan, setPlan] = useState({
    workflow: 'shoot_edit',
    videographer: item.assigned_videographer || '',
    editor: item.assigned_editor || '',
    shoot_due: '',
    edit_due: '',
    shoot_brief: '',
    edit_brief: '',
  });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const wf = WORKFLOWS.find(w => w.key === plan.workflow);
  const set = k => e => {
    setPlan(p => ({ ...p, [k]: e.target.value }));
    setError('');
  };
  const start = async e => {
    e.preventDefault();
    setBusy(true);
    setError('');
    try {
      await api.post(`content-items/${item.id}/start-production/`, {
        ...plan,
        priority: 'Medium',
        shoot_due: plan.shoot_due ? new Date(plan.shoot_due).toISOString() : null,
        edit_due: plan.edit_due ? new Date(plan.edit_due).toISOString() : null,
      });
      toast(tr('Production started — the crew has been notified'));
      onDone();
    } catch (err) {
      setError(errorText(err));
    } finally {
      setBusy(false);
    }
  };
  const step = stage => {
    const isShoot = stage === 'shoot';
    const s = STAGES.find(x => x.key === stage);
    return (
      <div key={stage} className="pl-4 border-l-[3px]" style={{ borderColor: s.color }}>
        <p className="font-semibold mb-3">{isShoot ? tr('Shoot') : tr('Edit')}</p>
        <div className="grid sm:grid-cols-2 gap-3">
          <div>
            <label className="label" htmlFor={`${stage}-who`}>
              {isShoot ? tr('Videographer') : tr('Editor')}
            </label>
            <select
              id={`${stage}-who`}
              className="field"
              value={isShoot ? plan.videographer : plan.editor}
              onChange={set(isShoot ? 'videographer' : 'editor')}
              required
            >
              <option value="">{tr('Choose…')}</option>
              {people
                .filter(u => u.role === (isShoot ? 'VIDEOGRAPHER' : 'EDITOR'))
                .map(u => (
                  <option key={u.id} value={u.id}>
                    {nameOf(u)}
                  </option>
                ))}
            </select>
          </div>
          <div>
            <label className="label" htmlFor={`${stage}-due`}>
              {tr('Deadline')}
            </label>
            <input
              id={`${stage}-due`}
              type="datetime-local"
              className="field"
              value={plan[`${stage}_due`]}
              onChange={set(`${stage}_due`)}
              required
            />
          </div>
        </div>
        <label className="label mt-3" htmlFor={`${stage}-brief`}>
          {tr('Notes for them')} <span className="font-normal text-mist">{tr('(optional)')}</span>
        </label>
        <textarea
          id={`${stage}-brief`}
          rows={2}
          className="field"
          value={plan[`${stage}_brief`]}
          onChange={set(`${stage}_brief`)}
          placeholder={isShoot ? tr('Shots you need, location, props') : tr('Length, music, captions, style')}
        />
      </div>
    );
  };
  return (
    <form onSubmit={start} className="space-y-5">
      <div className="seg flex-wrap" role="group" aria-label={tr('How it’s made')}>
        {WORKFLOWS.map(w => (
          <button
            type="button"
            key={w.key}
            aria-pressed={plan.workflow === w.key}
            onClick={() => setPlan(p => ({ ...p, workflow: w.key }))}
          >
            {w.label}
          </button>
        ))}
      </div>
      {wf.hint && <p className="text-[14px] text-graphite -mt-2">{wf.hint}</p>}
      {wf.stages.map(step)}
      {error && (
        <p role="alert" className="text-tally">
          {error}
        </p>
      )}
      <div className="flex justify-end">
        <button disabled={busy} className="btn btn-primary">
          <Clapperboard /> {busy ? tr('Starting…') : tr('Start production')}
        </button>
      </div>
    </form>
  );
}

export default function ContentPage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const toast = useToast();
  const confirm = useConfirm();
  const [data, setData] = useState(null);
  const [changing, setChanging] = useState(false);
  const [publishing, setPublishing] = useState(false);
  const [comment, setComment] = useState('');

  const load = useCallback(
    () =>
      Promise.all([
        api.get(`content-items/${id}/`).then(r => r.data),
        api.get('users/').then(list),
        api
          .get('video-submissions/', { params: { content_item: id } })
          .then(list)
          .catch(() => []),
        api
          .get('comments/', { params: { entity_type: 'ContentItem', entity_id: id } })
          .then(list)
          .catch(() => []),
      ]).then(([item, people, files, comments]) =>
        setData({ item, people: people.filter(u => u.is_active), files, comments }),
      ),
    [id],
  );
  useEffect(() => {
    load();
  }, [load]);

  if (!data) return <Spinner />;
  const { item, people, files, comments } = data;
  const steps = item.production || [];

  const saveField = async patch => {
    try {
      const { data: next } = await api.patch(`content-items/${id}/`, patch);
      setData(d => ({ ...d, item: { ...d.item, ...next } }));
      toast(tr('Saved'));
    } catch (err) {
      toast(errorText(err), 'error');
    }
  };
  const addComment = async e => {
    e.preventDefault();
    if (!comment.trim()) return;
    await api
      .post('comments/', { entity_type: 'ContentItem', entity_id: Number(id), message: comment.trim() })
      .catch(err => toast(errorText(err), 'error'));
    setComment('');
    load();
  };
  const remove = async () => {
    if (
      !(await confirm({
        title: tr('Delete “{title}”?', { title: item.title }),
        body: tr('Its orders, files and feedback go with it. This can’t be undone.'),
        action: tr('Delete content'),
        danger: true,
      }))
    )
      return;
    await api
      .delete(`content-items/${id}/`)
      .then(() => {
        toast(tr('Content deleted'));
        navigate('/production');
      })
      .catch(err => toast(errorText(err), 'error'));
  };

  return (
    <>
      <nav className="flex items-center gap-1.5 text-[14px] text-graphite mb-4" aria-label={tr('Breadcrumb')}>
        <Link to="/production" className="hover:text-ink">
          {tr('Production')}
        </Link>
        <ChevronRight size={14} />
        <Link to={`/projects/${item.project}`} className="hover:text-ink truncate">
          {item.project_name}
        </Link>
      </nav>
      <header className="mb-6">
        <h1 className="display text-[26px] sm:text-[31px] leading-tight font-semibold">{item.title}</h1>
        <p className="text-graphite mt-1.5">
          {item.client_name}, {item.platform} {item.content_type && tr(item.content_type).toLowerCase()}
          {item.target_publish_date ? `, ${tr('publishing {when}', { when: when(item.target_publish_date) })}` : ''}
        </p>
      </header>

      <section className="panel p-5 sm:p-6 mb-6">
        <div className="flex flex-wrap items-baseline justify-between gap-2 mb-1">
          <p className="font-semibold">{STATUS_TEXT[item.status]}</p>
          {item.status === 'approved' && (
            <button onClick={() => setPublishing(true)} className="btn btn-primary btn-sm">
              <Send /> {tr('Mark as published')}
            </button>
          )}
          {item.publish_url && (
            <a
              href={item.publish_url}
              target="_blank"
              rel="noreferrer"
              className="text-[14px] font-semibold inline-flex items-center gap-1 hover:underline"
            >
              {tr('View the post')} <ExternalLink size={14} />
            </a>
          )}
        </div>
        <BigTrack status={item.status} />
      </section>

      <div className="grid lg:grid-cols-[1.5fr_1fr] gap-6 items-start">
        <div className="space-y-6 min-w-0">
          <section className="panel p-5 sm:p-6">
            <div className="flex items-baseline justify-between gap-3 mb-4">
              <h2 className="text-[17px] font-semibold">{tr('Crew and deadlines')}</h2>
              {steps.some(s => !['completed', 'cancelled'].includes(s.status)) && (
                <button onClick={() => setChanging(true)} className="btn btn-quiet btn-sm">
                  <PencilLine /> {tr('Change')}
                </button>
              )}
            </div>
            {steps.length === 0 ? (
              <PlanProduction item={item} people={people} onDone={load} />
            ) : (
              <ol className="space-y-1">
                {steps.map(s => {
                  const st = STAGES.find(x => x.key === s.stage);
                  return (
                    <li key={s.task}>
                      <Link
                        to={`/orders/${s.task}`}
                        className="flex items-center gap-4 rounded-[10px] p-3 -mx-3 hover:bg-haze"
                      >
                        <span className="w-1 self-stretch rounded-full" style={{ background: st?.color }} />
                        <span className="w-14 text-[14px] font-semibold">{st?.label}</span>
                        <Avatar name={s.assignee} size={28} />
                        <span className="min-w-0 flex-1">
                          <span className="block font-medium truncate">{s.assignee || tr('Nobody yet')}</span>
                          <span className="block text-[13px] text-graphite">
                            {s.is_blocked ? (
                              <span className="inline-flex items-center gap-1">
                                <Lock size={12} /> {tr('Starts after the shoot is approved')}
                              </span>
                            ) : (
                              ORDER_TEXT[s.status]
                            )}
                          </span>
                        </span>
                        <Due
                          date={s.due_date}
                          done={['completed', 'waiting_for_review'].includes(s.status)}
                          className="hidden sm:inline"
                        />
                      </Link>
                    </li>
                  );
                })}
              </ol>
            )}
          </section>

          <section className="panel p-5 sm:p-6">
            <h2 className="text-[17px] font-semibold mb-4">{tr('Work and feedback')}</h2>
            {files.length === 0 ? (
              <p className="text-graphite text-[14px] mb-5">
                {tr('No work sent yet. Versions appear here when the crew sends them for review.')}
              </p>
            ) : (
              <ul className="mb-6 divide-y divide-hairline">
                {files.map(f => (
                  <li key={f.id}>
                    <Link
                      to={`/review/${f.id}`}
                      className="flex items-center gap-3 py-3 hover:bg-haze -mx-2 px-2 rounded-[10px]"
                    >
                      {f.delivery === 'in_person' ? (
                        <HardDrive size={18} className="text-graphite" />
                      ) : (
                        <FileVideo size={18} className="text-graphite" />
                      )}
                      <span className="min-w-0 flex-1">
                        <span className="block font-medium truncate">
                          {tr('Version')} {f.version}
                          {f.delivery === 'in_person' ? `, ${tr('handed over in person')}` : `, ${f.original_filename}`}
                        </span>
                        <span className="block text-[13px] text-graphite">
                          {f.uploader_name}, {ago(f.created_at)}
                        </span>
                      </span>
                      <span
                        className={`text-[13px] font-semibold ${f.status === 'approved' ? 'text-publish' : f.status === 'rejected' ? 'text-tally' : 'text-review'}`}
                      >
                        {{
                          pending: tr('Waiting for review'),
                          approved: tr('Approved'),
                          rejected: tr('Changes requested'),
                        }[f.status] || f.status}
                      </span>
                    </Link>
                  </li>
                ))}
              </ul>
            )}
            <ul className="space-y-4 mb-4">
              {comments.map(c => (
                <li key={c.id} className="flex gap-3">
                  <Avatar name={c.author_name} size={28} />
                  <div className="min-w-0">
                    <p className="text-[14px]">
                      <span className="font-semibold">{c.author_name}</span>{' '}
                      <span className="text-mist">{ago(c.created_at)}</span>
                    </p>
                    <p className="whitespace-pre-line">{c.message}</p>
                  </div>
                </li>
              ))}
            </ul>
            <form onSubmit={addComment} className="flex gap-2">
              <input
                value={comment}
                onChange={e => setComment(e.target.value)}
                className="field"
                placeholder={tr('Leave a note for the team')}
                aria-label={tr('Note')}
              />
              <button disabled={!comment.trim()} className="btn btn-quiet" aria-label={tr('Send note')}>
                <Send />
              </button>
            </form>
          </section>
        </div>

        <aside className="space-y-6 min-w-0">
          <section className="panel p-5 sm:p-6">
            <h2 className="text-[17px] font-semibold mb-4">{tr('Brief')}</h2>
            <EditableText
              label={tr('Idea or script')}
              value={item.script_scenario}
              rows={6}
              onSave={v => saveField({ script_scenario: v })}
              placeholder={tr('What happens on screen, the message, the call to action')}
            />
            <EditableText
              label={tr('Goal')}
              value={item.objective}
              rows={2}
              onSave={v => saveField({ objective: v })}
              placeholder={tr('What this piece should achieve')}
            />
            <EditableText
              label={tr('Shooting location')}
              value={item.shooting_location}
              rows={1}
              onSave={v => saveField({ shooting_location: v })}
              placeholder={tr('Address or venue')}
            />
            <label className="label mt-4" htmlFor="pub">
              {tr('Publish on')}
            </label>
            <input
              id="pub"
              type="datetime-local"
              className="field"
              defaultValue={item.target_publish_date ? toInput(new Date(item.target_publish_date)) : ''}
              onBlur={e =>
                saveField({ target_publish_date: e.target.value ? new Date(e.target.value).toISOString() : null })
              }
            />
            <p className="text-[13px] text-mist mt-4">
              {tr('Changes save when you click away. Last change')} {ago(item.updated_at)}.
            </p>
          </section>
          <button onClick={remove} className="btn btn-ghost text-tally w-full">
            <Trash2 /> {tr('Delete this content')}
          </button>
        </aside>
      </div>

      {changing && (
        <ChangeOrders
          taskIds={steps.filter(s => !['completed', 'cancelled'].includes(s.status)).map(s => s.task)}
          onClose={() => setChanging(false)}
          onSaved={load}
        />
      )}
      {publishing && <PublishDialog item={item} onClose={() => setPublishing(false)} onDone={load} />}
      <p className="sr-only">
        {tr('Created')} {stamp(item.created_at)}
      </p>
    </>
  );
}

function EditableText({ label, value, onSave, rows = 3, placeholder }) {
  const [v, setV] = useState(value || '');
  const [seen, setSeen] = useState(value);
  if (value !== seen) {
    setSeen(value);
    setV(value || '');
  }
  const id = label.replace(/\W/g, '');
  return (
    <div className="mt-4 first:mt-0">
      <label className="label" htmlFor={id}>
        {label}
      </label>
      {rows === 1 ? (
        <input
          id={id}
          className="field"
          value={v}
          placeholder={placeholder}
          onChange={e => setV(e.target.value)}
          onBlur={() => v !== (value || '') && onSave(v)}
        />
      ) : (
        <textarea
          id={id}
          rows={rows}
          className="field"
          value={v}
          placeholder={placeholder}
          onChange={e => setV(e.target.value)}
          onBlur={() => v !== (value || '') && onSave(v)}
        />
      )}
    </div>
  );
}

function PublishDialog({ item, onClose, onDone }) {
  const toast = useToast();
  const [url, setUrl] = useState('');
  const [busy, setBusy] = useState(false);
  const publish = async () => {
    setBusy(true);
    try {
      await api.post(`content-items/${item.id}/publish/`, { post_url: url, platform: item.platform });
      toast(tr('Marked as published'));
      onDone();
      onClose();
    } catch (err) {
      toast(errorText(err), 'error');
      setBusy(false);
    }
  };
  return (
    <Dialog
      title={tr('Mark as published')}
      sub={`${item.title} on ${item.platform}`}
      onClose={onClose}
      footer={
        <>
          <button onClick={onClose} className="btn btn-ghost">
            {tr('Cancel')}
          </button>
          <button onClick={publish} disabled={busy} className="btn btn-primary">
            {busy ? tr('Saving…') : tr('Mark as published')}
          </button>
        </>
      }
    >
      <label className="label" htmlFor="purl">
        {tr('Link to the post')} <span className="font-normal text-mist">{tr('(optional)')}</span>
      </label>
      <input
        id="purl"
        type="url"
        className="field"
        value={url}
        onChange={e => setUrl(e.target.value)}
        placeholder={tr('https://instagram.com/p/…')}
      />
    </Dialog>
  );
}
