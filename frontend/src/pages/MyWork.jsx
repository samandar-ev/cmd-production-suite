import { useState } from 'react';
import { Link } from 'react-router-dom';
import { Play, UploadCloud, Lock, ChevronRight } from 'lucide-react';
import api, { errorText, list } from '../lib/api';
import { useAuth, nameOf } from '../lib/auth';
import { STAGES } from '../lib/stages';
import { dayLong, greeting, left, when } from '../lib/format';
import { Due, PageHeader, Spinner } from '../ui';
import { useLoad, useToast } from '../lib/hooks';
import SendWork from '../features/SendWork';
import DayTimeline from '../features/DayTimeline';
import { tr, trn } from '../lib/i18n';

const ymd = d =>
  `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;

async function load() {
  const today = new Date();
  const [tasks, cal] = await Promise.all([
    api.get('tasks/').then(list),
    api
      .get('calendar/', { params: { start: ymd(today), end: ymd(today), tz: -today.getTimezoneOffset() } })
      .then(r => r.data)
      .catch(() => []),
  ]);
  return { tasks, cal };
}

const group = t => {
  const sub = t.latest_submission?.status;
  if (t.status === 'cancelled') return null;
  if (t.status === 'completed' || sub === 'approved') return 'done';
  if (t.is_blocked) return 'next';
  if (t.status === 'waiting_for_review' || sub === 'pending') return 'review';
  return 'todo';
};

function Row({ t }) {
  const stage = STAGES.find(s => s.key === t.stage);
  const changes = t.latest_submission?.status === 'rejected';
  return (
    <li>
      <Link to={`/orders/${t.id}`} className="flex items-center gap-3.5 py-3.5 px-4 sm:px-5 hover:bg-haze">
        <span
          className="w-1 self-stretch rounded-full shrink-0"
          style={{ background: stage?.color || 'var(--color-mist)' }}
        />
        <span className="min-w-0 flex-1">
          <span className="block font-semibold truncate">{t.title}</span>
          <span className="block text-[13px] text-graphite truncate">
            {t.project_name}
            {changes ? `, ${tr('changes requested')}` : ''}
          </span>
        </span>
        <Due date={t.due_date} done={group(t) !== 'todo'} className="hidden sm:inline" />
        <ChevronRight size={18} className="text-mist shrink-0" />
      </Link>
    </li>
  );
}

export default function MyWork() {
  const user = useAuth(s => s.user);
  const toast = useToast();
  const { data, reload } = useLoad(load, []);
  const [sending, setSending] = useState(null);
  if (!data)
    return (
      <>
        <PageHeader
          title={tr('{greeting}, {name}', {
            greeting: greeting(),
            name: (user?.first_name || nameOf(user)).split(' ')[0],
          })}
        />
        <Spinner />
      </>
    );

  const by = { todo: [], review: [], next: [], done: [] };
  data.tasks.forEach(t => {
    const g = group(t);
    if (g) by[g].push(t);
  });
  by.todo.sort(
    (a, b) => (a.due_date ? new Date(a.due_date) : Infinity) - (b.due_date ? new Date(b.due_date) : Infinity),
  );
  const focus = by.todo[0];
  const rest = by.todo.slice(1);
  const timeline = data.cal.map(c => ({
    id: c.id,
    title: c.title,
    kind: c.type,
    at: new Date(c.start),
    stage: c.stage,
    who: null,
    allDay: c.all_day || (c.type !== 'order' && c.type !== 'event'),
    to: c.type === 'order' ? `/orders/${c.ref}` : '/calendar',
    done: c.status === 'completed',
  }));

  const start = async t => {
    try {
      await api.post(`tasks/${t.id}/start/`);
      toast(tr('Started'));
      reload();
    } catch (err) {
      toast(errorText(err), 'error');
    }
  };

  return (
    <>
      <PageHeader
        title={tr('{greeting}, {name}', {
          greeting: greeting(),
          name: (user?.first_name || nameOf(user)).split(' ')[0],
        })}
        sub={[
          dayLong(new Date()),
          by.todo.length ? trn(by.todo.length, '{n} order to do', '{n} orders to do') : tr('Nothing to do right now'),
          by.review.length ? trn(by.review.length, '{n} waiting for review', '{n} waiting for review') : null,
        ]
          .filter(Boolean)
          .join('. ')}
      />

      {focus && (
        <section className="panel p-5 sm:p-7 mb-6 relative overflow-hidden" aria-labelledby="focus">
          <span
            aria-hidden
            className="absolute left-0 top-0 bottom-0 w-1.5"
            style={{ background: STAGES.find(s => s.key === focus.stage)?.color || 'var(--color-ink)' }}
          />
          <p className="text-[13px] font-semibold text-graphite">
            {left(focus.due_date)?.late ? tr('Late — do this first') : tr('Do this next')}
          </p>
          <h2 id="focus" className="display text-[22px] sm:text-[26px] font-semibold leading-tight mt-1.5">
            <Link to={`/orders/${focus.id}`} className="hover:underline underline-offset-4">
              {focus.title}
            </Link>
          </h2>
          <p className="text-graphite mt-1">{focus.project_name}</p>
          <div className="flex flex-wrap items-end justify-between gap-4 mt-5">
            <div>
              <p className={`display text-[22px] font-semibold num ${left(focus.due_date)?.late ? 'text-tally' : ''}`}>
                {focus.due_date ? when(focus.due_date) : tr('No deadline')}
              </p>
              {focus.due_date && <p className="text-[14px] text-graphite num">{left(focus.due_date).text}</p>}
            </div>
            <div className="flex gap-2">
              {focus.status === 'not_started' && (
                <button onClick={() => start(focus)} className="btn btn-quiet">
                  <Play /> {tr('Start')}
                </button>
              )}
              <button onClick={() => setSending(focus)} className="btn btn-primary">
                <UploadCloud />{' '}
                {focus.latest_submission?.status === 'rejected' ? tr('Send new version') : tr('Send work')}
              </button>
            </div>
          </div>
        </section>
      )}

      {timeline.length > 0 && (
        <section className="panel p-5 sm:p-6 mb-6">
          <h2 className="text-[17px] font-semibold mb-4">{tr('Today')}</h2>
          <DayTimeline items={timeline} />
        </section>
      )}

      <div className="space-y-6">
        {[
          [tr('To do'), rest],
          [tr('Waiting for review'), by.review],
          [tr('Up next'), by.next],
          [tr('Done recently'), by.done.slice(0, 5)],
        ].map(
          ([title, items]) =>
            items.length > 0 && (
              <section key={title}>
                <h2 className="text-[17px] font-semibold mb-2.5 flex items-center gap-2">
                  {title === tr('Up next') && <Lock size={15} className="text-graphite" />}
                  {title}
                  <span className="text-graphite font-normal num">{items.length}</span>
                </h2>
                {title === tr('Up next') && (
                  <p className="text-[14px] text-graphite -mt-1.5 mb-2.5">
                    {tr('These start when the step before them is approved.')}
                  </p>
                )}
                <ul className="panel divide-y divide-hairline overflow-hidden">
                  {items.map(t => (
                    <Row key={t.id} t={t} />
                  ))}
                </ul>
              </section>
            ),
        )}
        {data.tasks.length === 0 && (
          <p className="panel p-8 text-center text-graphite">
            {tr('No orders yet. When your manager gives you one, it appears here and on Telegram.')}
          </p>
        )}
      </div>
      {sending && <SendWork task={sending} onClose={() => setSending(null)} onSent={reload} />}
    </>
  );
}
