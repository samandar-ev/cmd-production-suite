import { useCallback, useEffect, useState } from 'react';
import { NavLink, Outlet, useLocation, useNavigate } from 'react-router-dom';
import {
  CircleDot,
  Clapperboard,
  PlayCircle,
  FolderClosed,
  Building2,
  CalendarDays,
  MessagesSquare,
  NotebookPen,
  Landmark,
  Users,
  FileSignature,
  ChartNoAxesColumn,
  Settings,
  Bell,
  LayoutGrid,
  LogOut,
  Search,
} from 'lucide-react';
import api, { list } from '../lib/api';
import { useAuth, isManager, nameOf, ROLE_TEXT } from '../lib/auth';
import { Avatar, Dialog } from '../ui';
import { ago } from '../lib/format';
import CommandBar from './CommandBar';
import { pathFor, usePulse } from '../lib/hooks';
import { tr, trn } from '../lib/i18n';

const navFor = (user, counts) => {
  const owner = user?.role === 'OWNER';
  if (!isManager(user)) {
    return {
      main: [
        { to: '/', label: tr('My work'), icon: CircleDot, end: true },
        { to: '/projects', label: tr('Projects'), icon: FolderClosed },
        { to: '/calendar', label: tr('Calendar'), icon: CalendarDays },
        { to: '/messages', label: tr('Messages'), icon: MessagesSquare, badge: counts.unread },
        { to: '/workspace', label: tr('Notes & to-dos'), short: tr('Notes'), icon: NotebookPen },
      ],
      mobile: ['/', '/calendar', '/messages', '/projects'],
    };
  }
  return {
    main: [
      { to: '/', label: tr('Today'), icon: CircleDot, end: true },
      { to: '/production', label: tr('Production'), icon: Clapperboard },
      { to: '/review', label: tr('Review'), icon: PlayCircle, badge: counts.review },
      { to: '/projects', label: tr('Projects'), icon: FolderClosed },
      { to: '/clients', label: tr('Clients'), icon: Building2 },
      { to: '/calendar', label: tr('Calendar'), icon: CalendarDays },
      { to: '/messages', label: tr('Messages'), icon: MessagesSquare, badge: counts.unread },
      { to: '/workspace', label: tr('Notes & to-dos'), short: tr('Notes'), icon: NotebookPen },
    ],
    business: owner
      ? [
          { to: '/money', label: tr('Money'), icon: Landmark },
          { to: '/reports', label: tr('Reports'), icon: ChartNoAxesColumn },
          { to: '/team', label: tr('Team'), icon: Users },
          { to: '/contracts', label: tr('Contracts'), icon: FileSignature },
        ]
      : [],
    mobile: ['/', '/production', '/review', '/messages'],
  };
};

const RailLink = ({ item, onClick }) => (
  <NavLink
    to={item.to}
    end={item.end}
    onClick={onClick}
    className={({ isActive }) =>
      `relative flex items-center gap-3 h-10 pl-4 pr-3 rounded-[10px] text-[14px] transition-colors ${
        isActive
          ? 'bg-paper text-ink font-semibold shadow-[0_1px_2px_rgba(26,31,43,.06)]'
          : 'text-graphite hover:text-ink hover:bg-paper/60'
      }`
    }
  >
    {({ isActive }) => (
      <>
        {isActive && <span aria-hidden className="absolute left-0 top-2 bottom-2 w-[3px] rounded-full bg-tally" />}
        <item.icon size={18} strokeWidth={isActive ? 2.2 : 1.8} />
        <span className="flex-1 truncate">{item.label}</span>
        {item.badge > 0 && (
          <span className="num min-w-5 h-5 px-1.5 rounded-full bg-ink text-paper text-[11px] font-semibold flex items-center justify-center">
            {item.badge}
          </span>
        )}
      </>
    )}
  </NavLink>
);

export default function Shell() {
  const { user, signOut } = useAuth();
  const { pathname } = useLocation();
  const [counts, setCounts] = useState({ unread: 0, review: 0, notes: 0 });
  const [notes, setNotes] = useState(null);
  const [notesOpen, setNotesOpen] = useState(false);
  const [morePath, setMorePath] = useState(null);
  const more = morePath === pathname;
  const setMore = open => setMorePath(open ? pathname : null);
  const [cmd, setCmd] = useState(false);

  const pulse = useCallback(() => {
    Promise.all([
      api
        .get('chats/unread/')
        .then(r => r.data.unread)
        .catch(() => 0),
      api
        .get('notifications/')
        .then(list)
        .catch(() => []),
      isManager(user)
        ? api
            .get('video-submissions/', { params: { status: 'pending' } })
            .then(r => list(r).length)
            .catch(() => 0)
        : 0,
    ]).then(([unread, ns, review]) => {
      setCounts({ unread, review, notes: ns.filter(n => !n.is_read).length });
      setNotes(ns);
    });
  }, [user]);
  usePulse(pulse, 30000);

  useEffect(() => {
    const onKey = e => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault();
        setCmd(o => !o);
      }
    };
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, []);
  useEffect(() => {
    window.scrollTo(0, 0);
  }, [pathname]);

  const nav = navFor(user, counts);
  const all = [...nav.main, ...(nav.business || [])];
  const mobile = nav.mobile.map(to => all.find(i => i.to === to));

  return (
    <div className="min-h-dvh lg:pl-[240px]">
      <aside
        className="hidden lg:flex fixed inset-y-0 left-0 w-[240px] flex-col px-3 py-5 border-r border-hairline"
        aria-label={tr('Main')}
      >
        <div className="flex items-center justify-between px-2 mb-6">
          <span className="display text-[19px] font-semibold flex items-center gap-1.5">
            {tr('CMD')}
            <span className="w-2 h-2 rounded-full bg-tally mb-3" aria-hidden />
          </span>
          <button
            onClick={() => setNotesOpen(true)}
            className="btn-icon relative"
            aria-label={tr('Notifications, {n} unread', { n: counts.notes })}
          >
            <Bell size={18} />
            {counts.notes > 0 && (
              <span className="absolute top-2 right-2 w-2 h-2 rounded-full bg-tally ring-2 ring-wall" />
            )}
          </button>
        </div>
        <button
          onClick={() => setCmd(true)}
          className="mx-1 mb-5 h-9 px-3 rounded-[9px] bg-paper/70 border border-hairline text-mist text-[13px] flex items-center gap-2 hover:border-mist"
        >
          <Search size={15} /> <span className="flex-1 text-left">{tr('Find anything')}</span>
          <kbd className="text-[11px] font-sans">⌘K</kbd>
        </button>
        <nav className="flex flex-col gap-0.5 overflow-y-auto">
          {nav.main.map(i => (
            <RailLink key={i.to} item={i} />
          ))}
          {nav.business?.length > 0 && (
            <>
              <p className="px-4 mt-5 mb-1.5 text-[12px] font-semibold text-mist">{tr('Business')}</p>
              {nav.business.map(i => (
                <RailLink key={i.to} item={i} />
              ))}
            </>
          )}
        </nav>
        <div className="mt-auto pt-4 border-t border-hairline flex items-center gap-2.5 px-2">
          <NavLink
            to="/settings"
            className="flex items-center gap-2.5 min-w-0 flex-1 rounded-[10px] p-1.5 -m-1.5 hover:bg-paper/60"
          >
            <Avatar name={nameOf(user)} src={user?.avatar_url} size={32} />
            <span className="min-w-0">
              <span className="block text-[14px] font-semibold truncate">{nameOf(user)}</span>
              <span className="block text-[12px] text-graphite">{ROLE_TEXT[user?.role]}</span>
            </span>
          </NavLink>
          <NavLink to="/settings" className="btn-icon" aria-label={tr('Settings')}>
            <Settings size={17} />
          </NavLink>
        </div>
      </aside>

      <header className="lg:hidden sticky top-0 z-30 flex items-center justify-between h-14 px-4 bg-wall/90 backdrop-blur border-b border-hairline">
        <span className="display text-[17px] font-semibold flex items-center gap-1">
          {tr('CMD')}
          <span className="w-1.5 h-1.5 rounded-full bg-tally mb-2.5" aria-hidden />
        </span>
        <div className="flex items-center gap-1">
          <button onClick={() => setCmd(true)} className="btn-icon" aria-label={tr('Find anything')}>
            <Search size={19} />
          </button>
          <button
            onClick={() => setNotesOpen(true)}
            className="btn-icon relative"
            aria-label={tr('Notifications, {n} unread', { n: counts.notes })}
          >
            <Bell size={19} />
            {counts.notes > 0 && <span className="absolute top-2 right-2 w-2 h-2 rounded-full bg-tally" />}
          </button>
          <NavLink to="/settings" aria-label={tr('Settings')} className="ml-1">
            <Avatar name={nameOf(user)} src={user?.avatar_url} size={30} />
          </NavLink>
        </div>
      </header>

      <main className="px-4 sm:px-6 lg:px-10 pt-5 lg:pt-9 pb-28 lg:pb-12 max-w-[1320px]">
        <Outlet context={{ refreshCounts: pulse }} />
      </main>

      <nav
        className="lg:hidden fixed bottom-0 inset-x-0 z-30 bg-paper/95 backdrop-blur border-t border-hairline pb-safe"
        aria-label={tr('Main')}
      >
        <div className="grid grid-cols-5 h-16">
          {mobile.map(i => (
            <NavLink
              key={i.to}
              to={i.to}
              end={i.end}
              className={({ isActive }) =>
                `relative flex flex-col items-center justify-center gap-0.5 text-[11px] font-medium ${isActive ? 'text-ink' : 'text-mist'}`
              }
            >
              {({ isActive }) => (
                <>
                  {isActive && <span aria-hidden className="absolute top-0 w-8 h-[3px] rounded-b-full bg-tally" />}
                  <span className="relative">
                    <i.icon size={21} strokeWidth={isActive ? 2.2 : 1.8} />
                    {i.badge > 0 && (
                      <span className="absolute -top-1 -right-2 num min-w-4 h-4 px-1 rounded-full bg-tally text-paper text-[10px] font-semibold flex items-center justify-center">
                        {i.badge}
                      </span>
                    )}
                  </span>
                  {i.short || i.label}
                </>
              )}
            </NavLink>
          ))}
          <button
            onClick={() => setMore(true)}
            className="flex flex-col items-center justify-center gap-0.5 text-[11px] font-medium text-mist"
          >
            <LayoutGrid size={21} strokeWidth={1.8} />
            {tr('More')}
          </button>
        </div>
      </nav>

      {more && (
        <Dialog title={tr('All places')} onClose={() => setMore(false)}>
          <div className="grid grid-cols-3 gap-2 pb-2">
            {[...all, { to: '/settings', label: tr('Settings'), icon: Settings }].map(i => (
              <NavLink
                key={i.to}
                to={i.to}
                end={i.end}
                className={({ isActive }) =>
                  `flex flex-col items-center gap-1.5 rounded-[12px] p-3 text-center text-[13px] font-medium border ${isActive ? 'border-ink' : 'border-hairline'}`
                }
              >
                <i.icon size={20} />
                {i.label}
              </NavLink>
            ))}
          </div>
          <button
            onClick={() => {
              signOut();
              location.assign('/sign-in');
            }}
            className="btn btn-ghost w-full mt-2"
          >
            <LogOut /> {tr('Sign out')}
          </button>
        </Dialog>
      )}
      {notesOpen && (
        <Notifications items={notes || []} user={user} onClose={() => setNotesOpen(false)} onChange={pulse} />
      )}
      {cmd && (
        <CommandBar
          onClose={() => setCmd(false)}
          nav={[...all, { to: '/settings', label: tr('Settings'), icon: Settings }]}
        />
      )}
    </div>
  );
}

function Notifications({ items, user, onClose, onChange }) {
  const navigate = useNavigate();
  const open = async n => {
    if (!n.is_read) await api.patch(`notifications/${n.id}/`, { is_read: true }).catch(() => {});
    onChange();
    const to = pathFor(n.related_entity_type, n.related_entity_id, user);
    if (to) {
      onClose();
      navigate(to);
    }
  };
  const readAll = async () => {
    await api.post('notifications/mark_all_read/').catch(() => {});
    onChange();
  };
  const unread = items.filter(n => !n.is_read).length;
  return (
    <Dialog
      title={tr('Notifications')}
      sub={unread ? trn(unread, '{n} unread', '{n} unread') : tr('You’re all caught up')}
      onClose={onClose}
      footer={
        unread > 0 && (
          <button onClick={readAll} className="btn btn-quiet btn-sm">
            {tr('Mark all as read')}
          </button>
        )
      }
    >
      {items.length === 0 ? (
        <p className="text-graphite py-6 text-center">{tr('Nothing here yet.')}</p>
      ) : (
        <ul className="-mx-2">
          {items.slice(0, 40).map(n => (
            <li key={n.id}>
              <button
                onClick={() => open(n)}
                className="w-full text-left flex gap-3 rounded-[10px] px-2 py-3 hover:bg-haze"
              >
                <span className={`mt-2 w-2 h-2 rounded-full shrink-0 ${n.is_read ? 'bg-transparent' : 'bg-tally'}`} />
                <span className="min-w-0">
                  <span className={`block text-[14px] ${n.is_read ? 'text-graphite' : 'font-semibold'}`}>
                    {n.title}
                  </span>
                  <span className="block text-[13px] text-graphite line-clamp-2">{n.message}</span>
                  <span className="block text-[12px] text-mist mt-0.5">{ago(n.created_at)}</span>
                </span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </Dialog>
  );
}
