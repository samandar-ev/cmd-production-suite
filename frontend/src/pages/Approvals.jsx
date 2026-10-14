import { useCallback, useState } from 'react';
import { Bot, Check, X, Landmark, Trash2 } from 'lucide-react';
import api, { errorText } from '../lib/api';
import { ago } from '../lib/format';
import { Empty, PageHeader, Spinner } from '../ui';
import { useToast } from '../lib/hooks';
import { usePulse } from '../lib/hooks';
import { tr } from '../lib/i18n';

export default function Approvals() {
  const toast = useToast();
  const [rows, setRows] = useState(null);
  const load = useCallback(
    () =>
      api
        .get('ai/approvals/')
        .then(r => setRows(r.data))
        .catch(() => setRows([])),
    [],
  );
  usePulse(load, 5000);
  const decide = async (a, approve) => {
    try {
      await api.post(`ai/approvals/${a.id}/decide/`, { approve });
      toast(approve ? tr('Approved — Claude can continue') : tr('Denied'));
      load();
    } catch (err) {
      toast(errorText(err), 'error');
    }
  };
  if (!rows)
    return (
      <>
        <PageHeader title={tr('Claude’s requests')} />
        <Spinner />
      </>
    );
  const pending = rows.filter(r => r.status === 'pending');
  const past = rows.filter(r => r.status !== 'pending');
  const Icon = ({ kind }) => (
    <span
      className={`w-10 h-10 rounded-[10px] flex items-center justify-center shrink-0 ${kind === 'delete' ? 'bg-tally/10 text-tally' : 'bg-haze text-ink'}`}
    >
      {kind === 'delete' ? <Trash2 size={18} /> : <Landmark size={18} />}
    </span>
  );
  return (
    <>
      <PageHeader
        title={tr('Claude’s requests')}
        sub={tr('Claude asks before it sees money or deletes anything. Approve only what you asked it to do.')}
      />
      <section className="panel overflow-hidden mb-8">
        {pending.length === 0 ? (
          <Empty title={tr('Nothing waiting')}>
            <Bot className="inline -mt-1 mr-1" size={16} />
            {tr('Requests from Claude appear here and in Telegram.')}
          </Empty>
        ) : (
          <ul className="divide-y divide-hairline">
            {pending.map(a => (
              <li key={a.id} className="flex flex-col sm:flex-row sm:items-center gap-3 px-5 py-4">
                <div className="flex items-start gap-3 flex-1 min-w-0">
                  <Icon kind={a.kind} />
                  <div className="min-w-0">
                    <p className="font-semibold">
                      {a.kind === 'delete' ? tr('Wants to delete') : tr('Wants to see or change money')}
                    </p>
                    <p className="text-[14px] text-graphite break-words">{a.summary}</p>
                    <p className="text-[12px] text-mist mt-0.5">
                      {a.app}, {ago(a.created_at)}
                    </p>
                  </div>
                </div>
                <div className="flex gap-2 shrink-0">
                  <button onClick={() => decide(a, false)} className="btn btn-quiet">
                    <X /> {tr('Deny')}
                  </button>
                  <button onClick={() => decide(a, true)} className="btn btn-primary">
                    <Check /> {tr('Approve')}
                  </button>
                </div>
              </li>
            ))}
          </ul>
        )}
      </section>
      {past.length > 0 && (
        <>
          <h2 className="text-[17px] font-semibold mb-3">{tr('Earlier')}</h2>
          <ul className="panel divide-y divide-hairline overflow-hidden">
            {past.map(a => (
              <li key={a.id} className="flex items-center gap-3 px-5 py-3">
                <Icon kind={a.kind} />
                <p className="flex-1 min-w-0 text-[14px] break-words">{a.summary}</p>
                <span
                  className={`text-[13px] font-semibold shrink-0 ${a.status === 'denied' ? 'text-tally' : 'text-publish'}`}
                >
                  {a.status === 'denied' ? tr('Denied') : tr('Approved')}
                </span>
              </li>
            ))}
          </ul>
        </>
      )}
    </>
  );
}
