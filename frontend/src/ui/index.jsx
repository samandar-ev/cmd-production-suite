import { useEffect, useRef, useState, useCallback } from 'react';
import { ConfirmCtx, ToastCtx } from '../lib/hooks';
import { X } from 'lucide-react';
import { initials, left, when } from '../lib/format';
import { STAGES } from '../lib/stages';
import { tr } from '../lib/i18n';

export const PageHeader = ({ title, sub, actions, children }) => (
  <header className="flex flex-wrap items-end justify-between gap-x-6 gap-y-3 mb-6 lg:mb-8">
    <div className="min-w-0">
      <h1 className="display text-[26px] sm:text-[31px] leading-[1.15] font-semibold">{title}</h1>
      {sub && <p className="text-graphite mt-1.5 max-w-[60ch]">{sub}</p>}
    </div>
    {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
    {children}
  </header>
);

const TONES = ['#2F9DC2', '#C99413', '#A548BA', '#3C67D6', '#2C9466', '#5D6472'];
export const Avatar = ({ name, size = 28, src }) => {
  const tone = TONES[[...(name || '')].reduce((a, c) => a + c.charCodeAt(0), 0) % TONES.length];
  return src ? (
    <img src={src} alt="" className="rounded-full object-cover shrink-0" style={{ width: size, height: size }} />
  ) : (
    <span
      aria-hidden
      className="rounded-full shrink-0 inline-flex items-center justify-center font-semibold text-paper"
      style={{ width: size, height: size, background: tone, fontSize: size * 0.38 }}
    >
      {initials(name)}
    </span>
  );
};

export const Stage = ({ stage, text }) => {
  const s = STAGES.find(x => x.key === stage) || STAGES[0];
  return (
    <span className="inline-flex items-center gap-1.5 text-[13px] font-medium text-graphite whitespace-nowrap">
      <span className="w-2.5 h-2.5 rounded-[3px]" style={{ background: s.color }} />
      {text || s.label}
    </span>
  );
};

export const Due = ({ date, done, className = '' }) => {
  if (!date) return <span className={`text-[13px] text-mist ${className}`}>{tr('No deadline')}</span>;
  const l = left(date);
  const tone = done
    ? 'text-mist'
    : l.late
      ? 'text-tally font-semibold'
      : l.soon
        ? 'text-ink font-semibold'
        : 'text-graphite';
  return (
    <span className={`num text-[13px] ${tone} ${className}`} title={new Date(date).toLocaleString()}>
      <span className="whitespace-nowrap">{when(date)}</span>
      {!done && (
        <>
          {' '}
          <span className="text-mist font-normal whitespace-nowrap">· {l.text}</span>
        </>
      )}
    </span>
  );
};

export const Empty = ({ title, children, action }) => (
  <div className="py-12 px-6 text-center">
    <p className="font-semibold">{title}</p>
    {children && <p className="text-graphite mt-1 max-w-[46ch] mx-auto">{children}</p>}
    {action && <div className="mt-4">{action}</div>}
  </div>
);

export const Spinner = ({ label = tr('Loading') }) => (
  <div role="status" aria-label={label} className="flex items-center gap-2 text-graphite py-10 justify-center">
    <span className="w-4 h-4 rounded-full border-2 border-hairline border-t-ink animate-spin" />
    <span className="text-[14px]">{label}…</span>
  </div>
);

export const Dialog = ({ title, sub, onClose, children, footer, wide = false }) => {
  const ref = useRef(null);
  useEffect(() => {
    const onKey = e => e.key === 'Escape' && onClose();
    document.addEventListener('keydown', onKey);
    const prev = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    ref.current?.querySelector('input, select, textarea, button:not([data-close])')?.focus();
    return () => {
      document.removeEventListener('keydown', onKey);
      document.body.style.overflow = prev;
    };
  }, [onClose]);
  return (
    <div
      className="fixed inset-0 z-50 flex items-end sm:items-center justify-center sm:p-6 bg-ink/35"
      onMouseDown={onClose}
    >
      <div
        ref={ref}
        role="dialog"
        aria-modal="true"
        aria-label={title}
        onMouseDown={e => e.stopPropagation()}
        className={`bg-paper w-full ${wide ? 'sm:max-w-2xl' : 'sm:max-w-lg'} rounded-t-[20px] sm:rounded-[var(--radius-panel)] shadow-[0_24px_60px_-20px_rgba(26,31,43,.45)] max-h-[92dvh] flex flex-col sheet-in`}
      >
        <div className="flex items-start justify-between gap-4 px-6 pt-5 pb-4">
          <div className="min-w-0">
            <h2 className="text-[19px] font-semibold leading-snug">{title}</h2>
            {sub && <p className="text-[14px] text-graphite mt-0.5">{sub}</p>}
          </div>
          <button data-close onClick={onClose} className="btn-icon -mr-2 -mt-1" aria-label={tr('Close')}>
            <X />
          </button>
        </div>
        <div className="px-6 pb-5 overflow-y-auto">{children}</div>
        {footer && <div className="px-6 py-4 border-t border-hairline flex flex-wrap justify-end gap-2">{footer}</div>}
      </div>
    </div>
  );
};

export const ConfirmHost = ({ children }) => {
  const [ask, setAsk] = useState(null);
  const confirm = useCallback(opts => new Promise(resolve => setAsk({ ...opts, resolve })), []);
  const answer = yes => {
    ask.resolve(yes);
    setAsk(null);
  };
  return (
    <ConfirmCtx.Provider value={confirm}>
      {children}
      {ask && (
        <Dialog
          title={ask.title}
          onClose={() => answer(false)}
          footer={
            <>
              <button onClick={() => answer(false)} className="btn btn-ghost">
                {ask.cancel || tr('Cancel')}
              </button>
              <button onClick={() => answer(true)} className={`btn ${ask.danger ? 'btn-danger' : 'btn-primary'}`}>
                {ask.action || tr('Confirm')}
              </button>
            </>
          }
        >
          {ask.body && <p className="text-graphite">{ask.body}</p>}
        </Dialog>
      )}
    </ConfirmCtx.Provider>
  );
};

export const ToastHost = ({ children }) => {
  const [items, setItems] = useState([]);
  const push = useCallback((text, tone = 'ok') => {
    const id = Math.random();
    setItems(xs => [...xs, { id, text, tone }]);
    setTimeout(() => setItems(xs => xs.filter(x => x.id !== id)), 3500);
  }, []);
  return (
    <ToastCtx.Provider value={push}>
      {children}
      <div
        aria-live="polite"
        className="fixed z-[60] left-4 right-4 sm:right-auto bottom-[calc(76px+env(safe-area-inset-bottom))] lg:bottom-6 lg:left-[252px] flex flex-col gap-2"
      >
        {items.map(t => (
          <div
            key={t.id}
            className="sheet-in flex items-center gap-2.5 rounded-[10px] bg-ink text-paper px-4 py-3 text-[14px] shadow-lg max-w-md"
          >
            <span className={`w-2 h-2 rounded-full ${t.tone === 'error' ? 'bg-tally' : 'bg-publish'}`} />
            {t.text}
          </div>
        ))}
      </div>
    </ToastCtx.Provider>
  );
};
