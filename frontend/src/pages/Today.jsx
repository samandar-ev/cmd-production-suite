import { Link } from 'react-router-dom';
import { Plus, PlayCircle, Bot, AlarmClock, ArrowUpRight } from 'lucide-react';
import api, { list } from '../lib/api';
import { useAuth, nameOf } from '../lib/auth';
import { STAGES, stageOf } from '../lib/stages';
import { ago, dayLong, greeting, left } from '../lib/format';
import { PageHeader, Spinner } from '../ui';
import { useLoad } from '../lib/hooks';
import DayTimeline from '../features/DayTimeline';
import { tr } from '../lib/i18n';

const tz = () => -new Date().getTimezoneOffset();
const iso = d => d.toISOString();
const ymd = d =>
  `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;

async function loadToday() {
  const start = new Date();
  start.setHours(0, 0, 0, 0);
  const end = new Date(start);
  end.setDate(end.getDate() + 1);
  const [metrics, cal, approvals, tasks] = await Promise.all([
    api.get('dashboards/metrics/', { params: { start: iso(start), end: iso(end), tz: tz() } }).then(r => r.data),
    api
      .get('calendar/', { params: { start: ymd(start), end: ymd(start), tz: tz() } })
      .then(r => r.data)
      .catch(() => []),
    api
      .get('ai/approvals/')
      .then(r => r.data.filter(a => a.status === 'pending'))
      .catch(() => []),
    api
      .get('tasks/')
      .then(list)
      .catch(() => []),
  ]);
  const timeline = cal.map(c => ({
    id: c.id,
    title: c.title,
    kind: c.type,
    at: new Date(c.start),
    allDay: c.all_day || c.type === 'publish' || c.type === 'todo',
    stage: c.stage,
    who: c.who,
    done: c.status === 'completed' || c.completed,
    to:
      c.type === 'order'
        ? `/orders/${c.ref}`
        : c.type === 'publish'
          ? `/content/${c.ref}`
          : c.type === 'todo'
            ? '/workspace'
            : '/calendar',
  }));
  const late = tasks.filter(t => t.is_overdue).sort((a, b) => new Date(a.due_date) - new Date(b.due_date));
  return { metrics, timeline, approvals, late };
}

function NeedsRow({ to, color, title, sub, action }) {
  return (
    <li>
      <Link to={to} className="group flex items-center gap-3.5 py-3.5 px-1 -mx-1 rounded-[10px] hover:bg-haze">
        <span className="w-1 self-stretch rounded-full shrink-0" style={{ background: color }} />
        <span className="min-w-0 flex-1">
          <span className="block font-semibold truncate">{title}</span>
          <span className="block text-[13px] text-graphite truncate">{sub}</span>
        </span>
        <span className="btn btn-quiet btn-sm shrink-0 group-hover:border-ink">{action}</span>
      </Link>
    </li>
  );
}

export default function Today() {
  const user = useAuth(s => s.user);
  const { data, error } = useLoad(loadToday, []);
  const first = (user?.first_name || nameOf(user)).split(' ')[0];

  return (
    <>
      <PageHeader
        title={`${greeting()}, ${first}`}
        sub={dayLong(new Date())}
        actions={
          <Link to="/production?new=1" className="btn btn-primary">
            <Plus /> {tr('New content')}
          </Link>
        }
      />
      {error && <p className="text-tally">{tr('Couldn’t load today. Refresh the page to try again.')}</p>}
      {!data ? <Spinner label={tr('Loading today')} /> : <TodayBody {...data} />}
    </>
  );
}

function TodayBody({ metrics, timeline, approvals, late }) {
  const t = metrics.today || {};
  const reviews = metrics.review_items || [];
  const needs = reviews.length + approvals.length + late.length;

  const byStage = STAGES.map(s => ({ ...s, n: 0 }));
  Object.entries(metrics.pipeline || {}).forEach(([status, n]) => {
    if (status === 'completed') return;
    const st = byStage.find(s => s.key === stageOf(status).key);
    st.n += n;
  });
  const total = byStage.reduce((a, s) => a + s.n, 0);

  return (
    <div className="space-y-6">
      <section className="panel p-5 sm:p-6" aria-labelledby="tl">
        <div className="flex flex-wrap items-baseline justify-between gap-2 mb-5">
          <h2 id="tl" className="text-[17px] font-semibold">
            {tr('Today’s timeline')}
          </h2>
          <p className="text-[14px] text-graphite num">
            {t.due_today
              ? tr('{done} of {n} due today done', { done: t.due_today_done, n: t.due_today })
              : tr('Nothing due today')}
            {t.done_today > 0 && `, ${t.done_today} finished`}
            {t.published_today > 0 && `, ${tr('{n} published', { n: t.published_today })}`}
          </p>
        </div>
        <DayTimeline items={timeline} />
      </section>

      <div className="grid lg:grid-cols-[1.35fr_1fr] gap-6 items-start">
        <section className="panel p-5 sm:p-6" aria-labelledby="needs">
          <div className="flex items-baseline justify-between mb-1">
            <h2 id="needs" className="text-[17px] font-semibold">
              {tr('Needs you')}
            </h2>
            <span className="text-[14px] text-graphite num">{needs || ''}</span>
          </div>
          {needs === 0 ? (
            <p className="text-graphite py-6">
              {tr('Nothing is waiting on you. Work in review, Claude’s requests and late orders will show up here.')}
            </p>
          ) : (
            <ul className="divide-y divide-hairline">
              {approvals.map(a => (
                <NeedsRow
                  key={`a${a.id}`}
                  to="/approvals"
                  color="var(--color-ink)"
                  action={
                    <>
                      <Bot /> {tr('Decide')}
                    </>
                  }
                  title={
                    a.kind === 'delete'
                      ? tr('Claude wants to delete something')
                      : tr('Claude wants to see finance data')
                  }
                  sub={a.summary}
                />
              ))}
              {reviews.map(r => (
                <NeedsRow
                  key={`r${r.id}`}
                  to={`/review/${r.id}`}
                  color="var(--color-review)"
                  action={
                    <>
                      <PlayCircle /> {tr('Review')}
                    </>
                  }
                  title={r.title}
                  sub={`${r.client_name}, ${r.platform}, sent ${ago(r.updated_at)}`}
                />
              ))}
              {late.map(o => (
                <NeedsRow
                  key={`l${o.id}`}
                  to={`/orders/${o.id}`}
                  color="var(--color-tally)"
                  action={
                    <>
                      <AlarmClock /> {tr('Open')}
                    </>
                  }
                  title={o.title}
                  sub={`${o.assigned_to_name || tr('Nobody assigned')}, ${left(o.due_date)?.text}`}
                />
              ))}
            </ul>
          )}
        </section>

        <section className="panel p-5 sm:p-6" aria-labelledby="where">
          <div className="flex items-baseline justify-between mb-4">
            <h2 id="where" className="text-[17px] font-semibold">
              {tr('Where everything is')}
            </h2>
            <Link
              to="/production"
              className="text-[14px] font-semibold text-graphite hover:text-ink inline-flex items-center gap-1"
            >
              {tr('Production')} <ArrowUpRight size={15} />
            </Link>
          </div>
          <div
            className="flex h-3 rounded-full overflow-hidden bg-haze gap-[2px]"
            role="img"
            aria-label={byStage.map(s => `${s.label}: ${s.n}`).join(', ')}
          >
            {total > 0 &&
              byStage.filter(s => s.n).map(s => <span key={s.key} style={{ flex: s.n, background: s.color }} />)}
          </div>
          <ul className="mt-4 grid grid-cols-[repeat(auto-fit,minmax(5.75rem,1fr))] gap-x-2 gap-y-4">
            {byStage.map(s => (
              <li key={s.key}>
                <Link to={`/production?stage=${s.key}`} className="block rounded-[10px] p-2 -m-2 hover:bg-haze">
                  <span className="display block text-[25px] font-semibold num leading-none">{s.n}</span>
                  <span className="flex items-center gap-1.5 mt-2 text-[13px] text-graphite">
                    <span className="w-2 h-2 rounded-[2px]" style={{ background: s.color }} />
                    {s.label}
                  </span>
                </Link>
              </li>
            ))}
          </ul>
          <dl className="mt-6 pt-5 border-t border-hairline grid grid-cols-2 gap-y-3 text-[14px]">
            <dt className="text-graphite">{tr('Orders in progress')}</dt>
            <dd className="text-right font-semibold num">{t.active_tasks ?? 0}</dd>
            <dt className="text-graphite">{tr('Sent for review')}</dt>
            <dd className="text-right font-semibold num">{t.in_review_tasks ?? 0}</dd>
            <dt className="text-graphite">{tr('Late')}</dt>
            <dd className={`text-right font-semibold num ${t.overdue ? 'text-tally' : ''}`}>{t.overdue ?? 0}</dd>
          </dl>
        </section>
      </div>
    </div>
  );
}
