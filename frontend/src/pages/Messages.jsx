import { useCallback, useEffect, useState } from 'react';
import { Link, useNavigate, useOutletContext, useParams } from 'react-router-dom';
import { ArrowLeft, Search, ExternalLink } from 'lucide-react';
import api from '../lib/api';
import { ago } from '../lib/format';
import { Avatar, PageHeader } from '../ui';
import { usePulse } from '../lib/hooks';
import Chat from '../features/Chat';
import { tr } from '../lib/i18n';

export default function Messages() {
  const { taskId } = useParams();
  const navigate = useNavigate();
  const { refreshCounts } = useOutletContext() || {};
  const [rows, setRows] = useState(null);
  const [q, setQ] = useState('');
  const load = useCallback(
    () =>
      api
        .get('chats/')
        .then(r => setRows(r.data))
        .catch(() => setRows([])),
    [],
  );
  usePulse(load, 15000);
  useEffect(() => {
    if (!taskId || !refreshCounts) return undefined;
    const t = setTimeout(() => {
      refreshCounts();
      load();
    }, 1500);
    return () => clearTimeout(t);
  }, [taskId, refreshCounts, load]);

  const s = q.trim().toLowerCase();
  const shown = (rows || []).filter(r => !s || `${r.title} ${r.with_name} ${r.project_name}`.toLowerCase().includes(s));
  const open = rows?.find(r => String(r.task) === taskId);

  return (
    <>
      <div className={taskId ? 'hidden lg:block' : ''}>
        <PageHeader
          title={tr('Messages')}
          sub={tr('One conversation per order, between the manager and the person doing it.')}
        />
      </div>
      <div className="lg:grid lg:grid-cols-[340px_1fr] gap-6 items-start">
        <section className={`panel overflow-hidden ${taskId ? 'hidden lg:block' : ''}`}>
          <div className="p-3 border-b border-hairline">
            <label className="relative block">
              <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-mist" />
              <input
                value={q}
                onChange={e => setQ(e.target.value)}
                className="field pl-9"
                placeholder={tr('Find a conversation')}
                aria-label={tr('Find a conversation')}
              />
            </label>
          </div>
          {rows === null ? (
            <p className="p-6 text-graphite">{tr('Loading…')}</p>
          ) : shown.length === 0 ? (
            <p className="p-6 text-graphite text-[14px]">
              {q
                ? tr('No conversation matches.')
                : tr('No conversations yet. Start one from any order’s Messages section.')}
            </p>
          ) : (
            <ul className="max-h-[calc(100dvh-260px)] overflow-y-auto divide-y divide-hairline">
              {shown.map(r => (
                <li key={r.task}>
                  <button
                    onClick={() => navigate(`/messages/${r.task}`)}
                    aria-current={String(r.task) === taskId}
                    className={`w-full text-left flex gap-3 px-4 py-3.5 ${String(r.task) === taskId ? 'bg-haze' : 'hover:bg-haze/60'}`}
                  >
                    <Avatar name={r.with_name} size={36} />
                    <span className="min-w-0 flex-1">
                      <span className="flex items-baseline justify-between gap-2">
                        <span className={`truncate ${r.unread ? 'font-semibold' : 'font-medium'}`}>{r.with_name}</span>
                        {r.last_at && <span className="text-[12px] text-mist shrink-0">{ago(r.last_at)}</span>}
                      </span>
                      <span className="block text-[13px] text-graphite truncate">{r.title}</span>
                      <span
                        className={`flex items-center gap-2 text-[13px] truncate ${r.unread ? 'text-ink' : 'text-mist'}`}
                      >
                        <span className="truncate flex-1">{r.last_message || tr('No messages yet')}</span>
                        {r.unread > 0 && (
                          <span className="num min-w-5 h-5 px-1.5 rounded-full bg-tally text-paper text-[11px] font-semibold flex items-center justify-center">
                            {r.unread}
                          </span>
                        )}
                      </span>
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </section>

        <section
          className={`panel p-4 flex flex-col h-[calc(100dvh-170px)] lg:h-[calc(100dvh-210px)] ${taskId ? '' : 'hidden lg:flex'}`}
        >
          {taskId ? (
            <>
              <div className="flex items-center gap-2 pb-3 border-b border-hairline">
                <button
                  onClick={() => navigate('/messages')}
                  className="btn-icon lg:hidden"
                  aria-label={tr('All conversations')}
                >
                  <ArrowLeft size={18} />
                </button>
                <div className="min-w-0 flex-1">
                  <p className="font-semibold truncate">{open?.with_name || tr('Conversation')}</p>
                  <p className="text-[13px] text-graphite truncate">
                    {open ? `${open.title}, ${open.project_name}` : ''}
                  </p>
                </div>
                <Link to={`/orders/${taskId}`} className="btn btn-quiet btn-sm shrink-0">
                  <ExternalLink /> {tr('Order')}
                </Link>
              </div>
              <Chat key={taskId} taskId={taskId} className="flex-1 pt-2" />
            </>
          ) : (
            <div className="m-auto text-center text-graphite">
              <p className="font-semibold text-ink">{tr('Pick a conversation')}</p>
              <p className="text-[14px] mt-1">{tr('Messages also arrive on Telegram.')}</p>
            </div>
          )}
        </section>
      </div>
    </>
  );
}
