import { useState } from 'react';
import { Plus, Printer, Search } from 'lucide-react';
import api, { errorText, list } from '../lib/api';
import { day, money } from '../lib/format';
import { Dialog, Empty, PageHeader, Spinner } from '../ui';
import { useLoad, useToast, useConfirm } from '../lib/hooks';
import { tr, trn } from '../lib/i18n';

const STATUS = [
  ['draft', tr('Draft')],
  ['sent', tr('Sent')],
  ['signed', tr('Signed')],
  ['generated', tr('Ready')],
  ['uploaded', tr('Uploaded')],
];
const S = Object.fromEntries(STATUS);
const load = () => Promise.all([api.get('contracts/').then(list), api.get('projects/').then(list)]);

export default function Contracts() {
  const { data, reload } = useLoad(load, []);
  const [open, setOpen] = useState(null);
  const [q, setQ] = useState('');
  if (!data)
    return (
      <>
        <PageHeader title={tr('Contracts')} />
        <Spinner />
      </>
    );
  const [contracts, projects] = data;
  const s = q.trim().toLowerCase();
  const rows = contracts.filter(
    c => !s || `${c.contract_number} ${c.project_name} ${c.client_name}`.toLowerCase().includes(s),
  );
  return (
    <>
      <PageHeader
        title={tr('Contracts')}
        sub={tr('{contracts}, {n} signed', {
          contracts: trn(contracts.length, '{n} contract', '{n} contracts'),
          n: contracts.filter(c => c.status === 'signed').length,
        })}
        actions={
          <button onClick={() => setOpen({})} className="btn btn-primary">
            <Plus /> {tr('New contract')}
          </button>
        }
      />
      <label className="relative block max-w-xs mb-4">
        <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-mist" />
        <input
          value={q}
          onChange={e => setQ(e.target.value)}
          className="field pl-9"
          placeholder={tr('Find a contract')}
          aria-label={tr('Find a contract')}
        />
      </label>
      <section className="panel overflow-hidden">
        {rows.length === 0 ? (
          <Empty title={tr('No contracts yet')}>
            {tr('Create one for a project; the client and fee are filled in for you.')}
          </Empty>
        ) : (
          <ul className="divide-y divide-hairline">
            {rows.map(c => (
              <li key={c.id}>
                <button
                  onClick={() => setOpen(c)}
                  className="w-full text-left grid sm:grid-cols-[1fr_auto_auto] items-center gap-x-6 gap-y-1 px-5 py-4 hover:bg-haze"
                >
                  <span className="min-w-0">
                    <span className="block font-semibold truncate">{c.contract_number}</span>
                    <span className="block text-[13px] text-graphite truncate">
                      {c.client_name}, {c.project_name}
                    </span>
                  </span>
                  <span className="text-[13px] text-graphite">
                    {c.issued_date ? day(c.issued_date) : tr('Not issued')}
                  </span>
                  <span
                    className={`text-[13px] font-semibold ${c.status === 'signed' ? 'text-publish' : 'text-graphite'}`}
                  >
                    {S[c.status] || c.status}
                  </span>
                </button>
              </li>
            ))}
          </ul>
        )}
      </section>
      {open && (
        <ContractDialog
          contract={open}
          projects={projects}
          nextNo={contracts.length + 1}
          onClose={() => setOpen(null)}
          onSaved={reload}
        />
      )}
    </>
  );
}

function ContractDialog({ contract, projects, nextNo, onClose, onSaved }) {
  const toast = useToast();
  const confirm = useConfirm();
  const isNew = !contract.id;
  const [form, setForm] = useState({
    contract_number: contract.contract_number || `CMD-${new Date().getFullYear()}-${String(nextNo).padStart(3, '0')}`,
    project: contract.project || projects[0]?.id || '',
    status: contract.status || 'draft',
    issued_date: contract.issued_date || '',
    terms_and_conditions: contract.terms_and_conditions || '',
  });
  const set = k => e => setForm(f => ({ ...f, [k]: e.target.value }));
  const project = projects.find(p => String(p.id) === String(form.project));
  const save = async e => {
    e?.preventDefault();
    try {
      isNew
        ? await api.post('contracts/', { ...form, issued_date: form.issued_date || null })
        : await api.patch(`contracts/${contract.id}/`, { ...form, issued_date: form.issued_date || null });
      toast(isNew ? tr('Contract created') : tr('Contract saved'));
      onSaved();
      onClose();
    } catch (err) {
      toast(errorText(err), 'error');
    }
  };
  const remove = async () => {
    if (
      !(await confirm({
        title: tr('Delete contract {number}?', { number: form.contract_number }),
        body: tr('It can’t be brought back.'),
        action: tr('Delete contract'),
        danger: true,
      }))
    )
      return;
    await api.delete(`contracts/${contract.id}/`).catch(() => {});
    onSaved();
    onClose();
  };
  const print = () => {
    const w = window.open('', '_blank');
    const esc = t => String(t || '').replace(/[&<>]/g, ch => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;' })[ch]);
    w.document.write(`<!doctype html><meta charset="utf-8"><title>${esc(form.contract_number)}</title>
      <style>body{font:15px/1.6 Georgia,serif;max-width:700px;margin:48px auto;padding:0 24px;color:#111}h1{font:600 22px system-ui;margin:0 0 4px}
      .meta{color:#555;margin-bottom:28px}pre{white-space:pre-wrap;font:inherit}.sig{display:flex;gap:48px;margin-top:64px}.sig div{flex:1;border-top:1px solid #111;padding-top:6px;font-size:13px}</style>
      <h1>Contract ${esc(form.contract_number)}</h1>
      <div class="meta">${esc(project?.client_name)} — ${esc(project?.name)}<br>${form.issued_date ? `Date: ${esc(form.issued_date)}` : ''}${project?.service_fee ? `<br>Fee: ${esc(money(project.service_fee))}` : ''}</div>
      <pre>${esc(form.terms_and_conditions)}</pre><div class="sig"><div>CMD Agency</div><div>${esc(project?.client_name)}</div></div>`);
    w.document.close();
    w.focus();
    w.print();
  };
  return (
    <Dialog
      title={isNew ? tr('New contract') : form.contract_number}
      onClose={onClose}
      wide
      footer={
        <>
          {!isNew && (
            <button onClick={remove} className="btn btn-ghost text-tally mr-auto">
              {tr('Delete')}
            </button>
          )}
          <button onClick={print} className="btn btn-quiet">
            <Printer /> {tr('Print / save as PDF')}
          </button>
          <button onClick={save} className="btn btn-primary">
            {isNew ? tr('Create') : tr('Save')}
          </button>
        </>
      }
    >
      <form onSubmit={save} className="grid sm:grid-cols-2 gap-4">
        <div>
          <label className="label" htmlFor="ct-n">
            {tr('Number')}
          </label>
          <input id="ct-n" className="field" value={form.contract_number} onChange={set('contract_number')} />
        </div>
        <div>
          <label className="label" htmlFor="ct-p">
            {tr('Project')}
          </label>
          <select id="ct-p" className="field" value={form.project} onChange={set('project')}>
            {projects.map(p => (
              <option key={p.id} value={p.id}>
                {p.name}
              </option>
            ))}
          </select>
        </div>
        <div>
          <label className="label" htmlFor="ct-s">
            {tr('Status')}
          </label>
          <select id="ct-s" className="field" value={form.status} onChange={set('status')}>
            {STATUS.map(([k, l]) => (
              <option key={k} value={k}>
                {l}
              </option>
            ))}
          </select>
        </div>
        <div>
          <label className="label" htmlFor="ct-d">
            {tr('Issued')}
          </label>
          <input id="ct-d" type="date" className="field" value={form.issued_date || ''} onChange={set('issued_date')} />
        </div>
        <div className="sm:col-span-2">
          <label className="label" htmlFor="ct-t">
            {tr('Terms')}
          </label>
          <textarea
            id="ct-t"
            rows={10}
            className="field"
            value={form.terms_and_conditions}
            onChange={set('terms_and_conditions')}
            placeholder={tr('Scope of work, deliverables, payment schedule, rights to the footage…')}
          />
        </div>
      </form>
    </Dialog>
  );
}
