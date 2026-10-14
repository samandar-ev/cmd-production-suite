import { useCallback, useEffect, useRef, useState } from 'react';
import { Paperclip, Send, X, FileText, Download } from 'lucide-react';
import api, { errorText } from '../lib/api';
import { useAuth } from '../lib/auth';
import { day, time } from '../lib/format';
import { usePulse } from '../lib/hooks';
import { tr } from '../lib/i18n';

const MAX_FILE = 100 * 1000 * 1000;

const putFile = (url, file, type, onProgress) =>
  new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open('PUT', url);
    xhr.setRequestHeader('Content-Type', type);
    xhr.upload.onprogress = e => e.lengthComputable && onProgress(e.loaded / e.total);
    xhr.onload = () =>
      xhr.status < 300 ? resolve() : reject(new Error(tr('Upload failed ({status})', { status: xhr.status })));
    xhr.onerror = () => reject(new Error(tr('Network problem while uploading. Try again.')));
    xhr.send(file);
  });

export default function Chat({ taskId, className = '' }) {
  const me = useAuth(s => s.user);
  const [messages, setMessages] = useState(null);
  const [text, setText] = useState('');
  const [file, setFile] = useState(null);
  const [error, setError] = useState('');
  const [sending, setSending] = useState(false);
  const end = useRef(null);
  const count = useRef(0);

  const load = useCallback(
    () =>
      api
        .get(`chats/${taskId}/messages/`)
        .then(r => setMessages(r.data))
        .catch(() => setMessages(m => m || [])),
    [taskId],
  );
  usePulse(load, 6000);
  useEffect(() => {
    if (messages && messages.length !== count.current) {
      count.current = messages.length;
      end.current?.scrollIntoView({ block: 'nearest' });
    }
  }, [messages]);

  const attach = async f => {
    if (!f) return;
    if (f.size > MAX_FILE) {
      setError(tr('Files in chat can be up to 100 MB. Use “Send work” for bigger deliveries.'));
      return;
    }
    setError('');
    setFile({ name: f.name, progress: 0 });
    try {
      const type = f.type || 'application/octet-stream';
      const { data } = await api.post(`chats/${taskId}/attachments/`, {
        filename: f.name,
        size: f.size,
        content_type: type,
      });
      await putFile(data.upload_url, f, data.content_type, p => setFile(x => ({ ...x, progress: p })));
      setFile({ name: f.name, id: data.id, progress: 1, ready: true });
    } catch (err) {
      setError(errorText(err, err.message));
      setFile(null);
    }
  };

  const send = async e => {
    e.preventDefault();
    if ((!text.trim() && !file?.ready) || sending) return;
    setSending(true);
    setError('');
    try {
      await api.post(`chats/${taskId}/messages/`, { body: text.trim(), attachment: file?.id || null });
      setText('');
      setFile(null);
      load();
    } catch (err) {
      setError(errorText(err));
    } finally {
      setSending(false);
    }
  };

  let lastDay = '';
  return (
    <div className={`flex flex-col min-h-0 ${className}`}>
      <div className="flex-1 overflow-y-auto py-2 space-y-1.5">
        {messages === null && <p className="text-graphite text-center py-8">{tr('Loading messages…')}</p>}
        {messages?.length === 0 && (
          <p className="text-graphite text-center py-8 px-6">
            {tr(
              'No messages yet. Ask a question or share an update — the other person gets it in the app and on Telegram.',
            )}
          </p>
        )}
        {messages?.map(m => {
          const mine = m.sender === me?.id;
          const d = day(m.created_at);
          const showDay = d !== lastDay;
          lastDay = d;
          return (
            <div key={m.id}>
              {showDay && <p className="text-center text-[12px] text-mist my-3">{d}</p>}
              <div className={`flex ${mine ? 'justify-end' : 'justify-start'}`}>
                <div className={`max-w-[82%] sm:max-w-[70%] ${mine ? 'items-end' : 'items-start'} flex flex-col gap-1`}>
                  {!mine && <span className="text-[12px] text-graphite px-1">{m.sender_name}</span>}
                  {m.attachment && <Attachment a={m.attachment} mine={mine} />}
                  {m.body && (
                    <p
                      className={`px-3.5 py-2 rounded-[14px] whitespace-pre-line break-words ${mine ? 'bg-ink text-paper rounded-br-[4px]' : 'bg-haze rounded-bl-[4px]'}`}
                    >
                      {m.body}
                    </p>
                  )}
                  <span className="text-[11px] text-mist px-1 num">{time(m.created_at)}</span>
                </div>
              </div>
            </div>
          );
        })}
        <div ref={end} />
      </div>
      {error && (
        <p role="alert" className="text-tally text-[14px] px-1 pb-2">
          {error}
        </p>
      )}
      {file && (
        <div className="flex items-center gap-2 mb-2 rounded-[10px] bg-haze px-3 py-2 text-[14px]">
          <FileText size={16} className="text-graphite" />
          <span className="flex-1 truncate">{file.name}</span>
          <span className="text-mist num">{file.ready ? tr('Ready') : `${Math.round(file.progress * 100)}%`}</span>
          <button onClick={() => setFile(null)} aria-label={tr('Remove file')} className="text-graphite">
            <X size={16} />
          </button>
        </div>
      )}
      <form onSubmit={send} className="flex items-end gap-2">
        <label className="btn-icon cursor-pointer shrink-0" aria-label={tr('Attach a file')}>
          <Paperclip size={18} />
          <input
            type="file"
            className="sr-only"
            onChange={e => {
              attach(e.target.files[0]);
              e.target.value = '';
            }}
          />
        </label>
        <textarea
          value={text}
          onChange={e => setText(e.target.value)}
          rows={1}
          placeholder={tr('Write a message')}
          onKeyDown={e => {
            if (e.key === 'Enter' && !e.shiftKey) send(e);
          }}
          className="field min-h-10 max-h-32 py-2"
          aria-label={tr('Message')}
        />
        <button
          disabled={sending || (!text.trim() && !file?.ready)}
          className="btn btn-primary shrink-0 w-10 px-0"
          aria-label={tr('Send')}
        >
          <Send />
        </button>
      </form>
    </div>
  );
}

function Attachment({ a, mine }) {
  if (a.deleted || !a.download_url)
    return (
      <p className="text-[13px] text-mist px-1">
        {a.filename} {tr('is no longer available')}
      </p>
    );
  if (a.view_url && /^image\//.test(a.content_type || ''))
    return (
      <a href={a.view_url} target="_blank" rel="noreferrer">
        <img
          src={a.view_url}
          alt={a.filename}
          className="max-h-60 rounded-[12px] border border-hairline"
          loading="lazy"
        />
      </a>
    );
  return (
    <a
      href={a.download_url}
      className={`flex items-center gap-3 px-3.5 py-2.5 rounded-[12px] border ${mine ? 'border-ink/20' : 'border-hairline'} bg-paper hover:border-mist min-w-[200px]`}
    >
      <FileText size={18} className="text-graphite" />
      <span className="flex-1 truncate font-medium">{a.filename}</span>
      <Download size={16} className="text-graphite" />
    </a>
  );
}
