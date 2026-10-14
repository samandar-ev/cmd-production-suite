import { useState } from 'react';
import { Plus, Send } from 'lucide-react';
import api, { errorText, list } from '../lib/api';
import { useAuth, nameOf, ROLE_TEXT } from '../lib/auth';
import { day } from '../lib/format';
import { Avatar, Dialog, PageHeader, Spinner } from '../ui';
import { useLoad, useToast } from '../lib/hooks';
import { tr, trn } from '../lib/i18n';

const load = () => api.get('users/').then(list);
const ROLES = ['VIDEOGRAPHER', 'EDITOR', 'PROJECT_MANAGER', 'OWNER'];

export default function Team() {
  const me = useAuth(s => s.user);
  const { data, reload } = useLoad(load, []);
  const [open, setOpen] = useState(null);
  const [showInactive, setShowInactive] = useState(false);
  if (!data)
    return (
      <>
        <PageHeader title={tr('Team')} />
        <Spinner />
      </>
    );
  const people = data.filter(u => showInactive || u.is_active);
  const order = u => ROLES.indexOf(u.role);

  return (
    <>
      <PageHeader
        title={tr('Team')}
        sub={trn(data.filter(u => u.is_active).length, '{n} person can sign in', '{n} people can sign in')}
        actions={
          <button onClick={() => setOpen({})} className="btn btn-primary">
            <Plus /> {tr('Add someone')}
          </button>
        }
      />
      <section className="panel overflow-hidden">
        <ul className="divide-y divide-hairline">
          {people
            .sort((a, b) => order(a) - order(b) || nameOf(a).localeCompare(nameOf(b)))
            .map(u => (
              <li key={u.id}>
                <button
                  onClick={() => setOpen(u)}
                  className={`w-full text-left grid sm:grid-cols-[1fr_auto_auto] items-center gap-x-6 gap-y-1 px-5 py-4 hover:bg-haze ${u.is_active ? '' : 'opacity-55'}`}
                >
                  <span className="flex items-center gap-3 min-w-0">
                    <Avatar name={nameOf(u)} src={u.avatar_url} size={38} />
                    <span className="min-w-0">
                      <span className="block font-semibold truncate">
                        {nameOf(u)}
                        {u.id === me.id ? ' (you)' : ''}
                      </span>
                      <span className="block text-[13px] text-graphite truncate">
                        @{u.username}
                        {u.phone ? `, ${u.phone}` : ''}
                      </span>
                    </span>
                  </span>
                  <span className="text-[13px] text-graphite pl-[50px] sm:pl-0">
                    {ROLE_TEXT[u.role]}
                    {u.is_active ? '' : ', deactivated'}
                  </span>
                  <span
                    className={`text-[13px] pl-[50px] sm:pl-0 flex items-center gap-1.5 ${u.telegram_chat_id ? 'text-publish' : 'text-mist'}`}
                  >
                    <Send size={13} />
                    {u.telegram_chat_id ? tr('Telegram on') : tr('No Telegram')}
                  </span>
                </button>
              </li>
            ))}
        </ul>
      </section>
      {data.some(u => !u.is_active) && (
        <button onClick={() => setShowInactive(v => !v)} className="btn btn-ghost btn-sm mt-3">
          {showInactive ? tr('Hide deactivated people') : tr('Show deactivated people')}
        </button>
      )}
      {open && <PersonDialog person={open} isMe={open.id === me.id} onClose={() => setOpen(null)} onSaved={reload} />}
    </>
  );
}

function PersonDialog({ person, isMe, onClose, onSaved }) {
  const toast = useToast();
  const isNew = !person.id;
  const [form, setForm] = useState({
    first_name: person.first_name || '',
    last_name: person.last_name || '',
    username: person.username || '',
    password: '',
    role: person.role || 'VIDEOGRAPHER',
    phone: person.phone || '',
    email: person.email || '',
    telegram_chat_id: person.telegram_chat_id || '',
  });
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const set = k => e => setForm(f => ({ ...f, [k]: e.target.value }));
  const save = async e => {
    e.preventDefault();
    setBusy(true);
    setError('');
    const body = { ...form };
    if (!isNew) {
      delete body.username;
      if (!body.password) delete body.password;
    }
    try {
      isNew ? await api.post('users/', body) : await api.patch(`users/${person.id}/`, body);
      toast(isNew ? tr('{name} can now sign in', { name: form.first_name }) : tr('Saved'));
      onSaved();
      onClose();
    } catch (err) {
      setError(errorText(err));
    } finally {
      setBusy(false);
    }
  };
  const setActive = async active => {
    await api
      .patch(`users/${person.id}/`, { is_active: active })
      .then(() => {
        toast(active ? tr('Reactivated') : tr('Deactivated — they can no longer sign in'));
        onSaved();
        onClose();
      })
      .catch(err => setError(errorText(err)));
  };
  return (
    <Dialog
      title={isNew ? tr('Add someone') : nameOf(person)}
      sub={!isNew && tr('Joined {date}', { date: day(person.created_at) })}
      onClose={onClose}
      wide
      footer={
        <>
          {!isNew &&
            !isMe &&
            (person.is_active ? (
              <button onClick={() => setActive(false)} className="btn btn-ghost text-tally mr-auto">
                {tr('Deactivate')}
              </button>
            ) : (
              <button onClick={() => setActive(true)} className="btn btn-ghost mr-auto">
                {tr('Reactivate')}
              </button>
            ))}
          <button onClick={onClose} className="btn btn-ghost">
            {tr('Cancel')}
          </button>
          <button
            form="pd"
            disabled={busy || !form.first_name.trim() || (isNew && (!form.username.trim() || form.password.length < 8))}
            className="btn btn-primary"
          >
            {busy ? tr('Saving…') : isNew ? tr('Add') : tr('Save')}
          </button>
        </>
      }
    >
      <form id="pd" onSubmit={save} className="grid sm:grid-cols-2 gap-4" autoComplete="off">
        {error && (
          <p role="alert" className="text-tally sm:col-span-2">
            {error}
          </p>
        )}
        <div>
          <label className="label" htmlFor="pd-f">
            {tr('First name')}
          </label>
          <input id="pd-f" className="field" value={form.first_name} onChange={set('first_name')} required />
        </div>
        <div>
          <label className="label" htmlFor="pd-l">
            {tr('Last name')} <span className="font-normal text-mist">{tr('(optional)')}</span>
          </label>
          <input id="pd-l" className="field" value={form.last_name} onChange={set('last_name')} />
        </div>
        <div>
          <label className="label" htmlFor="pd-u">
            {tr('Username')}
          </label>
          <input
            id="pd-u"
            className="field"
            value={form.username}
            onChange={set('username')}
            disabled={!isNew}
            autoCapitalize="none"
            placeholder={tr('e.g. aziz')}
            required={isNew}
          />
          {isNew && <p className="text-[12px] text-mist mt-1">{tr('They sign in with this.')}</p>}
        </div>
        <div>
          <label className="label" htmlFor="pd-p">
            {isNew ? tr('Password') : tr('New password')}
          </label>
          <input
            id="pd-p"
            type="password"
            className="field"
            value={form.password}
            onChange={set('password')}
            autoComplete="new-password"
            placeholder={isNew ? tr('At least 8 characters') : tr('Leave empty to keep it')}
          />
          {!isNew && <p className="text-[12px] text-mist mt-1">{tr('Changing it signs them out everywhere.')}</p>}
        </div>
        <div>
          <label className="label" htmlFor="pd-r">
            {tr('Role')}
          </label>
          <select id="pd-r" className="field" value={form.role} onChange={set('role')} disabled={isMe}>
            {ROLES.map(r => (
              <option key={r} value={r}>
                {ROLE_TEXT[r]}
              </option>
            ))}
          </select>
        </div>
        <div>
          <label className="label" htmlFor="pd-ph">
            {tr('Phone')} <span className="font-normal text-mist">{tr('(optional)')}</span>
          </label>
          <input
            id="pd-ph"
            type="tel"
            className="field"
            value={form.phone}
            onChange={set('phone')}
            placeholder="+998 90 123 45 67"
          />
        </div>
        <div>
          <label className="label" htmlFor="pd-e">
            {tr('Email')} <span className="font-normal text-mist">{tr('(optional)')}</span>
          </label>
          <input id="pd-e" type="email" className="field" value={form.email} onChange={set('email')} />
        </div>
        <div>
          <label className="label" htmlFor="pd-t">
            {tr('Telegram chat ID')} <span className="font-normal text-mist">{tr('(optional)')}</span>
          </label>
          <input
            id="pd-t"
            inputMode="numeric"
            className="field num"
            value={form.telegram_chat_id}
            onChange={set('telegram_chat_id')}
            placeholder="123456789"
          />
          <p className="text-[12px] text-mist mt-1">{tr('They get it by pressing Start in the CMD Telegram bot.')}</p>
        </div>
      </form>
    </Dialog>
  );
}
