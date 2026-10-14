import { useEffect, useMemo, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Search, FolderClosed, Building2, Film, CircleDot, CornerDownLeft } from 'lucide-react';
import api from '../lib/api';
import { useAuth, isManager } from '../lib/auth';
import { tr } from '../lib/i18n';

export default function CommandBar({ onClose, nav }) {
  const navigate = useNavigate();
  const user = useAuth(s => s.user);
  const [q, setQ] = useState('');
  const [hits, setHits] = useState(null);
  const [active, setActive] = useState(0);
  const input = useRef(null);

  useEffect(() => {
    input.current?.focus();
  }, []);
  useEffect(() => {
    if (!isManager(user) || q.trim().length < 2) return undefined;
    const t = setTimeout(
      () =>
        api
          .get('dashboards/search/', { params: { q: q.trim() } })
          .then(r => setHits(r.data))
          .catch(() => {}),
      200,
    );
    return () => clearTimeout(t);
  }, [q, user]);

  const rows = useMemo(() => {
    const s = q.trim().toLowerCase();
    const places = nav
      .filter(i => !s || i.label.toLowerCase().includes(s))
      .map(i => ({ key: i.to, icon: i.icon, title: i.label, sub: tr('Go to'), to: i.to }));
    if (!hits || s.length < 2) return places;
    const found = [
      ...(hits.projects || []).map(p => ({
        key: `p${p.id}`,
        icon: FolderClosed,
        title: p.name,
        sub: tr('Project'),
        to: `/projects/${p.id}`,
      })),
      ...(hits.clients || []).map(c => ({
        key: `c${c.id}`,
        icon: Building2,
        title: c.client_name,
        sub: tr('Client'),
        to: '/clients',
      })),
      ...(hits.content_items || []).map(c => ({
        key: `i${c.id}`,
        icon: Film,
        title: c.title,
        sub: tr('{platform} content', { platform: c.platform }),
        to: `/content/${c.id}`,
      })),
      ...(hits.tasks || []).map(t => ({
        key: `t${t.id}`,
        icon: CircleDot,
        title: t.title,
        sub: tr('Order'),
        to: `/orders/${t.id}`,
      })),
    ];
    return [...found, ...places];
  }, [q, hits, nav]);

  const go = row => {
    if (!row) return;
    onClose();
    navigate(row.to);
  };
  const onKey = e => {
    if (e.key === 'Escape') onClose();
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      setActive(a => Math.min(a + 1, rows.length - 1));
    }
    if (e.key === 'ArrowUp') {
      e.preventDefault();
      setActive(a => Math.max(a - 1, 0));
    }
    if (e.key === 'Enter') go(rows[active]);
  };

  return (
    <div className="fixed inset-0 z-50 bg-ink/35 flex items-start justify-center p-4 pt-[12vh]" onMouseDown={onClose}>
      <div
        className="w-full max-w-xl bg-paper rounded-[var(--radius-panel)] shadow-[0_24px_60px_-20px_rgba(26,31,43,.45)] overflow-hidden sheet-in"
        onMouseDown={e => e.stopPropagation()}
        role="dialog"
        aria-label={tr('Find anything')}
      >
        <div className="flex items-center gap-3 px-4 h-14 border-b border-hairline">
          <Search size={18} className="text-mist" />
          <input
            ref={input}
            value={q}
            onChange={e => {
              setQ(e.target.value);
              setActive(0);
            }}
            onKeyDown={onKey}
            placeholder={isManager(user) ? tr('Find a project, client, content or order…') : tr('Go to…')}
            className="flex-1 bg-transparent outline-none text-[16px] placeholder:text-mist"
            aria-label={tr('Search')}
          />
          <kbd className="text-[12px] text-mist">{tr('Esc')}</kbd>
        </div>
        <ul className="max-h-[50vh] overflow-y-auto p-2" role="listbox">
          {rows.length === 0 && (
            <li className="px-3 py-6 text-center text-graphite">
              {tr('No matches for “')}
              {q}”.
            </li>
          )}
          {rows.map((r, i) => (
            <li key={r.key} role="option" aria-selected={i === active}>
              <button
                onMouseEnter={() => setActive(i)}
                onClick={() => go(r)}
                className={`w-full flex items-center gap-3 px-3 h-12 rounded-[10px] text-left ${i === active ? 'bg-haze' : ''}`}
              >
                <r.icon size={17} className="text-graphite shrink-0" />
                <span className="flex-1 min-w-0 truncate font-medium">{r.title}</span>
                <span className="text-[12px] text-mist shrink-0">{r.sub}</span>
                {i === active && <CornerDownLeft size={14} className="text-mist" />}
              </button>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}
