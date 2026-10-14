import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { CalendarClock, Check } from 'lucide-react';
import { STAGES } from '../lib/stages';
import { time } from '../lib/format';
import { tr } from '../lib/i18n';

const colorOf = it =>
  it.kind === 'publish'
    ? 'var(--color-publish)'
    : it.kind === 'event'
      ? 'var(--color-ink)'
      : it.kind === 'todo'
        ? 'var(--color-mist)'
        : STAGES.find(s => s.key === it.stage)?.color || 'var(--color-plan)';

const KIND = { order: tr('Order due'), publish: tr('Publish'), event: tr('Event'), todo: tr('To-do') };

const useNow = () => {
  const [now, setNow] = useState(() => new Date());
  useEffect(() => {
    const t = setInterval(() => setNow(new Date()), 60000);
    return () => clearInterval(t);
  }, []);
  return now;
};

function Clip({ it, style }) {
  const body = (
    <span className="flex h-full rounded-[var(--radius-clip)] bg-paper border border-hairline overflow-hidden hover:border-mist transition-colors">
      <span className="w-1.5 shrink-0" style={{ background: colorOf(it) }} />
      <span className="min-w-0 px-2.5 py-1.5">
        <span className={`block text-[13px] font-semibold truncate ${it.done ? 'line-through text-mist' : ''}`}>
          {it.title}
        </span>
        <span className="block text-[12px] text-graphite truncate num">
          {it.allDay ? KIND[it.kind] : time(it.at)}
          {it.who ? `, ${it.who}` : ''}
        </span>
      </span>
    </span>
  );
  return it.to ? (
    <Link to={it.to} className="absolute block" style={style} title={`${KIND[it.kind]}: ${it.title}`}>
      {body}
    </Link>
  ) : (
    <span className="absolute block" style={style} title={`${KIND[it.kind]}: ${it.title}`}>
      {body}
    </span>
  );
}

export default function DayTimeline({ items }) {
  const now = useNow();
  const timed = items.filter(i => !i.allDay).sort((a, b) => a.at - b.at);
  const allDay = items.filter(i => i.allDay);

  const hours = [...timed.map(i => i.at.getHours() + i.at.getMinutes() / 60), now.getHours() + now.getMinutes() / 60];
  const from = Math.max(0, Math.min(8, Math.floor(Math.min(...hours))));
  const to = Math.min(24, Math.max(20, Math.ceil(Math.max(...hours) + 1.5)));
  const span = to - from;
  const pos = d => ((d.getHours() + d.getMinutes() / 60 - from) / span) * 100;

  const CLIP = 14;
  const lanes = [];
  const placed = timed.map(it => {
    const left = Math.min(pos(it.at), 100 - CLIP);
    let lane = lanes.findIndex(endsAt => endsAt <= left);
    if (lane === -1) {
      lane = lanes.length;
      lanes.push(0);
    }
    lanes[lane] = left + CLIP + 0.5;
    return { it, lane, left };
  });
  const laneCount = Math.max(1, lanes.length);
  const nowPos = pos(now);

  return (
    <div>
      <div className="hidden sm:block">
        {allDay.length > 0 && (
          <div className="flex flex-wrap gap-2 mb-4">
            {allDay.map(it => (
              <Link
                key={it.id}
                to={it.to || '#'}
                className="inline-flex items-center gap-2 h-8 pl-2 pr-3 rounded-[var(--radius-clip)] bg-paper border border-hairline text-[13px] hover:border-mist"
              >
                <span className="w-1.5 h-4 rounded-full" style={{ background: colorOf(it) }} />
                <span className={`font-medium ${it.done ? 'line-through text-mist' : ''}`}>{it.title}</span>
                <span className="text-mist">{KIND[it.kind]}</span>
              </Link>
            ))}
          </div>
        )}
        <div className="relative">
          <div className="relative" style={{ height: laneCount * 56 + 8 }}>
            {Array.from({ length: span + 1 }, (_, i) => (
              <span
                key={i}
                className="absolute top-0 bottom-0 border-l border-hairline/70"
                style={{ left: `${(i / span) * 100}%` }}
              />
            ))}
            {placed.map(({ it, lane, left }) => (
              <Clip
                key={it.id}
                it={it}
                style={{ left: `${left}%`, top: lane * 56 + 4, height: 50, width: `calc(${CLIP}% - 4px)` }}
              />
            ))}
            {nowPos >= 0 && nowPos <= 100 && (
              <span
                aria-label={tr('Now, {time}', { time: time(now) })}
                className="absolute -top-2 -bottom-2 w-[2px] bg-tally z-10 pointer-events-none"
                style={{ left: `${nowPos}%` }}
              >
                <span className="absolute -top-0.5 left-1/2 -translate-x-1/2 w-2.5 h-2.5 rotate-45 rounded-[2px] bg-tally" />
              </span>
            )}
          </div>
          <div className="relative h-6 mt-2">
            {Array.from(
              { length: span + 1 },
              (_, i) =>
                i % (span > 14 ? 3 : 2) === 0 &&
                Math.abs((i / span) * 100 - nowPos) > 5 && (
                  <span
                    key={i}
                    className="absolute -translate-x-1/2 text-[12px] text-mist num"
                    style={{ left: `${(i / span) * 100}%` }}
                  >
                    {String(from + i).padStart(2, '0')}:00
                  </span>
                ),
            )}
            {nowPos >= 0 && nowPos <= 100 && (
              <span
                className="absolute -translate-x-1/2 text-[12px] font-semibold text-tally num bg-paper px-1"
                style={{ left: `${nowPos}%` }}
              >
                {time(now)}
              </span>
            )}
          </div>
          {timed.length === 0 && (
            <p className="absolute inset-x-0 top-3 text-center text-graphite text-[14px]">
              <CalendarClock size={16} className="inline -mt-0.5 mr-1.5" />
              {tr('Nothing scheduled with a time today.')}
            </p>
          )}
        </div>
      </div>

      <ol className="sm:hidden -mx-1">
        {[...allDay, ...timed].length === 0 && (
          <li className="text-graphite py-4 px-1">{tr('Nothing scheduled today.')}</li>
        )}
        {allDay.map(it => (
          <AgendaRow key={it.id} it={it} />
        ))}
        {timed.map((it, i) => (
          <li key={it.id}>
            {(i === 0 ? it.at > now : timed[i - 1].at <= now && it.at > now) && <NowLine now={now} />}
            <AgendaRow it={it} li={false} />
          </li>
        ))}
        {timed.length > 0 && timed[timed.length - 1].at <= now && (
          <li>
            <NowLine now={now} />
          </li>
        )}
      </ol>
    </div>
  );
}

const NowLine = ({ now }) => (
  <div className="flex items-center gap-2 py-1.5 px-1" aria-label={tr('Now, {time}', { time: time(now) })}>
    <span className="text-[12px] font-semibold text-tally num w-11">{time(now)}</span>
    <span className="flex-1 h-[2px] bg-tally rounded-full" />
  </div>
);

function AgendaRow({ it, li = true }) {
  const inner = (
    <Link to={it.to || '#'} className="flex items-center gap-3 py-2.5 px-1 rounded-[10px] active:bg-haze">
      <span className="text-[13px] text-graphite num w-11 shrink-0">{it.allDay ? tr('All day') : time(it.at)}</span>
      <span className="w-1 self-stretch rounded-full shrink-0" style={{ background: colorOf(it) }} />
      <span className="min-w-0 flex-1">
        <span className={`block font-medium truncate ${it.done ? 'line-through text-mist' : ''}`}>{it.title}</span>
        <span className="block text-[13px] text-graphite truncate">
          {KIND[it.kind]}
          {it.who ? `, ${it.who}` : ''}
        </span>
      </span>
      {it.done && <Check size={16} className="text-publish" />}
    </Link>
  );
  return li ? <li>{inner}</li> : inner;
}
