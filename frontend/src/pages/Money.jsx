import { useCallback, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { Plus, Check, Search } from 'lucide-react';
import api, { errorText, list } from '../lib/api';
import { day, money } from '../lib/format';
import { Dialog, PageHeader, Spinner } from '../ui';
import { useToast, useConfirm } from '../lib/hooks';
import { locale as loc, tr } from '../lib/i18n';

const trd = s => (s ? tr(s) : s);
const ymd = d =>
  `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
const PERIODS = {
  month: () => {
    const e = new Date();
    const s = new Date(e.getFullYear(), e.getMonth(), 1);
    return [s, e, tr('This month')];
  },
  last: () => {
    const e = new Date();
    e.setDate(0);
    const s = new Date(e.getFullYear(), e.getMonth(), 1);
    return [s, e, tr('Last month')];
  },
  quarter: () => {
    const e = new Date();
    const s = new Date(e.getFullYear(), Math.floor(e.getMonth() / 3) * 3, 1);
    return [s, e, tr('This quarter')];
  },
  year: () => {
    const e = new Date();
    return [new Date(e.getFullYear(), 0, 1), e, tr('This year')];
  },
};
const pct = (now, prev) => (prev ? Math.round(((now - prev) / Math.abs(prev)) * 100) : null);

export default function Money() {
  const [period, setPeriod] = useState('month');
  const [basis, setBasis] = useState('accrual');
  const [sum, setSum] = useState(null);
  const [adding, setAdding] = useState(null);
  const [s, e, label] = PERIODS[period]();
  const start = ymd(s),
    end = ymd(e);
  const load = useCallback(
    () =>
      api
        .get('finance/summary/', { params: { start, end, basis } })
        .then(r => setSum(r.data))
        .catch(() => setSum({ error: true })),
    [start, end, basis],
  );
  useEffect(() => {
    load();
  }, [load]);

  return (
    <>
      <PageHeader
        title={tr('Money')}
        sub={tr('Profit, cash and who owes whom.')}
        actions={
          <>
            <button onClick={() => setAdding('expense')} className="btn btn-quiet">
              <Plus /> {tr('Expense')}
            </button>
            <button onClick={() => setAdding('income')} className="btn btn-primary">
              <Plus /> {tr('button|Income')}
            </button>
          </>
        }
      />
      <div className="flex flex-wrap gap-2 mb-6">
        <div className="seg" role="group" aria-label={tr('Period')}>
          {Object.entries(PERIODS).map(([k, f]) => (
            <button key={k} aria-pressed={period === k} onClick={() => setPeriod(k)}>
              {f()[2]}
            </button>
          ))}
        </div>
        <div className="seg" role="group" aria-label={tr('Count money')}>
          <button
            aria-pressed={basis === 'accrual'}
            onClick={() => setBasis('accrual')}
            title={tr('Income and costs count on the day they’re earned or billed')}
          >
            {tr('When earned')}
          </button>
          <button
            aria-pressed={basis === 'cash'}
            onClick={() => setBasis('cash')}
            title={tr('Only money that actually moved, on the day it moved')}
          >
            {tr('When paid')}
          </button>
        </div>
      </div>
      {!sum ? (
        <Spinner />
      ) : sum.error ? (
        <p className="text-tally">{tr('Couldn’t load the numbers.')}</p>
      ) : (
        <Body sum={sum} label={label} onChange={load} />
      )}
      {adding && <TxDialog type={adding} onClose={() => setAdding(null)} onSaved={load} />}
    </>
  );
}

function Body({ sum, label, onChange }) {
  const toast = useToast();
  const p = sum.pnl;
  const change = pct(Number(p.net_profit), Number(sum.previous?.net_profit));
  const ladder = [
    [tr('Income'), p.income, 1],
    [tr('Production costs'), -p.groups.direct],
    [tr('Gross profit'), p.gross_profit, 1],
    [tr('Salaries'), -p.groups.payroll],
    [tr('Running costs'), -p.groups.operating],
    [tr('Taxes'), -p.groups.tax],
    [tr('Profit'), p.net_profit, 2],
  ];
  const max = Math.max(...sum.trend.flatMap(m => [Number(m.income), Number(m.expense)]), 1);
  const markPaid = async t => {
    await api
      .post(`finance/transactions/${t.id}/mark_paid/`)
      .then(() => {
        toast(tr('Marked as paid'));
        onChange();
      })
      .catch(err => toast(errorText(err), 'error'));
  };

  return (
    <div className="space-y-6">
      <div className="grid lg:grid-cols-[1.1fr_1fr] gap-6">
        <section className="panel p-6 sm:p-7">
          <p className="text-graphite">
            {label}
            {tr(', profit')}
          </p>
          <p
            className={`display text-[39px] sm:text-[48px] font-semibold num leading-none mt-2 ${Number(p.net_profit) < 0 ? 'text-tally' : ''}`}
          >
            {money(p.net_profit)}
          </p>
          <p className="text-[14px] text-graphite mt-3 num">
            {tr('{in} in, {out} out', { in: money(p.income), out: money(p.expense) })}
            {p.net_margin != null ? `, ${tr('{n}% margin', { n: p.net_margin })}` : ''}
            {change != null && (
              <span className={change >= 0 ? 'text-publish' : 'text-tally'}>
                {' '}
                — {change >= 0 ? '+' : ''}
                {change}
                {tr('% vs the period before')}
              </span>
            )}
          </p>
          <dl className="mt-6 space-y-2">
            {ladder.map(([name, v, strong]) => (
              <div
                key={name}
                className={`flex items-baseline justify-between gap-4 text-[14px] ${strong ? 'font-semibold pt-2 border-t border-hairline' : 'text-graphite'}`}
              >
                <dt>{name}</dt>
                <dd className="num">{money(v)}</dd>
              </div>
            ))}
          </dl>
        </section>

        <section className="panel p-6 sm:p-7">
          <div className="flex items-baseline justify-between mb-5">
            <h2 className="text-[17px] font-semibold">{tr('Last 12 months')}</h2>
            <span className="flex gap-4 text-[13px] text-graphite">
              <span className="flex items-center gap-1.5">
                <span className="w-2.5 h-2.5 rounded-[2px] bg-ink" />
                {tr('In')}
              </span>
              <span className="flex items-center gap-1.5">
                <span className="w-2.5 h-2.5 rounded-[2px] bg-[#B8BDC4]" />
                {tr('Out')}
              </span>
            </span>
          </div>
          <div
            className="h-48 flex items-end gap-[6px]"
            role="img"
            aria-label={tr('Money in and out per month for the last 12 months')}
          >
            {sum.trend.map(m => (
              <div
                key={m.month}
                className="flex-1 h-full flex flex-col justify-end group relative"
                title={tr('{month}: in {in}, out {out}, profit {profit}', {
                  month: m.month,
                  in: money(m.income),
                  out: money(m.expense),
                  profit: money(m.net),
                })}
              >
                <div className="flex items-end gap-[2px] h-full">
                  <span
                    className="flex-1 rounded-t-[3px] bg-ink"
                    style={{ height: `${(Number(m.income) / max) * 100}%` }}
                  />
                  <span
                    className="flex-1 rounded-t-[3px] bg-[#B8BDC4]"
                    style={{ height: `${(Number(m.expense) / max) * 100}%` }}
                  />
                </div>
                <span className="text-[11px] text-mist text-center mt-1.5">
                  {new Date(`${m.month}-01`).toLocaleDateString(loc(), { month: 'narrow' })}
                </span>
              </div>
            ))}
          </div>
          <details className="mt-4 text-[13px]">
            <summary className="cursor-pointer text-graphite">{tr('Show as a table')}</summary>
            <table className="w-full mt-2 num">
              <thead>
                <tr className="text-left text-mist">
                  <th className="font-medium py-1">{tr('Month')}</th>
                  <th className="font-medium text-right">{tr('In')}</th>
                  <th className="font-medium text-right">{tr('Out')}</th>
                  <th className="font-medium text-right">{tr('Profit')}</th>
                </tr>
              </thead>
              <tbody>
                {sum.trend.map(m => (
                  <tr key={m.month} className="border-t border-hairline">
                    <td className="py-1">{m.month}</td>
                    <td className="text-right">{money(m.income)}</td>
                    <td className="text-right">{money(m.expense)}</td>
                    <td className="text-right">{money(m.net)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </details>
        </section>
      </div>

      <div className="grid md:grid-cols-2 gap-6">
        {[
          [tr('Owed to you'), sum.receivables],
          [tr('You owe'), sum.payables],
        ].map(([title, r]) => (
          <section key={title} className="panel p-5 sm:p-6">
            <div className="flex items-baseline justify-between mb-1">
              <h2 className="text-[17px] font-semibold">{title}</h2>
              <span className="display text-[20px] font-semibold num">{money(r.total)}</span>
            </div>
            {r.overdue_count > 0 && (
              <p className="text-[14px] text-tally mb-2 num">
                {money(r.overdue)} {tr('overdue')}
              </p>
            )}
            {r.items.length === 0 ? (
              <p className="text-graphite text-[14px] py-3">{tr('Nothing outstanding.')}</p>
            ) : (
              <ul className="divide-y divide-hairline">
                {r.items.map(t => (
                  <li key={t.id} className="flex items-center gap-3 py-3">
                    <span className="min-w-0 flex-1">
                      <span className="block font-medium truncate">
                        {t.counterparty || t.client_name || trd(t.category_name)}
                      </span>
                      <span className={`block text-[13px] truncate ${t.is_overdue ? 'text-tally' : 'text-graphite'}`}>
                        {t.description?.replace('[demo] ', '') || trd(t.category_name)}
                        {t.due_date ? `, ${tr('due {date}', { date: day(t.due_date) })}` : ''}
                      </span>
                    </span>
                    <span className="font-semibold num">{money(t.amount)}</span>
                    <button
                      onClick={() => markPaid(t)}
                      className="btn btn-quiet btn-sm"
                      aria-label={tr('Mark {name} as paid', { name: t.counterparty })}
                    >
                      <Check /> {tr('Paid')}
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </section>
        ))}
      </div>

      <div className="grid lg:grid-cols-[1fr_1.4fr] gap-6 items-start">
        <section className="panel p-5 sm:p-6">
          <h2 className="text-[17px] font-semibold mb-1">{tr('Cash')}</h2>
          <p className="display text-[25px] font-semibold num">{money(sum.cash)}</p>
          {sum.runway_months != null && (
            <p className="text-[14px] text-graphite mt-1">
              {tr('About {n} months of costs at the current pace.', { n: sum.runway_months })}
            </p>
          )}
          <ul className="mt-4 divide-y divide-hairline">
            {sum.accounts.map(a => (
              <li key={a.id} className="flex justify-between py-2.5 text-[14px]">
                <span>{trd(a.name)}</span>
                <span className="font-semibold num">{money(a.balance)}</span>
              </li>
            ))}
          </ul>
        </section>
        <section className="panel p-5 sm:p-6 min-w-0">
          <h2 className="text-[17px] font-semibold mb-3">{tr('Projects')}</h2>
          <div className="scroll-x">
            <table className="w-full text-[14px] num min-w-[480px]">
              <thead>
                <tr className="text-left text-graphite">
                  <th className="font-medium pb-2">{tr('Project')}</th>
                  <th className="font-medium text-right">{tr('Billed')}</th>
                  <th className="font-medium text-right">{tr('Costs')}</th>
                  <th className="font-medium text-right">{tr('Profit')}</th>
                  <th className="font-medium text-right">{tr('Still to bill')}</th>
                </tr>
              </thead>
              <tbody>
                {sum.projects.slice(0, 8).map(r => (
                  <tr key={r.id} className="border-t border-hairline">
                    <td className="py-2.5 pr-3">
                      <Link to={`/projects/${r.id}`} className="font-medium hover:underline underline-offset-2">
                        {r.name}
                      </Link>
                      <span className="block text-[12px] text-mist">{r.client}</span>
                    </td>
                    <td className="text-right">{money(r.invoiced)}</td>
                    <td className="text-right text-graphite">{money(r.costs)}</td>
                    <td className={`text-right font-semibold ${Number(r.profit) < 0 ? 'text-tally' : ''}`}>
                      {money(r.profit)}
                    </td>
                    <td className="text-right text-graphite">{money(r.to_invoice)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      </div>
      <Transactions onChange={onChange} />
    </div>
  );
}

function Transactions({ onChange }) {
  const [rows, setRows] = useState(null);
  const [q, setQ] = useState('');
  const [editing, setEditing] = useState(null);
  const load = useCallback(
    () =>
      api
        .get('finance/transactions/', { params: q ? { q } : {} })
        .then(list)
        .then(setRows)
        .catch(() => setRows([])),
    [q],
  );
  useEffect(() => {
    const t = setTimeout(load, 250);
    return () => clearTimeout(t);
  }, [load]);
  return (
    <section className="panel overflow-hidden">
      <div className="flex flex-wrap items-center justify-between gap-3 px-5 py-4 border-b border-hairline">
        <h2 className="text-[17px] font-semibold">{tr('All transactions')}</h2>
        <label className="relative w-full sm:w-64">
          <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-mist" />
          <input
            value={q}
            onChange={e => setQ(e.target.value)}
            className="field pl-9"
            placeholder={tr('Find by who, what or invoice')}
            aria-label={tr('Find transactions')}
          />
        </label>
      </div>
      {!rows ? (
        <Spinner />
      ) : (
        <ul className="divide-y divide-hairline max-h-[520px] overflow-y-auto">
          {rows.slice(0, 100).map(t => (
            <li key={t.id}>
              <button
                onClick={() => setEditing(t)}
                className="w-full text-left flex items-center gap-4 px-5 py-3 hover:bg-haze"
              >
                <span className="text-[13px] text-graphite num w-14 shrink-0">{day(t.date)}</span>
                <span className="min-w-0 flex-1">
                  <span className="block font-medium truncate">
                    {t.counterparty || trd(t.category_name) || tr('Transfer')}
                  </span>
                  <span className="block text-[13px] text-graphite truncate">
                    {[
                      trd(t.category_name),
                      t.project_name,
                      t.status === 'pending' && (t.is_overdue ? tr('overdue') : tr('not paid yet')),
                    ]
                      .filter(Boolean)
                      .join(', ')}
                  </span>
                </span>
                <span
                  className={`font-semibold num shrink-0 ${t.type === 'income' ? '' : 'text-graphite'} ${t.is_overdue ? 'text-tally' : ''}`}
                >
                  {t.type === 'expense' ? '−' : t.type === 'income' ? '+' : ''}
                  {money(t.amount)}
                </span>
              </button>
            </li>
          ))}
          {rows.length === 0 && (
            <li className="p-6 text-graphite">
              {tr('No transactions')}
              {q ? ` match “${q}”` : ' yet'}.
            </li>
          )}
        </ul>
      )}
      {editing && (
        <TxDialog
          tx={editing}
          type={editing.type}
          onClose={() => setEditing(null)}
          onSaved={() => {
            load();
            onChange();
          }}
        />
      )}
    </section>
  );
}

function TxDialog({ tx, type, onClose, onSaved }) {
  const toast = useToast();
  const confirm = useConfirm();
  const [opts, setOpts] = useState(null);
  const [form, setForm] = useState(() => ({
    type,
    amount: tx?.amount || '',
    date: tx?.date || ymd(new Date()),
    account: tx?.account || '',
    category: tx?.category || '',
    project: tx?.project || '',
    client: tx?.client || '',
    counterparty: tx?.counterparty || '',
    description: tx?.description || '',
    status: tx?.status || 'paid',
    due_date: tx?.due_date || '',
  }));
  useEffect(() => {
    Promise.all([
      api.get('finance/accounts/').then(list),
      api.get('finance/categories/').then(list),
      api.get('projects/').then(list),
      api.get('clients/').then(list),
    ]).then(([accounts, categories, projects, clients]) => {
      setOpts({ accounts, categories, projects, clients });
      setForm(f => ({ ...f, account: f.account || accounts[0]?.id || '' }));
    });
  }, []);
  const set = k => e => setForm(f => ({ ...f, [k]: e.target.value }));
  const save = async e => {
    e.preventDefault();
    const body = Object.fromEntries(Object.entries(form).map(([k, v]) => [k, v === '' ? null : v]));
    try {
      tx ? await api.patch(`finance/transactions/${tx.id}/`, body) : await api.post('finance/transactions/', body);
      toast(tx ? tr('Saved') : form.type === 'income' ? tr('Income added') : tr('Expense added'));
      onSaved();
      onClose();
    } catch (err) {
      toast(errorText(err), 'error');
    }
  };
  const remove = async () => {
    if (
      !(await confirm({
        title: tr('Delete this transaction?'),
        body: tr('Profit, cash and the reports will be recalculated without it.'),
        action: tr('Delete'),
        danger: true,
      }))
    )
      return;
    await api.delete(`finance/transactions/${tx.id}/`).catch(() => {});
    onSaved();
    onClose();
  };
  const income = form.type === 'income';
  const cats = (opts?.categories || []).filter(c =>
    (income ? ['revenue', 'other_income'] : ['direct', 'payroll', 'operating', 'tax']).includes(c.group),
  );
  return (
    <Dialog
      title={tx ? tr('Transaction') : income ? tr('Money in') : tr('Money out')}
      onClose={onClose}
      footer={
        <>
          {tx && (
            <button onClick={remove} className="btn btn-ghost text-tally mr-auto">
              {tr('Delete')}
            </button>
          )}
          <button onClick={onClose} className="btn btn-ghost">
            {tr('Cancel')}
          </button>
          <button form="tx" disabled={!form.amount} className="btn btn-primary">
            {tx ? tr('Save') : tr('Add')}
          </button>
        </>
      }
    >
      {!opts ? (
        <Spinner />
      ) : (
        <form id="tx" onSubmit={save} className="grid grid-cols-2 gap-4">
          <div className="col-span-2 seg" role="group" aria-label={tr('Type')}>
            <button
              type="button"
              className="flex-1"
              aria-pressed={income}
              onClick={() => setForm(f => ({ ...f, type: 'income', category: '' }))}
            >
              {tr('Money in')}
            </button>
            <button
              type="button"
              className="flex-1"
              aria-pressed={form.type === 'expense'}
              onClick={() => setForm(f => ({ ...f, type: 'expense', category: '' }))}
            >
              {tr('Money out')}
            </button>
          </div>
          <div>
            <label className="label" htmlFor="tx-a">
              {tr('Amount, USD')}
            </label>
            <input
              id="tx-a"
              type="number"
              min="0"
              step="0.01"
              className="field num text-[18px] font-semibold"
              value={form.amount}
              onChange={set('amount')}
              required
              autoFocus
            />
          </div>
          <div>
            <label className="label" htmlFor="tx-d">
              {tr('Date')}
            </label>
            <input id="tx-d" type="date" className="field" value={form.date} onChange={set('date')} />
          </div>
          <div className="col-span-2">
            <label className="label" htmlFor="tx-w">
              {income ? tr('From') : tr('To')}
            </label>
            <input
              id="tx-w"
              className="field"
              value={form.counterparty}
              onChange={set('counterparty')}
              placeholder={income ? tr('Client or payer') : tr('Shop, person or company')}
            />
          </div>
          <div>
            <label className="label" htmlFor="tx-c">
              {tr('Category')}
            </label>
            <select id="tx-c" className="field" value={form.category || ''} onChange={set('category')}>
              <option value="">{tr('Choose…')}</option>
              {cats.map(c => (
                <option key={c.id} value={c.id}>
                  {trd(c.name)}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="label" htmlFor="tx-ac">
              {tr('Account')}
            </label>
            <select id="tx-ac" className="field" value={form.account || ''} onChange={set('account')}>
              {opts.accounts.map(a => (
                <option key={a.id} value={a.id}>
                  {trd(a.name)}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="label" htmlFor="tx-p">
              {tr('Project')}
            </label>
            <select id="tx-p" className="field" value={form.project || ''} onChange={set('project')}>
              <option value="">{tr('None')}</option>
              {opts.projects.map(p => (
                <option key={p.id} value={p.id}>
                  {p.name}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="label" htmlFor="tx-s">
              {tr('Paid?')}
            </label>
            <select id="tx-s" className="field" value={form.status} onChange={set('status')}>
              <option value="paid">{tr('Paid')}</option>
              <option value="pending">{tr('Not yet')}</option>
            </select>
          </div>
          {form.status === 'pending' && (
            <div className="col-span-2">
              <label className="label" htmlFor="tx-due">
                {tr('Due')}
              </label>
              <input id="tx-due" type="date" className="field" value={form.due_date || ''} onChange={set('due_date')} />
            </div>
          )}
          <div className="col-span-2">
            <label className="label" htmlFor="tx-n">
              {tr('Note')}
            </label>
            <input
              id="tx-n"
              className="field"
              value={form.description}
              onChange={set('description')}
              placeholder={tr('e.g. Invoice #1044')}
            />
          </div>
        </form>
      )}
    </Dialog>
  );
}
