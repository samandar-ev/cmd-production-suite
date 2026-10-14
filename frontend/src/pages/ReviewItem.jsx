import { useCallback, useEffect, useRef, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { ArrowLeft, Check, Undo2, HardDrive, Download, FileText, Send, Clock } from 'lucide-react';
import api, { errorText } from '../lib/api';
import { ago, stamp } from '../lib/format';
import { Avatar, Spinner } from '../ui';
import { useToast } from '../lib/hooks';
import { tr } from '../lib/i18n';

const tc = s => {
  const m = Math.floor(s / 60);
  return `${m}:${String(Math.floor(s % 60)).padStart(2, '0')}`;
};
const MEDIA = {
  hard_drive: tr('Hard drive'),
  ssd: 'SSD',
  memory_card: tr('Memory card'),
  usb: tr('USB stick'),
  other: tr('Drive'),
};

export default function ReviewItem() {
  const { id } = useParams();
  const navigate = useNavigate();
  const toast = useToast();
  const video = useRef(null);
  const [d, setD] = useState(null);
  const [err, setErr] = useState('');
  const [note, setNote] = useState('');
  const [pin, setPin] = useState(true);
  const [verdict, setVerdict] = useState('');
  const [busy, setBusy] = useState(false);
  const [dur, setDur] = useState(0);

  const load = useCallback(
    () =>
      api
        .get(`video-submissions/${id}/`)
        .then(r => setD(r.data))
        .catch(e => setErr(errorText(e, tr('This version isn’t available.')))),
    [id],
  );
  useEffect(() => {
    load();
  }, [load]);
  if (err) return <p className="text-tally">{err}</p>;
  if (!d) return <Spinner label={tr('Opening')} />;

  const inPerson = d.delivery === 'in_person';
  const seek = s => {
    if (video.current) {
      video.current.currentTime = s;
      video.current.play();
    }
  };
  const addNote = async e => {
    e.preventDefault();
    if (!note.trim()) return;
    const at = pin && video.current ? Math.floor(video.current.currentTime) : null;
    await api
      .post(`video-submissions/${id}/comments/`, { body: note.trim(), timestamp_seconds: at })
      .catch(e2 => toast(errorText(e2), 'error'));
    setNote('');
    load();
  };
  const decide = async decision => {
    if (decision === 'rejected' && !verdict.trim()) {
      toast(tr('Say what to change, so they know what to fix'), 'error');
      return;
    }
    setBusy(true);
    try {
      await api.post(`video-submissions/${id}/review/`, { decision, comment: verdict.trim() });
      toast(
        decision === 'approved'
          ? inPerson
            ? tr('Receipt confirmed')
            : tr('Approved — the next step can start')
          : tr('Sent back with your notes'),
      );
      load();
    } catch (e2) {
      toast(errorText(e2), 'error');
    } finally {
      setBusy(false);
    }
  };
  const pinned = (d.comments || []).filter(c => c.timestamp_seconds != null);

  return (
    <>
      <button onClick={() => navigate(-1)} className="btn btn-ghost btn-sm -ml-3 mb-3">
        <ArrowLeft /> {tr('Back')}
      </button>
      <header className="flex flex-wrap items-end justify-between gap-3 mb-5">
        <div className="min-w-0">
          <p className="text-[14px] text-graphite">{d.project_name}</p>
          <h1 className="display text-[24px] sm:text-[30px] font-semibold leading-tight">
            {d.content_item_title || d.project_name} <span className="text-mist">v{d.version}</span>
          </h1>
          <p className="text-graphite mt-1 flex items-center gap-2">
            <Avatar name={d.uploader_name} size={20} />
            {d.uploader_name}, {ago(d.created_at)}
          </p>
        </div>
        {d.task && (
          <Link to={`/orders/${d.task}`} className="btn btn-quiet btn-sm">
            {tr('Open the order')}
          </Link>
        )}
      </header>

      <div className="grid xl:grid-cols-[1fr_380px] gap-6 items-start">
        <div className="min-w-0 space-y-4">
          {inPerson ? (
            <div className="panel p-8 sm:p-12 text-center">
              <HardDrive size={40} className="mx-auto text-shoot" />
              <p className="display text-[20px] font-semibold mt-4">{tr('Handed over in person')}</p>
              <p className="text-graphite mt-2">
                {tr('{media}, given to {name}', {
                  media: MEDIA[d.handover_media],
                  name: d.handover_to_name || tr('the manager'),
                })}
                {d.handover_at ? `, ${stamp(d.handover_at)}` : ''}.
              </p>
              <p className="text-[14px] text-graphite mt-4 max-w-[46ch] mx-auto">
                {tr('The footage isn’t stored in CMD — it’s on the drive. Check it, then confirm receipt.')}
              </p>
            </div>
          ) : d.deleted ? (
            <div className="panel p-10 text-center text-graphite">
              {tr('This file was removed to free up storage. The notes and decision are kept below.')}
            </div>
          ) : d.kind === 'video' ? (
            <div className="rounded-[var(--radius-panel)] overflow-hidden bg-ink">
              <video
                ref={video}
                src={d.view_url}
                controls
                playsInline
                preload="metadata"
                className="w-full max-h-[70vh] bg-ink"
                onLoadedMetadata={e => setDur(e.target.duration)}
              />
              {dur > 0 && pinned.length > 0 && (
                <div className="relative h-7 mx-3 mb-2" aria-label={tr('Notes on the timeline')}>
                  <div className="absolute inset-x-0 top-3 h-[2px] bg-paper/20 rounded-full" />
                  {pinned.map(c => (
                    <button
                      key={c.id}
                      onClick={() => seek(c.timestamp_seconds)}
                      title={`${tc(c.timestamp_seconds)}: ${c.body}`}
                      className="absolute top-1 w-3 h-5 -ml-1.5 rounded-[3px] bg-tally hover:scale-110"
                      style={{ left: `${(c.timestamp_seconds / dur) * 100}%` }}
                    />
                  ))}
                </div>
              )}
            </div>
          ) : d.kind === 'image' ? (
            <img
              src={d.view_url}
              alt={d.original_filename}
              className="w-full max-h-[70vh] object-contain rounded-[var(--radius-panel)] bg-ink"
            />
          ) : (
            <div className="panel p-10 text-center">
              <FileText size={36} className="mx-auto text-graphite" />
              <p className="font-semibold mt-3">{d.original_filename}</p>
              <p className="text-graphite text-[14px] mt-1">
                {tr('This kind of file can’t be previewed. Download it to open it.')}
              </p>
            </div>
          )}
          {!inPerson && !d.deleted && d.download_url && (
            <a href={d.download_url} className="btn btn-quiet btn-sm">
              <Download /> {tr('Download')} {d.original_filename}
            </a>
          )}
          {d.editor_note && (
            <section className="panel p-5">
              <h2 className="font-semibold mb-1.5">{inPerson ? tr('What’s on it') : tr('Their note')}</h2>
              <p className="whitespace-pre-line text-graphite">{d.editor_note}</p>
            </section>
          )}
        </div>

        <aside className="space-y-4 min-w-0">
          {d.status !== 'pending' ? (
            <section
              className={`panel p-5 border-l-4 ${d.status === 'approved' ? 'border-l-publish' : 'border-l-tally'}`}
            >
              <p className="font-semibold">
                {d.status === 'approved'
                  ? inPerson
                    ? tr('Receipt confirmed')
                    : tr('Approved')
                  : tr('Changes requested')}
              </p>
              <p className="text-[14px] text-graphite">
                {d.reviewer_name}, {d.reviewed_at ? ago(d.reviewed_at) : ''}
              </p>
              {d.review_comment && <p className="mt-3 whitespace-pre-line">{d.review_comment}</p>}
            </section>
          ) : d.can_review ? (
            <section className="panel p-5">
              <h2 className="text-[17px] font-semibold">{inPerson ? tr('Have the drive?') : tr('Your decision')}</h2>
              <textarea
                rows={3}
                className="field mt-3"
                value={verdict}
                onChange={e => setVerdict(e.target.value)}
                placeholder={
                  inPerson
                    ? tr('Anything missing? (needed if you send it back)')
                    : tr('What should change? (needed if you send it back)')
                }
                aria-label={tr('Decision note')}
              />
              <div className="grid grid-cols-2 gap-2 mt-3">
                <button onClick={() => decide('rejected')} disabled={busy} className="btn btn-quiet">
                  <Undo2 /> {tr('Send back')}
                </button>
                <button onClick={() => decide('approved')} disabled={busy} className="btn btn-primary">
                  <Check /> {inPerson ? tr('Confirm receipt') : tr('Approve')}
                </button>
              </div>
              <p className="text-[13px] text-mist mt-3">
                {inPerson
                  ? tr('Confirming completes the shoot and unlocks the edit.')
                  : tr('Approving completes this step; the next one starts automatically.')}
              </p>
            </section>
          ) : (
            <section className="panel p-5">
              <p className="font-semibold flex items-center gap-2">
                <Clock size={16} /> {tr('Waiting for review')}
              </p>
              <p className="text-[14px] text-graphite mt-1">{tr('You’ll get a message when the manager decides.')}</p>
            </section>
          )}

          <section className="panel p-5">
            <h2 className="text-[17px] font-semibold mb-3">
              {tr('Notes')}{' '}
              {d.comments?.length > 0 && <span className="text-graphite font-normal num">{d.comments.length}</span>}
            </h2>
            <ul className="space-y-3.5 max-h-[420px] overflow-y-auto">
              {(d.comments || []).length === 0 && (
                <li className="text-[14px] text-graphite">
                  {tr('No notes yet.')}
                  {d.kind === 'video' ? ` ${tr('Pause the video and write one — it’s pinned to that moment.')}` : ''}
                </li>
              )}
              {(d.comments || []).map(c => (
                <li key={c.id} className="flex gap-2.5">
                  <Avatar name={c.author_name} size={24} />
                  <div className="min-w-0">
                    <p className="text-[13px]">
                      <span className="font-semibold">{c.author_name}</span>{' '}
                      <span className="text-mist">{ago(c.created_at)}</span>
                    </p>
                    <p className="text-[14px]">
                      {c.timestamp_seconds != null && (
                        <button
                          onClick={() => seek(c.timestamp_seconds)}
                          className="font-semibold text-tally num mr-1.5 hover:underline"
                        >
                          {tc(c.timestamp_seconds)}
                        </button>
                      )}
                      {c.body}
                    </p>
                  </div>
                </li>
              ))}
            </ul>
            <form onSubmit={addNote} className="mt-4">
              <div className="flex gap-2">
                <input
                  value={note}
                  onChange={e => setNote(e.target.value)}
                  className="field"
                  placeholder={tr('Write a note')}
                  aria-label={tr('Note')}
                />
                <button disabled={!note.trim()} className="btn btn-quiet w-10 px-0" aria-label={tr('Add note')}>
                  <Send />
                </button>
              </div>
              {d.kind === 'video' && !inPerson && (
                <label className="flex items-center gap-2 text-[13px] text-graphite mt-2 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={pin}
                    onChange={e => setPin(e.target.checked)}
                    className="accent-ink"
                  />{' '}
                  {tr('Pin to the current moment in the video')}
                </label>
              )}
            </form>
          </section>

          {d.history?.length > 1 && (
            <section className="panel p-5">
              <h2 className="text-[17px] font-semibold mb-2">{tr('Versions')}</h2>
              <ul>
                {d.history.map(v => (
                  <li key={v.id}>
                    <Link
                      to={`/review/${v.id}`}
                      className={`flex justify-between gap-3 py-2 px-2 -mx-2 rounded-[8px] hover:bg-haze ${v.id === d.id ? 'font-semibold' : ''}`}
                    >
                      <span>
                        {tr('Version')} {v.version}
                      </span>
                      <span className="text-[13px] text-graphite">
                        {
                          { pending: tr('Waiting'), approved: tr('Approved'), rejected: tr('Changes requested') }[
                            v.status
                          ]
                        }
                      </span>
                    </Link>
                  </li>
                ))}
              </ul>
            </section>
          )}
        </aside>
      </div>
    </>
  );
}
