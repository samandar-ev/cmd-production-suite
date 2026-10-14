import { useCallback, useEffect, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import {
  ArrowLeft,
  Play,
  UploadCloud,
  PencilLine,
  PlayCircle,
  Lock,
  HardDrive,
  Download,
  MapPin,
  Check,
  Plus,
  Trash2,
  Clock,
} from 'lucide-react';
import api, { errorText, list } from '../lib/api';
import { useAuth, isManager } from '../lib/auth';
import { STAGES } from '../lib/stages';
import { ago, left, stamp, when } from '../lib/format';
import { Spinner } from '../ui';
import { useToast } from '../lib/hooks';
import Chat from '../features/Chat';
import SendWork from '../features/SendWork';
import ChangeOrders from '../features/ChangeOrders';
import { tr } from '../lib/i18n';

const stateOf = t => {
  const sub = t.latest_submission?.status;
  if (t.is_blocked)
    return {
      key: 'next',
      text: tr('Up next'),
      note: tr('Starts when the previous step is approved. You’ll get a message.'),
    };
  if (t.status === 'completed' || sub === 'approved')
    return { key: 'done', text: tr('Done'), note: tr('Approved. Nice work.') };
  if (t.status === 'waiting_for_review' || sub === 'pending')
    return {
      key: 'review',
      text: tr('Waiting for review'),
      note: tr('Your manager has it. You’ll get a message when they decide.'),
    };
  if (sub === 'rejected')
    return {
      key: 'changes',
      text: tr('Changes requested'),
      note: tr('Read the feedback below, then send a new version.'),
    };
  if (t.status === 'in_progress') return { key: 'doing', text: tr('In progress') };
  if (t.status === 'cancelled') return { key: 'cancelled', text: tr('Cancelled') };
  return { key: 'new', text: tr('New') };
};

export default function OrderPage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const toast = useToast();
  const me = useAuth(s => s.user);
  const manager = isManager(me);
  const [data, setData] = useState(null);
  const [error, setError] = useState('');
  const [tab, setTab] = useState('details');
  const [sending, setSending] = useState(false);
  const [changing, setChanging] = useState(false);

  const load = useCallback(
    () =>
      Promise.all([
        api.get(`tasks/${id}/`).then(r => r.data),
        api
          .get('task-checklist-items/', { params: { task: id } })
          .then(list)
          .catch(() => []),
        api
          .get('video-submissions/', { params: { task: id } })
          .then(list)
          .catch(() => []),
      ]).then(
        ([task, checklist, subs]) => setData({ task, checklist, subs }),
        err =>
          setError(err?.response?.status === 404 ? tr('This order doesn’t exist or isn’t yours.') : errorText(err)),
      ),
    [id],
  );
  useEffect(() => {
    load();
  }, [load]);

  if (error) return <p className="text-tally">{error}</p>;
  if (!data) return <Spinner label={tr('Loading the order')} />;
  const { task, checklist, subs } = data;
  const st = stateOf(task);
  const mine = task.assigned_to === me?.id;
  const stage = STAGES.find(s => s.key === task.stage);
  const due = left(task.due_date);
  const canSend = mine && !task.is_blocked && ['new', 'doing', 'changes'].includes(st.key);
  const latest = subs[0];

  const start = async () => {
    try {
      await api.post(`tasks/${id}/start/`);
      toast(tr('Started — good luck'));
      load();
    } catch (err) {
      toast(errorText(err), 'error');
    }
  };

  return (
    <div className="lg:grid lg:grid-cols-[1fr_400px] lg:gap-8 items-start">
      <div className="min-w-0">
        <button onClick={() => navigate(-1)} className="btn btn-ghost btn-sm -ml-3 mb-3">
          <ArrowLeft /> {tr('Back')}
        </button>
        <p className="text-[14px] text-graphite flex items-center gap-2">
          {stage && <span className="w-2.5 h-2.5 rounded-[3px]" style={{ background: stage.color }} />}
          {[task.project_name, task.content_item_title].filter(Boolean).join(', ')}
        </p>
        <h1 className="display text-[24px] sm:text-[30px] leading-tight font-semibold mt-1">{task.title}</h1>

        <section className="panel p-5 mt-5">
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div>
              <p
                className={`text-[13px] font-semibold ${st.key === 'changes' ? 'text-tally' : st.key === 'done' ? 'text-publish' : 'text-graphite'}`}
              >
                {st.text}
              </p>
              <p
                className={`display text-[25px] font-semibold num mt-1 ${due?.late && !['done', 'review'].includes(st.key) ? 'text-tally' : ''}`}
              >
                {task.due_date ? when(task.due_date) : tr('No deadline')}
              </p>
              {task.due_date && !['done', 'review', 'next'].includes(st.key) && (
                <p className="text-[14px] text-graphite mt-0.5 num">{due.text}</p>
              )}
              {st.note && <p className="text-[14px] text-graphite mt-2 max-w-[48ch]">{st.note}</p>}
            </div>
            <div className="flex flex-wrap gap-2">
              {manager && !['done', 'cancelled'].includes(st.key) && (
                <button onClick={() => setChanging(true)} className="btn btn-quiet">
                  <PencilLine /> {tr('Change')}
                </button>
              )}
              {manager && latest?.status === 'pending' && (
                <Link to={`/review/${latest.id}`} className="btn btn-primary">
                  <PlayCircle /> {tr('Review')}
                </Link>
              )}
              {mine && st.key === 'new' && !task.is_blocked && (
                <button onClick={start} className="btn btn-primary">
                  <Play /> {tr('Start')}
                </button>
              )}
              {canSend && (
                <button onClick={() => setSending(true)} className="btn btn-primary">
                  <UploadCloud /> {st.key === 'changes' ? tr('Send new version') : tr('Send work for review')}
                </button>
              )}
            </div>
          </div>
          {!manager && (
            <p className="text-[13px] text-mist mt-4">
              {tr('From {name}', { name: task.project_manager_name || tr('your manager') })}
              {task.assigned_to_name && !mine ? `, ${tr('for {name}', { name: task.assigned_to_name })}` : ''}
            </p>
          )}
          {manager && (
            <p className="text-[13px] text-mist mt-4">
              {task.assigned_to_name
                ? tr('Assigned to {name}', { name: task.assigned_to_name })
                : tr('Nobody assigned yet')}
            </p>
          )}
        </section>

        <div className="seg w-full mt-6 lg:hidden" role="group" aria-label={tr('Order sections')}>
          <button className="flex-1" aria-pressed={tab === 'details'} onClick={() => setTab('details')}>
            {tr('Details')}
          </button>
          <button className="flex-1" aria-pressed={tab === 'chat'} onClick={() => setTab('chat')}>
            {tr('Messages')}
            {task.unread_messages > 0 ? ` (${task.unread_messages})` : ''}
          </button>
        </div>

        <div className={`${tab === 'chat' ? 'hidden lg:block' : ''} space-y-6 mt-6`}>
          {(task.description || task.content_item_script || task.content_item_location) && (
            <section>
              <h2 className="text-[17px] font-semibold mb-3">{tr('What to do')}</h2>
              {task.description && <p className="whitespace-pre-line">{task.description}</p>}
              {task.content_item_script && (
                <details className="mt-3 panel p-4" open={!task.description}>
                  <summary className="font-semibold cursor-pointer">{tr('Script')}</summary>
                  <p className="whitespace-pre-line mt-2 text-graphite">{task.content_item_script}</p>
                </details>
              )}
              {task.content_item_location && (
                <p className="mt-3 flex items-center gap-2 text-graphite">
                  <MapPin size={16} />
                  {task.content_item_location}
                </p>
              )}
            </section>
          )}

          {task.input_files?.length > 0 && (
            <section>
              <h2 className="text-[17px] font-semibold mb-3">
                {task.stage === 'edit' ? tr('Footage to edit') : tr('From the previous step')}
              </h2>
              <ul className="space-y-2">
                {task.input_files.map(f => (
                  <li key={f.id}>
                    <Link to={`/review/${f.id}`} className="panel flex items-center gap-3 p-4 hover:border-mist">
                      {f.delivery === 'in_person' ? (
                        <HardDrive className="text-shoot shrink-0" />
                      ) : (
                        <Download className="text-graphite shrink-0" />
                      )}
                      <span className="min-w-0">
                        <span className="block font-semibold truncate">
                          {f.delivery === 'in_person' ? tr('On a drive') : f.filename}
                        </span>
                        <span className="block text-[13px] text-graphite">
                          {f.delivery === 'in_person'
                            ? tr('Collect it from {name}', { name: f.handover_to_name || tr('your manager') })
                            : tr('Approved, from {name}', { name: f.uploader })}
                        </span>
                      </span>
                    </Link>
                  </li>
                ))}
              </ul>
            </section>
          )}

          {subs.length > 0 && (
            <section>
              <h2 className="text-[17px] font-semibold mb-3">{tr('Sent for review')}</h2>
              <ul className="panel divide-y divide-hairline">
                {subs.map(s => (
                  <li key={s.id}>
                    <Link to={`/review/${s.id}`} className="block p-4 hover:bg-haze">
                      <div className="flex items-center justify-between gap-3">
                        <span className="font-semibold">
                          {tr('Version {n}', { n: s.version })}
                          {s.delivery === 'in_person' ? `, ${tr('in person')}` : ''}
                        </span>
                        <span
                          className={`text-[13px] font-semibold ${s.status === 'approved' ? 'text-publish' : s.status === 'rejected' ? 'text-tally' : 'text-review'}`}
                        >
                          {
                            { pending: tr('Waiting'), approved: tr('Approved'), rejected: tr('Changes requested') }[
                              s.status
                            ]
                          }
                        </span>
                      </div>
                      <p className="text-[13px] text-graphite mt-0.5">{stamp(s.created_at)}</p>
                      {s.review_comment && (
                        <p className="mt-2 pl-3 border-l-2 border-hairline">
                          “{s.review_comment}” <span className="text-mist">— {s.reviewer_name}</span>
                        </p>
                      )}
                    </Link>
                  </li>
                ))}
              </ul>
            </section>
          )}

          <Checklist taskId={task.id} items={checklist} editable={mine || manager} onChange={load} />
          {task.is_blocked && (
            <p className="text-[14px] text-graphite flex items-center gap-2">
              <Lock size={15} /> {tr('This order unlocks when the previous step is approved.')}
            </p>
          )}
          <p className="text-[13px] text-mist flex items-center gap-1.5">
            <Clock size={13} /> {tr('Created')} {ago(task.created_at)}
          </p>
        </div>
      </div>

      <aside className={`${tab === 'chat' ? '' : 'hidden'} lg:block mt-6 lg:mt-0 lg:sticky lg:top-8`}>
        <section className="panel p-4 flex flex-col h-[calc(100dvh-260px)] lg:h-[calc(100dvh-64px)]">
          <h2 className="text-[17px] font-semibold px-1 pb-3 border-b border-hairline">{tr('Messages')}</h2>
          <Chat taskId={task.id} className="flex-1 pt-2" />
        </section>
      </aside>

      {sending && <SendWork task={task} onClose={() => setSending(false)} onSent={load} />}
      {changing && <ChangeOrders taskIds={[task.id]} onClose={() => setChanging(false)} onSaved={load} />}
    </div>
  );
}

function Checklist({ taskId, items, editable, onChange }) {
  const [text, setText] = useState('');
  const add = async e => {
    e.preventDefault();
    if (!text.trim()) return;
    await api
      .post('task-checklist-items/', { task: taskId, text: text.trim(), order_index: items.length })
      .catch(() => {});
    setText('');
    onChange();
  };
  const toggle = i => api.patch(`task-checklist-items/${i.id}/`, { is_completed: !i.is_completed }).finally(onChange);
  const remove = i => api.delete(`task-checklist-items/${i.id}/`).finally(onChange);
  const done = items.filter(i => i.is_completed).length;
  return (
    <section>
      <div className="flex items-baseline justify-between mb-3">
        <h2 className="text-[17px] font-semibold">{tr('Checklist')}</h2>
        {items.length > 0 && (
          <span className="text-[14px] text-graphite num">
            {done} {tr('of')} {items.length}
          </span>
        )}
      </div>
      <ul className="space-y-1">
        {items.map(i => (
          <li key={i.id} className="group flex items-center gap-3 rounded-[10px] px-2 -mx-2 py-1.5 hover:bg-haze">
            <button
              onClick={() => editable && toggle(i)}
              aria-pressed={i.is_completed}
              aria-label={i.text}
              className={`w-5 h-5 rounded-[6px] border flex items-center justify-center shrink-0 ${i.is_completed ? 'bg-ink border-ink text-paper' : 'border-mist bg-paper'}`}
            >
              {i.is_completed && <Check size={13} strokeWidth={3} />}
            </button>
            <span className={`flex-1 ${i.is_completed ? 'line-through text-mist' : ''}`}>{i.text}</span>
            {editable && (
              <button
                onClick={() => remove(i)}
                className="btn-icon w-8 h-8 opacity-0 group-hover:opacity-100 focus:opacity-100"
                aria-label={tr('Remove {text}', { text: i.text })}
              >
                <Trash2 size={15} />
              </button>
            )}
          </li>
        ))}
      </ul>
      {editable && (
        <form onSubmit={add} className="flex gap-2 mt-2">
          <input
            value={text}
            onChange={e => setText(e.target.value)}
            className="field"
            placeholder={tr('Add a step, e.g. Charge the batteries')}
            aria-label={tr('New step')}
          />
          <button disabled={!text.trim()} className="btn btn-quiet" aria-label={tr('Add step')}>
            <Plus />
          </button>
        </form>
      )}
    </section>
  );
}
