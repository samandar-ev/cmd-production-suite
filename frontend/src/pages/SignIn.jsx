import { useState } from 'react';
import { Navigate, useLocation, useNavigate } from 'react-router-dom';
import { ArrowLeft } from 'lucide-react';
import { useAuth } from '../lib/auth';
import { errorText } from '../lib/api';
import { STAGES } from '../lib/stages';
import { tr } from '../lib/i18n';

function Slate() {
  return (
    <div aria-hidden className="relative">
      <div className="grid grid-cols-5 gap-1.5">
        {STAGES.map((s, i) => (
          <div key={s.key}>
            <div
              className="h-28 sm:h-40 lg:h-56 rounded-[6px]"
              style={{ background: s.color, opacity: 0.92 - i * 0.04 }}
            />
            <p className="mt-2.5 text-[13px] font-medium text-graphite">{s.label}</p>
          </div>
        ))}
      </div>
      <div className="slate-playhead absolute -top-3 bottom-7 w-[3px] rounded-full bg-tally">
        <span className="absolute -top-1.5 left-1/2 -translate-x-1/2 w-3 h-3 rounded-[3px] bg-tally rotate-45" />
      </div>
    </div>
  );
}

export default function SignIn() {
  const { user, signIn } = useAuth();
  const navigate = useNavigate();
  const from = useLocation().state?.from || '/';
  const [form, setForm] = useState({ username: '', password: '', code: '' });
  const [step, setStep] = useState('password');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  if (user) return <Navigate to={from} replace />;

  const set = k => e => {
    setForm(f => ({ ...f, [k]: k === 'code' ? e.target.value.replace(/\D/g, '') : e.target.value }));
    setError('');
  };
  const submit = async (e, resend = false) => {
    e?.preventDefault();
    setBusy(true);
    setError('');
    try {
      const res = await signIn(form.username.trim(), form.password, step === 'code' && !resend ? form.code : undefined);
      if (res.codeRequired) {
        setStep('code');
        setForm(f => ({ ...f, code: '' }));
        return;
      }
      navigate(from, { replace: true });
    } catch (err) {
      const status = err?.response?.status;
      setError(
        status === 401 && step === 'password'
          ? tr('That username and password don’t match. Check them and try again.')
          : errorText(err),
      );
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="min-h-dvh grid lg:grid-cols-[1.1fr_1fr]">
      <style>{`
        .slate-playhead { left: 0; animation: sweep 2.4s cubic-bezier(.65,0,.35,1) .3s both; }
        @keyframes sweep { from { left: 0; } to { left: 61%; } }
        @media (prefers-reduced-motion: reduce) { .slate-playhead { left: 61%; animation: none; } }
      `}</style>
      <section className="px-6 sm:px-10 lg:px-16 pt-10 lg:pt-16 pb-10 flex flex-col">
        <span className="display text-[22px] font-semibold flex items-center gap-1.5">
          {tr('CMD')}
          <span className="w-2 h-2 rounded-full bg-tally mb-3.5" aria-hidden />
        </span>
        <div className="mt-10 lg:mt-auto lg:mb-auto max-w-[620px] w-full">
          <h1 className="display text-[30px] sm:text-[40px] leading-[1.08] font-semibold">
            {tr('Plan it, shoot it,')}
            <br />
            {tr('cut it, ship it.')}
          </h1>
          <p className="text-graphite mt-4 max-w-[44ch]">
            {tr('The production floor of CMD Agency — every client, shoot, edit and review in one timeline.')}
          </p>
          <div className="mt-10">
            <Slate />
          </div>
        </div>
      </section>

      <section className="bg-paper lg:border-l border-hairline px-6 sm:px-10 lg:px-16 py-10 flex items-center">
        <form onSubmit={submit} className="w-full max-w-[380px] mx-auto lg:mx-0" noValidate>
          {step === 'password' ? (
            <>
              <h2 className="text-[22px] font-semibold">{tr('Sign in')}</h2>
              <p className="text-graphite mt-1 mb-7">{tr('Use the username your manager set up for you.')}</p>
              <label className="label" htmlFor="u">
                {tr('Username')}
              </label>
              <input
                id="u"
                className="field h-12"
                autoComplete="username"
                autoCapitalize="none"
                value={form.username}
                onChange={set('username')}
                required
                autoFocus
              />
              <label className="label mt-4" htmlFor="p">
                {tr('Password')}
              </label>
              <input
                id="p"
                className="field h-12"
                type="password"
                autoComplete="current-password"
                value={form.password}
                onChange={set('password')}
                required
              />
            </>
          ) : (
            <>
              <button
                type="button"
                onClick={() => {
                  setStep('password');
                  setError('');
                }}
                className="btn btn-ghost btn-sm -ml-3 mb-4"
              >
                <ArrowLeft /> {tr('Back')}
              </button>
              <h2 className="text-[22px] font-semibold">{tr('Check Telegram')}</h2>
              <p className="text-graphite mt-1 mb-7">
                {tr('We sent a 6-digit code to your Telegram. It works for 5 minutes.')}
              </p>
              <label className="label" htmlFor="c">
                {tr('Code')}
              </label>
              <input
                id="c"
                className="field h-14 text-center text-[24px] tracking-[0.5em] num"
                inputMode="numeric"
                autoComplete="one-time-code"
                maxLength={6}
                value={form.code}
                onChange={set('code')}
                autoFocus
              />
              <button
                type="button"
                onClick={() => submit(null, true)}
                disabled={busy}
                className="btn btn-ghost btn-sm -ml-3 mt-2"
              >
                {tr('Send a new code')}
              </button>
            </>
          )}
          {error && (
            <p role="alert" className="mt-4 text-[14px] text-tally">
              {error}
            </p>
          )}
          <button
            className="btn btn-primary w-full h-12 mt-6 text-[15px]"
            disabled={busy || (step === 'password' ? !form.username || !form.password : form.code.length !== 6)}
          >
            {busy ? tr('Checking…') : step === 'password' ? tr('Sign in') : tr('Confirm')}
          </button>
          <p className="text-[13px] text-mist mt-6">
            {tr('Forgot your password? Ask the owner to set a new one in Team.')}
          </p>
        </form>
      </section>
    </div>
  );
}
