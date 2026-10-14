import { useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { Plus, Search, Phone, Mail, Trash2 } from 'lucide-react';
import api, { errorText, list } from '../lib/api';
import { useAuth } from '../lib/auth';
import { Avatar, Dialog, Empty, PageHeader, Spinner } from '../ui';
import { useLoad, useToast, useConfirm } from '../lib/hooks';
import { tr, trn } from '../lib/i18n';
import { PROJECT_STATUS_TEXT } from '../lib/stages';

const load = () => Promise.all([api.get('clients/').then(list), api.get('projects/').then(list)]);

export default function Clients() {
  const owner = useAuth(s => s.user)?.role === 'OWNER';
  const { data, reload } = useLoad(load, []);
  const [q, setQ] = useState('');
  const [open, setOpen] = useState(null);
  const rows = useMemo(() => {
    if (!data) return [];
    const s = q.trim().toLowerCase();
    return data[0].filter(
      c => !s || `${c.client_name} ${c.brand_name} ${c.contact_person} ${c.niche}`.toLowerCase().includes(s),
    );
  }, [data, q]);
  if (!data)
    return (
      <>
        <PageHeader title={tr('Clients')} />
        <Spinner />
      </>
    );
  const [clients, projects] = data;

  return (
    <>
      <PageHeader
        title={tr('Clients')}
        sub={tr('{clients}, {n} with active work', {
          clients: trn(clients.length, '{n} client', '{n} clients'),
          n: clients.filter(c => c.active_project_count).length,
        })}
        actions={
          owner && (
            <button onClick={() => setOpen({})} className="btn btn-primary">
              <Plus /> {tr('New client')}
            </button>
          )
        }
      />
      <label className="relative block max-w-xs mb-4">
        <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-mist" />
        <input
          value={q}
          onChange={e => setQ(e.target.value)}
          className="field pl-9"
          placeholder={tr('Find a client')}
          aria-label={tr('Find a client')}
        />
      </label>
      <section className="panel overflow-hidden">
        {rows.length === 0 ? (
          <Empty title={q ? tr('No client matches “{q}”', { q }) : tr('No clients yet')}>
            {owner && !q && tr('Add the companies you work for.')}
          </Empty>
        ) : (
          <ul className="divide-y divide-hairline">
            {rows.map(c => (
              <li key={c.id}>
                <button
                  onClick={() => setOpen(c)}
                  className="w-full text-left grid sm:grid-cols-[1fr_1fr_auto] items-center gap-x-6 gap-y-1 px-4 sm:px-5 py-4 hover:bg-haze"
                >
                  <span className="flex items-center gap-3 min-w-0">
                    <Avatar name={c.client_name} size={36} />
                    <span className="min-w-0">
                      <span className="block font-semibold truncate">{c.client_name}</span>
                      <span className="block text-[13px] text-graphite truncate">
                        {c.niche || c.brand_name || tr('No industry set')}
                      </span>
                    </span>
                  </span>
                  <span className="text-[14px] text-graphite truncate pl-12 sm:pl-0">
                    {c.contact_person}
                    {c.phone ? `, ${c.phone}` : ''}
                  </span>
                  <span className="text-[13px] text-graphite pl-12 sm:pl-0 num">
                    {c.active_project_count
                      ? tr('{n} active', { n: c.active_project_count })
                      : tr('No active projects')}
                  </span>
                </button>
              </li>
            ))}
          </ul>
        )}
      </section>
      {open && (
        <ClientDialog
          client={open}
          projects={projects.filter(p => p.client === open.id)}
          editable={owner}
          onClose={() => setOpen(null)}
          onSaved={reload}
        />
      )}
    </>
  );
}

function ClientDialog({ client, projects, editable, onClose, onSaved }) {
  const toast = useToast();
  const confirm = useConfirm();
  const isNew = !client.id;
  const [form, setForm] = useState({
    client_name: client.client_name || '',
    contact_person: client.contact_person || '',
    phone: client.phone || '',
    email: client.email || '',
    niche: client.niche || '',
    brand_notes: client.brand_notes || '',
  });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const set = k => e => setForm(f => ({ ...f, [k]: e.target.value }));
  const save = async e => {
    e.preventDefault();
    setBusy(true);
    setError('');
    try {
      isNew ? await api.post('clients/', form) : await api.patch(`clients/${client.id}/`, form);
      toast(isNew ? tr('Client added') : tr('Client updated'));
      onSaved();
      onClose();
    } catch (err) {
      setError(errorText(err));
    } finally {
      setBusy(false);
    }
  };
  const remove = async () => {
    if (
      !(await confirm({
        title: tr('Delete {name}?', { name: client.client_name }),
        body: tr('All of their projects, content, orders and files are deleted too. This can’t be undone.'),
        action: tr('Delete client'),
        danger: true,
      }))
    )
      return;
    await api
      .delete(`clients/${client.id}/`)
      .then(() => {
        toast(tr('Client deleted'));
        onSaved();
        onClose();
      })
      .catch(err => toast(errorText(err), 'error'));
  };
  const ro = !editable;
  return (
    <Dialog
      title={isNew ? tr('New client') : client.client_name}
      sub={!isNew && (client.niche || undefined)}
      onClose={onClose}
      footer={
        editable ? (
          <>
            {!isNew && (
              <button onClick={remove} className="btn btn-ghost text-tally mr-auto">
                <Trash2 /> {tr('Delete')}
              </button>
            )}
            <button onClick={onClose} className="btn btn-ghost">
              {tr('Cancel')}
            </button>
            <button
              form="cf"
              disabled={busy || !form.client_name.trim() || !form.contact_person.trim()}
              className="btn btn-primary"
            >
              {busy ? tr('Saving…') : isNew ? tr('Add client') : tr('Save changes')}
            </button>
          </>
        ) : null
      }
    >
      <form id="cf" onSubmit={save} className="grid sm:grid-cols-2 gap-4">
        {error && (
          <p role="alert" className="text-tally sm:col-span-2">
            {error}
          </p>
        )}
        <div className="sm:col-span-2">
          <label className="label" htmlFor="cf-n">
            {tr('Company')}
          </label>
          <input
            id="cf-n"
            className="field"
            value={form.client_name}
            onChange={set('client_name')}
            readOnly={ro}
            required
          />
        </div>
        <div>
          <label className="label" htmlFor="cf-c">
            {tr('Contact person')}
          </label>
          <input
            id="cf-c"
            className="field"
            value={form.contact_person}
            onChange={set('contact_person')}
            readOnly={ro}
            required
          />
        </div>
        <div>
          <label className="label" htmlFor="cf-i">
            {tr('Industry')}
          </label>
          <input
            id="cf-i"
            className="field"
            value={form.niche}
            onChange={set('niche')}
            readOnly={ro}
            placeholder={tr('e.g. Coffee shop')}
          />
        </div>
        <div>
          <label className="label" htmlFor="cf-p">
            {tr('Phone')}
          </label>
          <input
            id="cf-p"
            type="tel"
            className="field"
            value={form.phone}
            onChange={set('phone')}
            readOnly={ro}
            placeholder="+998 90 123 45 67"
          />
        </div>
        <div>
          <label className="label" htmlFor="cf-e">
            {tr('Email')}
          </label>
          <input id="cf-e" type="email" className="field" value={form.email} onChange={set('email')} readOnly={ro} />
        </div>
        <div className="sm:col-span-2">
          <label className="label" htmlFor="cf-b">
            {tr('Brand notes')}
          </label>
          <textarea
            id="cf-b"
            rows={3}
            className="field"
            value={form.brand_notes}
            onChange={set('brand_notes')}
            readOnly={ro}
            placeholder={tr('Tone of voice, colours, things to avoid')}
          />
        </div>
      </form>
      {!isNew && (
        <div className="mt-6">
          {(client.phone || client.email) && (
            <div className="flex flex-wrap gap-2 mb-5">
              {client.phone && (
                <a href={`tel:${client.phone}`} className="btn btn-quiet btn-sm">
                  <Phone /> {tr('Call')}
                </a>
              )}
              {client.email && (
                <a href={`mailto:${client.email}`} className="btn btn-quiet btn-sm">
                  <Mail /> {tr('Email')}
                </a>
              )}
            </div>
          )}
          <h3 className="font-semibold mb-2">{tr('Projects')}</h3>
          {projects.length === 0 ? (
            <p className="text-graphite text-[14px]">{tr('No projects yet.')}</p>
          ) : (
            <ul className="divide-y divide-hairline">
              {projects.map(p => (
                <li key={p.id}>
                  <Link
                    to={`/projects/${p.id}`}
                    onClick={onClose}
                    className="flex justify-between py-2.5 hover:underline underline-offset-2"
                  >
                    <span>{p.name}</span>
                    <span className="text-[13px] text-graphite">{PROJECT_STATUS_TEXT[p.status] || p.status}</span>
                  </Link>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </Dialog>
  );
}
