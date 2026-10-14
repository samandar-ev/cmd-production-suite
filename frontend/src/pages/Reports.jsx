import { useCallback, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import api, { list } from '../lib/api';
import { ROLE_TEXT } from '../lib/auth';
import { day } from '../lib/format';
import { Avatar, PageHeader, Spinner } from '../ui';
import { tr } from '../lib/i18n';

const RANGES = [
  [7, tr('7 days')],
  [30, tr('30 days')],
  [90, tr('90 days')],
  [365, tr('12 months')],
];
const KPIS = [
  ['content_published', tr('Published'), v => v],
  ['orders_completed', tr('Orders done'), v => v],
  ['on_time_rate', tr('On time'), v => (v == null ? '—' : `${v}%`)],
  ['first_pass_rate', tr('Approved first time'), v => (v == null ? '—' : `${v}%`)],
  ['avg_order_days', tr('Average order'), v => (v == null ? '—' : tr('{n} d', { n: v }))],
  ['revisions', tr('Revisions'), v => v],
];
const LOWER_IS_BETTER = ['avg_order_days', 'revisions'];
const SERIES = [
  ['created', tr('New content'), 'var(--color-plan)'],
  ['completed', tr('Orders done'), 'var(--color-ink)'],
  ['published', tr('Published'), 'var(--color-publish)'],
];

export default function Reports() {
  const [days, setDays] = useState(30);
  const [filters, setFilters] = useState({ project: '', member: '' });
  const [opts, setOpts] = useState({ projects: [], people: [] });
  const [r, setR] = useState(null);
  useEffect(() => {
    Promise.all([api.get('projects/').then(list), api.get('users/').then(list)]).then(([projects, people]) =>
      setOpts({ projects, people }),
    );
  }, []);
  const load = useCallback(() => {
    const end = new Date();
    const start = new Date(end);
    start.setDate(start.getDate() - days);
    api
      .get('dashboards/reports/', {
        params: {
          start: start.toISOString(),
          end: end.toISOString(),
          tz: -end.getTimezoneOffset(),
          ...Object.fromEntries(Object.entries(filters).filter(([, v]) => v)),
        },
      })
      .then(res => setR(res.data))
      .catch(() => setR({ error: true }));
  }, [days, filters]);
  useEffect(() => {
    load();
  }, [load]);

  return (
    <>
      <PageHeader title={tr('Reports')} sub={tr('Output, speed and quality, compared with the period before.')} />
      <div className="flex flex-wrap gap-2 mb-6">
        <div className="seg" role="group" aria-label={tr('Period')}>
          {RANGES.map(([d, l]) => (
            <button key={d} aria-pressed={days === d} onClick={() => setDays(d)}>
              {l}
            </button>
          ))}
        </div>
        <select
          className="field w-auto"
          value={filters.project}
          onChange={e => setFilters(f => ({ ...f, project: e.target.value }))}
          aria-label={tr('Project')}
        >
          <option value="">{tr('All projects')}</option>
          {opts.projects.map(p => (
            <option key={p.id} value={p.id}>
              {p.name}
            </option>
          ))}
        </select>
        <select
          className="field w-auto"
          value={filters.member}
          onChange={e => setFilters(f => ({ ...f, member: e.target.value }))}
          aria-label={tr('Person')}
        >
          <option value="">{tr('Whole team')}</option>
          {opts.people
            .filter(u => ['VIDEOGRAPHER', 'EDITOR'].includes(u.role))
            .map(u => (
              <option key={u.id} value={u.id}>
                {u.full_name || u.username}
              </option>
            ))}
        </select>
      </div>
      {!r ? (
        <Spinner />
      ) : r.error ? (
        <p className="text-tally">{tr('Couldn’t build the report.')}</p>
      ) : (
        <div className="space-y-6">
          <section className="panel grid grid-cols-2 md:grid-cols-3 xl:grid-cols-6 divide-hairline">
            {KPIS.map(([k, label, fmt], i) => {
              const now = r.kpis[k];
              const prev = r.previous[k];
              const delta = now != null && prev != null && typeof now === 'number' ? now - prev : null;
              const good = delta == null || delta === 0 ? null : delta > 0 !== LOWER_IS_BETTER.includes(k);
              return (
                <div
                  key={k}
                  className={`p-5 ${i ? 'border-l' : ''} ${i >= 2 ? 'border-t md:border-t-0' : ''} border-hairline`}
                >
                  <p className="text-[13px] text-graphite">{label}</p>
                  <p className="display text-[28px] font-semibold num mt-1">{fmt(now)}</p>
                  <p className={`text-[13px] num ${good == null ? 'text-mist' : good ? 'text-publish' : 'text-tally'}`}>
                    {delta == null || delta === 0
                      ? tr('Same as before')
                      : tr('{delta} vs before', { delta: `${delta > 0 ? '+' : ''}${Math.round(delta * 10) / 10}` })}
                  </p>
                </div>
              );
            })}
          </section>

          <section className="panel p-5 sm:p-6">
            <div className="flex flex-wrap items-baseline justify-between gap-2 mb-5">
              <h2 className="text-[17px] font-semibold">
                {tr('Output')} {r.period.weekly ? tr('per week') : tr('per day')}
              </h2>
              <span className="flex flex-wrap gap-4 text-[13px] text-graphite">
                {SERIES.map(([k, l, c]) => (
                  <span key={k} className="flex items-center gap-1.5">
                    <span className="w-2.5 h-2.5 rounded-[2px]" style={{ background: c }} />
                    {l}
                  </span>
                ))}
              </span>
            </div>
            <Bars rows={r.trend} />
          </section>

          <div className="grid xl:grid-cols-2 gap-6 items-start">
            <section className="panel p-5 sm:p-6 min-w-0">
              <h2 className="text-[17px] font-semibold mb-3">{tr('Team')}</h2>
              <div className="scroll-x">
                <table className="w-full text-[14px] num min-w-[460px]">
                  <thead>
                    <tr className="text-left text-graphite">
                      <th className="font-medium pb-2">{tr('Person')}</th>
                      <th className="font-medium text-right">{tr('Done')}</th>
                      <th className="font-medium text-right">{tr('On time')}</th>
                      <th className="font-medium text-right">{tr('column|Open')}</th>
                      <th className="font-medium text-right">{tr('Late')}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {r.team.map(m => (
                      <tr key={m.id} className="border-t border-hairline">
                        <td className="py-2.5">
                          <span className="flex items-center gap-2">
                            <Avatar name={m.name} size={24} />
                            <span>
                              <span className="block font-medium">{m.name}</span>
                              <span className="block text-[12px] text-mist">{ROLE_TEXT[m.role]}</span>
                            </span>
                          </span>
                        </td>
                        <td className="text-right font-semibold">{m.completed}</td>
                        <td className="text-right">{m.on_time_rate == null ? '—' : `${m.on_time_rate}%`}</td>
                        <td className="text-right">{m.open}</td>
                        <td className={`text-right ${m.overdue ? 'text-tally font-semibold' : 'text-graphite'}`}>
                          {m.overdue}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </section>
            <section className="panel p-5 sm:p-6 min-w-0">
              <h2 className="text-[17px] font-semibold mb-3">{tr('Projects')}</h2>
              <div className="scroll-x">
                <table className="w-full text-[14px] num min-w-[460px]">
                  <thead>
                    <tr className="text-left text-graphite">
                      <th className="font-medium pb-2">{tr('Project')}</th>
                      <th className="font-medium text-right">{tr('Published')}</th>
                      <th className="font-medium text-right">{tr('In production')}</th>
                      <th className="font-medium text-right">{tr('Late orders')}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {r.projects.map(p => (
                      <tr key={p.id} className="border-t border-hairline">
                        <td className="py-2.5">
                          <Link to={`/projects/${p.id}`} className="font-medium hover:underline underline-offset-2">
                            {p.name}
                          </Link>
                          <span className="block text-[12px] text-mist">
                            {p.client}
                            {p.end_date ? `, ${tr('until {date}', { date: day(p.end_date) })}` : ''}
                          </span>
                        </td>
                        <td className="text-right font-semibold">{p.published_in_period}</td>
                        <td className="text-right">{p.in_production}</td>
                        <td className={`text-right ${p.overdue_orders ? 'text-tally font-semibold' : 'text-graphite'}`}>
                          {p.overdue_orders}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </section>
          </div>
        </div>
      )}
    </>
  );
}

function Bars({ rows }) {
  const max = Math.max(1, ...rows.flatMap(r => SERIES.map(([k]) => r[k])));
  const every = Math.ceil(rows.length / 7);
  return (
    <>
      <div
        className="h-52 flex items-end gap-1 border-b border-hairline"
        role="img"
        aria-label={tr('Content created, orders completed and content published over time')}
      >
        {rows.map(r => (
          <div
            key={r.date}
            className="flex-1 h-full flex items-end gap-px"
            title={`${day(r.date)}: ${SERIES.map(([k, l]) => `${l} ${r[k]}`).join(', ')}`}
          >
            {SERIES.map(([k, , c]) => (
              <span
                key={k}
                className="flex-1 rounded-t-[2px] min-h-px"
                style={{ height: `${(r[k] / max) * 100}%`, background: c }}
              />
            ))}
          </div>
        ))}
      </div>
      <div className="flex gap-1 mt-1.5 h-4">
        {rows.map((r, i) => (
          <span key={r.date} className="flex-1 min-w-0 relative">
            {i % every === 0 && (
              <span
                className={`absolute top-0 text-[11px] text-mist whitespace-nowrap ${i === 0 ? 'left-0' : i > rows.length - every ? 'right-0' : 'left-1/2 -translate-x-1/2'}`}
              >
                {day(r.date)}
              </span>
            )}
          </span>
        ))}
      </div>
      <details className="mt-3 text-[13px]">
        <summary className="cursor-pointer text-graphite">{tr('Show as a table')}</summary>
        <table className="w-full mt-2 num">
          <thead>
            <tr className="text-left text-mist">
              <th className="font-medium py-1">{tr('Date')}</th>
              {SERIES.map(([k, l]) => (
                <th key={k} className="font-medium text-right">
                  {l}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map(r => (
              <tr key={r.date} className="border-t border-hairline">
                <td className="py-1">{day(r.date)}</td>
                {SERIES.map(([k]) => (
                  <td key={k} className="text-right">
                    {r[k]}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </details>
    </>
  );
}
