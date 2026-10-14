import { useEffect, useRef, useState } from 'react';
import Uppy from '@uppy/core';
import AwsS3 from '@uppy/aws-s3';
import { UploadCloud, HardDrive, Pause, Play, RotateCcw, CheckCircle2 } from 'lucide-react';
import api, { errorText } from '../lib/api';
import { Dialog } from '../ui';
import { useConfirm } from '../lib/hooks';
import { tr } from '../lib/i18n';

const PART = 10 * 1024 * 1024;
const MAX = 500 * 1000 * 1000;
const MEDIA = [
  ['hard_drive', tr('Hard drive')],
  ['ssd', 'SSD'],
  ['memory_card', tr('Memory card')],
  ['usb', tr('USB stick')],
  ['other', tr('Other')],
];
const size = n => (n >= 1e9 ? `${(n / 1e9).toFixed(1)} GB` : `${Math.max(1, Math.round(n / 1e6))} MB`);
const localNow = () => {
  const d = new Date();
  d.setSeconds(0, 0);
  return new Date(d - d.getTimezoneOffset() * 6e4).toISOString().slice(0, 16);
};

export default function SendWork({ task, onClose, onSent }) {
  const confirm = useConfirm();
  const [mode, setMode] = useState('upload');
  const [file, setFile] = useState(null);
  const [note, setNote] = useState('');
  const [phase, setPhase] = useState('pick');
  const [progress, setProgress] = useState(0);
  const [error, setError] = useState('');
  const [drive, setDrive] = useState({ media: 'hard_drive', to: '', at: localNow() });
  const [receivers, setReceivers] = useState([]);
  const uppy = useRef(null);
  const noteRef = useRef('');
  useEffect(() => {
    noteRef.current = note;
  }, [note]);

  useEffect(() => {
    api
      .get('video-submissions/receivers/', { params: { task: task.id } })
      .then(r => {
        setReceivers(r.data);
        setDrive(d => ({ ...d, to: d.to || String(r.data[0]?.id || '') }));
      })
      .catch(() => {});
  }, [task.id]);

  useEffect(() => {
    const subs = new Map();
    const fail = err => {
      throw new Error(errorText(err, tr('Upload failed.')));
    };
    const u = new Uppy({ autoProceed: false, restrictions: { maxNumberOfFiles: 1 } }).use(AwsS3, {
      shouldUseMultipart: true,
      getChunkSize: () => PART,
      limit: 4,
      retryDelays: [0, 1000, 3000, 5000, 10000],
      async createMultipartUpload(f) {
        const { data } = await api
          .post('video-submissions/', {
            task: task.id,
            filename: f.name,
            size: f.size,
            content_type: f.type,
            note: noteRef.current,
          })
          .catch(fail);
        subs.set(f.id, data.id);
        return { uploadId: data.uploadId, key: data.key };
      },
      async signPart(f, { partNumber, signal }) {
        const { data } = await api
          .post(`video-submissions/${subs.get(f.id)}/sign-part/`, { part_number: partNumber }, { signal })
          .catch(fail);
        return { method: 'PUT', url: data.url };
      },
      async listParts(f, { signal }) {
        return (await api.get(`video-submissions/${subs.get(f.id)}/parts/`, { signal }).catch(fail)).data;
      },
      async completeMultipartUpload(f, { parts, signal }) {
        await api
          .post(
            `video-submissions/${subs.get(f.id)}/complete/`,
            { parts: parts.map(p => ({ PartNumber: p.PartNumber, ETag: p.ETag })) },
            { signal },
          )
          .catch(fail);
        return {};
      },
      async abortMultipartUpload(f) {
        const id = subs.get(f.id);
        if (id) await api.post(`video-submissions/${id}/abort/`).catch(() => {});
      },
    });
    u.on('upload-progress', (_f, p) => setProgress(p.bytesTotal ? p.bytesUploaded / p.bytesTotal : 0));
    u.on('upload-error', (_f, err) => {
      setError(err?.message || tr('Upload failed.'));
      setPhase('failed');
    });
    u.on('upload-success', () => {
      setPhase('done');
      onSent?.();
    });
    uppy.current = u;
    const guard = e => {
      if (u.getFiles().some(f => f.progress?.uploadStarted && !f.progress?.uploadComplete)) e.preventDefault();
    };
    window.addEventListener('beforeunload', guard);
    return () => {
      window.removeEventListener('beforeunload', guard);
      u.destroy();
    };
  }, [task.id, onSent]);

  const pick = f => {
    setError('');
    if (!f) return;
    if (f.size > MAX) {
      setError(
        tr('That file is {size}. The limit is 500 MB — export a smaller version, or hand the footage over in person.', {
          size: size(f.size),
        }),
      );
      return;
    }
    setFile(f);
  };
  const upload = () => {
    const u = uppy.current;
    u.cancelAll();
    setError('');
    setProgress(0);
    u.addFile({ name: file.name, type: file.type || 'application/octet-stream', data: file, source: 'local' });
    setPhase('sending');
    u.upload().catch(() => {});
  };
  const handOver = async () => {
    setPhase('sending');
    setError('');
    try {
      await api.post('video-submissions/handover/', {
        task: task.id,
        media: drive.media,
        handed_to: drive.to || null,
        handed_over_at: new Date(drive.at).toISOString(),
        note,
      });
      setPhase('done');
      onSent?.();
    } catch (err) {
      setError(errorText(err));
      setPhase('pick');
    }
  };
  const busy = phase === 'sending' || phase === 'paused';
  const close = async () => {
    if (
      busy &&
      mode === 'upload' &&
      !(await confirm({
        title: tr('Stop this upload?'),
        body: tr('What’s uploaded so far is discarded.'),
        action: tr('Stop upload'),
        danger: true,
      }))
    )
      return;
    onClose();
  };

  if (phase === 'done') {
    return (
      <Dialog
        title={mode === 'upload' ? tr('Sent for review') : tr('Handover recorded')}
        onClose={onClose}
        footer={
          <button onClick={onClose} className="btn btn-primary">
            {tr('Done')}
          </button>
        }
      >
        <div className="flex gap-3 items-start">
          <CheckCircle2 className="text-publish shrink-0 mt-0.5" />
          <p>
            {mode === 'upload'
              ? tr('Your manager has been told. You’ll get a message when they’ve looked at it.')
              : tr('Your manager will confirm once they have the drive. You’ll get a message.')}
          </p>
        </div>
      </Dialog>
    );
  }

  return (
    <Dialog
      title={tr('Send work for review')}
      sub={task.title}
      onClose={close}
      footer={
        <>
          <button onClick={close} className="btn btn-ghost">
            {tr('Cancel')}
          </button>
          {mode === 'upload' && phase === 'sending' && (
            <button
              onClick={() => {
                uppy.current.pauseAll();
                setPhase('paused');
              }}
              className="btn btn-quiet"
            >
              <Pause /> {tr('Pause')}
            </button>
          )}
          {mode === 'upload' && phase === 'paused' && (
            <button
              onClick={() => {
                uppy.current.resumeAll();
                setPhase('sending');
              }}
              className="btn btn-quiet"
            >
              <Play /> {tr('Resume')}
            </button>
          )}
          {mode === 'upload' && phase === 'failed' && (
            <button
              onClick={() => {
                setPhase('sending');
                uppy.current.retryAll().catch(() => {});
              }}
              className="btn btn-primary"
            >
              <RotateCcw /> {tr('Try again')}
            </button>
          )}
          {mode === 'upload' && phase === 'pick' && (
            <button onClick={upload} disabled={!file} className="btn btn-primary">
              <UploadCloud /> {tr('Upload and send')}
            </button>
          )}
          {mode === 'drive' && (
            <button onClick={handOver} disabled={busy} className="btn btn-primary">
              <HardDrive /> {busy ? tr('Saving…') : tr('Confirm handover')}
            </button>
          )}
        </>
      }
    >
      {!busy && phase !== 'failed' && (
        <div className="seg w-full mb-5" role="group" aria-label={tr('How are you sending it?')}>
          <button className="flex-1" aria-pressed={mode === 'upload'} onClick={() => setMode('upload')}>
            {tr('Upload a file')}
          </button>
          <button className="flex-1" aria-pressed={mode === 'drive'} onClick={() => setMode('drive')}>
            {tr('Hand over in person')}
          </button>
        </div>
      )}
      {error && (
        <p role="alert" className="text-tally mb-4">
          {error}
        </p>
      )}
      {mode === 'upload' ? (
        busy || phase === 'failed' ? (
          <div className="rounded-[12px] bg-haze p-4">
            <div className="flex justify-between text-[14px] font-medium mb-2">
              <span className="truncate pr-4">{file?.name}</span>
              <span className="num">{Math.floor(progress * 100)}%</span>
            </div>
            <div className="h-2 rounded-full bg-hairline overflow-hidden">
              <div className="h-full bg-ink transition-[width]" style={{ width: `${progress * 100}%` }} />
            </div>
            <p className="text-[13px] text-graphite mt-2">
              {phase === 'paused' ? tr('Paused. ') : ''}
              {tr('Keep this page open until it finishes. If the connection drops, it picks up where it stopped.')}
            </p>
          </div>
        ) : (
          <label
            className="flex flex-col items-center justify-center gap-2 p-8 rounded-[12px] border-2 border-dashed border-hairline hover:border-mist cursor-pointer text-center"
            onDragOver={e => e.preventDefault()}
            onDrop={e => {
              e.preventDefault();
              pick(e.dataTransfer.files[0]);
            }}
          >
            <UploadCloud className="text-graphite" />
            <span className="font-semibold">{file ? file.name : tr('Choose a file or drop it here')}</span>
            <span className="text-[13px] text-graphite">
              {file
                ? tr('{size}, tap to choose another', { size: size(file.size) })
                : tr('Video, photos, a ZIP of several files — up to 500 MB')}
            </span>
            <input type="file" className="sr-only" onChange={e => pick(e.target.files[0])} />
          </label>
        )
      ) : (
        <div className="space-y-4">
          <p className="text-graphite text-[14px]">
            {tr('For footage on a drive you give to your manager yourself. They confirm once they have it.')}
          </p>
          <div>
            <span className="label">{tr('It’s on')}</span>
            <div className="flex flex-wrap gap-1.5">
              {MEDIA.map(([k, l]) => (
                <button
                  key={k}
                  type="button"
                  aria-pressed={drive.media === k}
                  onClick={() => setDrive(d => ({ ...d, media: k }))}
                  className={`btn btn-sm ${drive.media === k ? 'btn-primary' : 'btn-quiet'}`}
                >
                  {l}
                </button>
              ))}
            </div>
          </div>
          <div className="grid sm:grid-cols-2 gap-3">
            <div>
              <label className="label" htmlFor="to">
                {tr('Given to')}
              </label>
              <select
                id="to"
                className="field"
                value={drive.to}
                onChange={e => setDrive(d => ({ ...d, to: e.target.value }))}
              >
                {receivers.map(r => (
                  <option key={r.id} value={r.id}>
                    {r.name}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="label" htmlFor="at">
                {tr('When')}
              </label>
              <input
                id="at"
                type="datetime-local"
                max={localNow()}
                className="field"
                value={drive.at}
                onChange={e => setDrive(d => ({ ...d, at: e.target.value }))}
              />
            </div>
          </div>
        </div>
      )}
      {!busy && phase !== 'failed' && (
        <>
          <label className="label mt-5" htmlFor="note">
            {mode === 'drive' ? tr('What’s on it?') : tr('Note for your manager')}{' '}
            <span className="font-normal text-mist">{tr('(optional)')}</span>
          </label>
          <textarea
            id="note"
            rows={2}
            className="field"
            value={note}
            onChange={e => setNote(e.target.value)}
            placeholder={
              mode === 'drive' ? tr('e.g. 2 cameras, about 180 GB, folder “Day 1”') : tr('What should they look at?')
            }
          />
        </>
      )}
    </Dialog>
  );
}
