import { useEffect, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { Send, KeyRound, Bot, Copy, LogOut, Camera } from 'lucide-react';
import api, { errorText } from '../lib/api';
import { useAuth, nameOf, ROLE_TEXT, isManager } from '../lib/auth';
import { ago } from '../lib/format';
import { Avatar, PageHeader, Spinner } from '../ui';
import { useToast } from '../lib/hooks';
import { setLanguage, tr } from '../lib/i18n';

const SECTIONS = [
  ['profile', tr('Profile')],
  ['security', tr('Sign-in & security')],
  ['notifications', tr('Telegram')],
  ['language', tr('Language')],
];

export default function Settings() {
  const [params, setParams] = useSearchParams();
  const { user, setUser, signOut } = useAuth();
  const section = SECTIONS.some(([k]) => k === params.get('s')) ? params.get('s') : 'profile';
  return (
    <>
      <PageHeader
        title={tr('Settings')}
        sub={`${nameOf(user)}, ${ROLE_TEXT[user.role]}`}
        actions={
          <button
            onClick={() => {
              signOut();
              location.assign('/sign-in');
            }}
            className="btn btn-quiet"
          >
            <LogOut /> {tr('Sign out')}
          </button>
        }
      />
      <div className="grid md:grid-cols-[220px_1fr] gap-6 items-start max-w-5xl">
        <nav className="flex md:flex-col gap-1 scroll-x" aria-label={tr('Settings')}>
          {SECTIONS.map(([k, l]) => (
            <button
              key={k}
              onClick={() => setParams(k === 'profile' ? {} : { s: k })}
              aria-current={section === k ? 'page' : undefined}
              className={`relative text-left shrink-0 h-10 px-4 rounded-[10px] text-[14px] ${section === k ? 'bg-paper font-semibold shadow-[0_1px_2px_rgba(26,31,43,.06)]' : 'text-graphite hover:text-ink'}`}
            >
              {section === k && (
                <span className="absolute left-0 top-2 bottom-2 w-[3px] rounded-full bg-tally hidden md:block" />
              )}
              {l}
            </button>
          ))}
        </nav>
        <div className="min-w-0 space-y-6">
          {section === 'profile' && <Profile user={user} setUser={setUser} />}
          {section === 'security' && <Security user={user} setUser={setUser} />}
          {section === 'notifications' && <Telegram user={user} setUser={setUser} />}
          {section === 'language' && <Language user={user} setUser={setUser} />}
        </div>
      </div>
    </>
  );
}

const Panel = ({ title, sub, children, footer }) => (
  <section className="panel">
    <div className="p-5 sm:p-6">
      <h2 className="text-[17px] font-semibold">{title}</h2>
      {sub && <p className="text-[14px] text-graphite mt-1 max-w-[60ch]">{sub}</p>}
      <div className="mt-5">{children}</div>
    </div>
    {footer && (
      <div className="px-5 sm:px-6 py-4 border-t border-hairline flex flex-wrap justify-end gap-2">{footer}</div>
    )}
  </section>
);

function Profile({ user, setUser }) {
  const toast = useToast();
  const [form, setForm] = useState({
    first_name: user.first_name,
    last_name: user.last_name,
    email: user.email || '',
    phone: user.phone || '',
  });
  const dirty = Object.entries(form).some(([k, v]) => v !== (user[k] || ''));
  const save = async () => {
    try {
      const { data } = await api.patch('users/me/', form);
      setUser(data);
      toast(tr('Profile saved'));
    } catch (err) {
      toast(errorText(err), 'error');
    }
  };
  const photo = f => {
    if (!f) return;
    if (f.size > 1.5e6) {
      toast(tr('Choose a photo under 1.5 MB'), 'error');
      return;
    }
    const r = new FileReader();
    r.onload = async () => {
      const { data } = await api.patch('users/me/', { avatar_url: r.result });
      setUser(data);
      toast(tr('Photo updated'));
    };
    r.readAsDataURL(f);
  };
  const set = k => e => setForm(f => ({ ...f, [k]: e.target.value }));
  return (
    <Panel
      title={tr('Profile')}
      sub={tr('How your colleagues see you.')}
      footer={
        <button onClick={save} disabled={!dirty} className="btn btn-primary">
          {tr('Save changes')}
        </button>
      }
    >
      <div className="flex items-center gap-4 mb-6">
        <Avatar name={nameOf(user)} src={user.avatar_url} size={64} />
        <label className="btn btn-quiet cursor-pointer">
          <Camera /> {tr('Change photo')}
          <input type="file" accept="image/*" className="sr-only" onChange={e => photo(e.target.files[0])} />
        </label>
      </div>
      <div className="grid sm:grid-cols-2 gap-4">
        <div>
          <label className="label" htmlFor="s-f">
            {tr('First name')}
          </label>
          <input id="s-f" className="field" value={form.first_name} onChange={set('first_name')} />
        </div>
        <div>
          <label className="label" htmlFor="s-l">
            {tr('Last name')}
          </label>
          <input id="s-l" className="field" value={form.last_name} onChange={set('last_name')} />
        </div>
        <div>
          <label className="label" htmlFor="s-e">
            {tr('Email')}
          </label>
          <input id="s-e" type="email" className="field" value={form.email} onChange={set('email')} />
        </div>
        <div>
          <label className="label" htmlFor="s-p">
            {tr('Phone')}
          </label>
          <input id="s-p" type="tel" className="field" value={form.phone} onChange={set('phone')} />
        </div>
      </div>
      <p className="text-[13px] text-mist mt-4">
        {tr('Your username is @')}
        {user.username}
        {tr('. Ask the owner if it needs to change.')}
      </p>
    </Panel>
  );
}

function Security({ user, setUser }) {
  const toast = useToast();
  const [pw, setPw] = useState({ a: '', b: '' });
  const [off, setOff] = useState('');
  const [apps, setApps] = useState(null);
  const loadApps = () =>
    api
      .get('ai/connections/')
      .then(r => setApps(r.data))
      .catch(() => setApps([]));
  const ai = isManager(user);
  useEffect(() => {
    if (ai) loadApps();
  }, [ai]);
  const changePw = async () => {
    try {
      const { data } = await api.patch('users/me/', { password: pw.a });
      if (data.tokens) {
        localStorage.setItem('access_token', data.tokens.access);
        localStorage.setItem('refresh_token', data.tokens.refresh);
      }
      setPw({ a: '', b: '' });
      toast(tr('Password changed — other devices were signed out'));
    } catch (err) {
      toast(errorText(err), 'error');
    }
  };
  const twoStep = async enabled => {
    try {
      const { data } = await api.post('auth/two-step/', enabled ? { enabled } : { enabled, password: off });
      if (data.tokens) {
        localStorage.setItem('access_token', data.tokens.access);
        localStorage.setItem('refresh_token', data.tokens.refresh);
      }
      setUser({ ...user, two_factor_enabled: enabled });
      setOff('');
      toast(enabled ? tr('Two-step sign-in is on — other devices were signed out') : tr('Two-step sign-in is off'));
    } catch (err) {
      toast(errorText(err), 'error');
    }
  };
  const url = `${location.origin}/mcp/`;
  return (
    <>
      <Panel
        title={tr('Password')}
        sub={tr('At least 8 characters. You stay signed in here; other devices are signed out.')}
        footer={
          <button onClick={changePw} disabled={pw.a.length < 8 || pw.a !== pw.b} className="btn btn-primary">
            {tr('Change password')}
          </button>
        }
      >
        <div className="grid sm:grid-cols-2 gap-4">
          <div>
            <label className="label" htmlFor="pw1">
              {tr('New password')}
            </label>
            <input
              id="pw1"
              type="password"
              autoComplete="new-password"
              className="field"
              value={pw.a}
              onChange={e => setPw(p => ({ ...p, a: e.target.value }))}
            />
          </div>
          <div>
            <label className="label" htmlFor="pw2">
              {tr('Repeat it')}
            </label>
            <input
              id="pw2"
              type="password"
              autoComplete="new-password"
              className="field"
              value={pw.b}
              onChange={e => setPw(p => ({ ...p, b: e.target.value }))}
            />
            {pw.b && pw.a !== pw.b && <p className="text-[13px] text-tally mt-1">{tr('The two don’t match yet.')}</p>}
          </div>
        </div>
      </Panel>
      <Panel
        title={tr('Two-step sign-in')}
        sub={tr(
          'Optional. After your password, you also type a code sent to your Telegram — so a leaked password alone can’t get anyone in.',
        )}
      >
        {!user.telegram_chat_id ? (
          <p className="text-[14px]">
            {tr('Connect Telegram first.')}{' '}
            <Link to="/settings?s=notifications" className="font-semibold underline underline-offset-2">
              {tr('Go to Telegram')}
            </Link>
          </p>
        ) : user.two_factor_enabled ? (
          <div className="flex flex-wrap items-end gap-3">
            <p className="w-full font-semibold text-publish">{tr('On')}</p>
            <div className="flex-1 min-w-[200px]">
              <label className="label" htmlFor="off">
                {tr('Your password, to turn it off')}
              </label>
              <input id="off" type="password" className="field" value={off} onChange={e => setOff(e.target.value)} />
            </div>
            <button onClick={() => twoStep(false)} disabled={!off} className="btn btn-quiet">
              {tr('Turn off')}
            </button>
          </div>
        ) : (
          <button onClick={() => twoStep(true)} className="btn btn-primary">
            <KeyRound /> {tr('Turn on')}
          </button>
        )}
      </Panel>
      {ai && (
        <Panel
          title={tr('Claude and other AI apps')}
          sub={tr(
            'Let Claude work in CMD as you. In Claude: Settings → Connectors → Add custom connector, and paste this address. It asks you before touching money or deleting anything.',
          )}
        >
          <div className="flex gap-2">
            <input
              readOnly
              value={url}
              className="field font-medium"
              onFocus={e => e.target.select()}
              aria-label={tr('Connector address')}
            />
            <button
              onClick={() => navigator.clipboard?.writeText(url).then(() => toast(tr('Address copied')))}
              className="btn btn-quiet shrink-0"
            >
              <Copy /> {tr('Copy')}
            </button>
          </div>
          <h3 className="font-semibold mt-6 mb-2">{tr('Connected')}</h3>
          {apps === null ? (
            <Spinner />
          ) : apps.length === 0 ? (
            <p className="text-[14px] text-graphite">{tr('Nothing connected.')}</p>
          ) : (
            <ul className="divide-y divide-hairline">
              {apps.map(a => (
                <li key={a.id} className="flex items-center gap-3 py-3">
                  <Bot size={18} className="text-graphite" />
                  <span className="flex-1 min-w-0">
                    <span className="block font-medium">{a.app}</span>
                    <span className="block text-[13px] text-graphite">
                      {tr('Connected')} {ago(a.created_at)}
                      {a.last_used_at ? `, ${tr('last used {when}', { when: ago(a.last_used_at) })}` : ''}
                    </span>
                  </span>
                  <button
                    onClick={() =>
                      api.post(`ai/connections/${a.id}/revoke/`).then(() => {
                        toast(tr('Disconnected'));
                        loadApps();
                      })
                    }
                    className="btn btn-ghost btn-sm text-tally"
                  >
                    {tr('Disconnect')}
                  </button>
                </li>
              ))}
            </ul>
          )}
          <Link to="/approvals" className="btn btn-quiet btn-sm mt-4">
            {tr('See Claude’s requests')}
          </Link>
        </Panel>
      )}
    </>
  );
}

function Telegram({ user, setUser }) {
  const toast = useToast();
  const [info, setInfo] = useState(null);
  const [link, setLink] = useState('');
  useEffect(() => {
    api
      .get('telegram/')
      .then(r => setInfo(r.data))
      .catch(() => setInfo({ enabled: false }));
  }, []);
  useEffect(() => {
    if (info?.enabled && !user.telegram_chat_id)
      api
        .post('telegram/connect/')
        .then(r => setLink(r.data.url))
        .catch(() => {});
  }, [info, user.telegram_chat_id]);
  useEffect(() => {
    const back = () =>
      document.visibilityState === 'visible' &&
      api
        .get('users/me/')
        .then(r => setUser(r.data))
        .catch(() => {});
    document.addEventListener('visibilitychange', back);
    return () => document.removeEventListener('visibilitychange', back);
  }, [setUser]);
  const patch = async (body, msg) => {
    try {
      const { data } = await api.patch('users/me/', body);
      setUser(data);
      toast(msg);
    } catch (err) {
      toast(errorText(err), 'error');
    }
  };
  if (!info) return <Spinner />;
  if (!info.enabled) return <Panel title={tr('Telegram')}>{tr('Telegram isn’t set up on this server yet.')}</Panel>;
  return (
    <Panel
      title={tr('Telegram')}
      sub={tr(
        'Orders, deadlines, reviews and messages arrive in Telegram the moment they happen, each with a button that opens it here.',
      )}
    >
      {user.telegram_chat_id ? (
        <>
          <p className="font-semibold text-publish">{tr('Connected')}</p>
          <label className="flex items-center gap-3 mt-4 cursor-pointer">
            <input
              type="checkbox"
              className="w-5 h-5 accent-ink"
              checked={user.telegram_enabled}
              onChange={e =>
                patch(
                  { telegram_enabled: e.target.checked },
                  e.target.checked ? tr('Notifications on') : tr('Notifications paused'),
                )
              }
            />
            <span>{tr('Send me notifications')}</span>
          </label>
          <div className="flex flex-wrap gap-2 mt-5">
            <button
              onClick={() =>
                api
                  .post('telegram/test/')
                  .then(() => toast(tr('Test sent — check Telegram')))
                  .catch(err => toast(errorText(err), 'error'))
              }
              className="btn btn-quiet"
            >
              <Send /> {tr('Send a test')}
            </button>
            <button
              onClick={() => patch({ telegram_chat_id: '' }, tr('Telegram disconnected'))}
              disabled={user.two_factor_enabled}
              className="btn btn-ghost"
              title={user.two_factor_enabled ? tr('Turn off two-step sign-in first') : undefined}
            >
              {tr('Disconnect')}
            </button>
          </div>
        </>
      ) : (
        <>
          <a
            href={link || undefined}
            target="_blank"
            rel="noreferrer"
            className={`btn btn-primary ${link ? '' : 'pointer-events-none opacity-50'}`}
          >
            <Send /> {tr('Connect Telegram')}
          </a>
          <p className="text-[14px] text-graphite mt-3">
            {tr('Opens @')}
            {info.bot_username} {tr('— press Start there, then come back here.')}
          </p>
        </>
      )}
    </Panel>
  );
}

function Language({ user, setUser }) {
  const choose = async code => {
    const { data } = await api.patch('users/me/', { language: code });
    setUser(data);
    setLanguage(code);
  };
  return (
    <Panel title={tr('Language')} sub={tr('For the app, notifications, Telegram messages and emails.')}>
      <div className="grid sm:grid-cols-2 gap-3">
        {[
          ['en', 'English'],
          ['ru', 'Русский'],
        ].map(([k, l]) => (
          <button
            key={k}
            onClick={() => choose(k)}
            aria-pressed={user.language === k}
            className={`text-left rounded-[12px] border p-4 font-semibold ${user.language === k ? 'border-ink' : 'border-hairline hover:border-mist'}`}
          >
            {l}
          </button>
        ))}
      </div>
    </Panel>
  );
}
