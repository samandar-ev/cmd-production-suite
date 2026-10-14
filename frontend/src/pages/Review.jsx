import { Link } from 'react-router-dom';
import { HardDrive, FileVideo, ChevronRight } from 'lucide-react';
import api, { list } from '../lib/api';
import { ago } from '../lib/format';
import { Avatar, Empty, PageHeader, Spinner } from '../ui';
import { useLoad } from '../lib/hooks';
import { tr } from '../lib/i18n';

const load = () => api.get('video-submissions/').then(list);
const DECIDED = { approved: [tr('Approved'), 'text-publish'], rejected: [tr('Changes requested'), 'text-tally'] };

function Item({ s, waiting }) {
  const inPerson = s.delivery === 'in_person';
  return (
    <li>
      <Link to={`/review/${s.id}`} className="flex items-center gap-4 px-4 sm:px-5 py-4 hover:bg-haze">
        <span
          className={`w-11 h-11 rounded-[10px] flex items-center justify-center shrink-0 ${waiting ? 'bg-review/10 text-review' : 'bg-haze text-graphite'}`}
        >
          {inPerson ? <HardDrive size={20} /> : <FileVideo size={20} />}
        </span>
        <span className="min-w-0 flex-1">
          <span className="block font-semibold truncate">
            {s.content_item_title || s.project_name}
            <span className="text-graphite font-normal">, {tr('version {n}', { n: s.version })}</span>
          </span>
          <span className="flex items-center gap-1.5 text-[13px] text-graphite truncate">
            <Avatar name={s.uploader_name} size={16} />
            {s.uploader_name}, {inPerson ? tr('handed over in person') : tr('uploaded')} {ago(s.created_at)}
          </span>
        </span>
        {waiting ? (
          <span className="btn btn-primary btn-sm shrink-0">{inPerson ? tr('Confirm') : tr('Review')}</span>
        ) : (
          <span className={`text-[13px] font-semibold shrink-0 ${DECIDED[s.status]?.[1]}`}>
            {DECIDED[s.status]?.[0]}
          </span>
        )}
        <ChevronRight size={18} className="text-mist shrink-0 hidden sm:block" />
      </Link>
    </li>
  );
}

export default function Review() {
  const { data } = useLoad(load, []);
  if (!data)
    return (
      <>
        <PageHeader title={tr('Review')} />
        <Spinner />
      </>
    );
  const waiting = data
    .filter(s => s.status === 'pending')
    .sort((a, b) => new Date(a.created_at) - new Date(b.created_at));
  const decided = data.filter(s => ['approved', 'rejected'].includes(s.status)).slice(0, 12);
  return (
    <>
      <PageHeader
        title={tr('Review')}
        sub={
          waiting.length
            ? tr('{n} waiting for your decision, oldest first.', { n: waiting.length })
            : tr('Nothing waiting for a decision.')
        }
      />
      <section className="panel overflow-hidden mb-8">
        {waiting.length === 0 ? (
          <Empty title={tr('You’re all caught up')}>
            {tr('When someone sends work or hands over a drive, it appears here — and you’ll get a message.')}
          </Empty>
        ) : (
          <ul className="divide-y divide-hairline">
            {waiting.map(s => (
              <Item key={s.id} s={s} waiting />
            ))}
          </ul>
        )}
      </section>
      {decided.length > 0 && (
        <section>
          <h2 className="text-[17px] font-semibold mb-3">{tr('Recently decided')}</h2>
          <ul className="panel divide-y divide-hairline overflow-hidden">
            {decided.map(s => (
              <Item key={s.id} s={s} />
            ))}
          </ul>
        </section>
      )}
    </>
  );
}
