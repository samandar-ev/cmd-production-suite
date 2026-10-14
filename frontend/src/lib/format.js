import { locale, tr } from './i18n';
const loc = locale;

export const time = d => new Date(d).toLocaleTimeString(loc(), { hour: '2-digit', minute: '2-digit' });
export const day = d => new Date(d).toLocaleDateString(loc(), { day: 'numeric', month: 'short' });
export const dayLong = d => new Date(d).toLocaleDateString(loc(), { weekday: 'long', day: 'numeric', month: 'long' });
export const stamp = d =>
  new Date(d).toLocaleString(loc(), { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' });

const startOfDay = d => {
  const x = new Date(d);
  x.setHours(0, 0, 0, 0);
  return x;
};

export const when = d => {
  if (!d) return null;
  const date = new Date(d);
  const days = Math.round((startOfDay(date) - startOfDay(new Date())) / 864e5);
  if (days === 0) return tr('Today {time}', { time: time(date) });
  if (days === 1) return tr('Tomorrow {time}', { time: time(date) });
  if (days === -1) return tr('Yesterday {time}', { time: time(date) });
  if (days > 1 && days < 7) return `${date.toLocaleDateString(loc(), { weekday: 'short' })} ${time(date)}`;
  return day(date);
};

export const left = d => {
  if (!d) return null;
  const ms = new Date(d) - Date.now();
  const abs = Math.abs(ms);
  const txt =
    abs >= 864e5
      ? tr('{n} d', { n: Math.round(abs / 864e5) })
      : abs >= 36e5
        ? tr('{n} h', { n: Math.round(abs / 36e5) })
        : tr('{n} min', { n: Math.max(1, Math.round(abs / 6e4)) });
  return {
    late: ms < 0,
    text: ms < 0 ? tr('{t} late', { t: txt }) : tr('{t} left', { t: txt }),
    soon: ms >= 0 && ms < 864e5,
  };
};

export const ago = d => {
  const s = (Date.now() - new Date(d)) / 1000;
  if (s < 60) return tr('just now');
  if (s < 3600) return tr('{n} min ago', { n: Math.round(s / 60) });
  if (s < 86400) return tr('{n} h ago', { n: Math.round(s / 3600) });
  if (s < 7 * 86400) return tr('{n} d ago', { n: Math.round(s / 86400) });
  return day(d);
};

export const money = v => {
  if (v == null || v === '') return '—';
  const n = Math.round(Number(v));
  return new Intl.NumberFormat(localStorage.getItem('lang') === 'ru' ? 'ru-RU' : 'en-US', {
    style: 'currency',
    currency: 'USD',
    maximumFractionDigits: 0,
  }).format(n === 0 ? 0 : n);
};

export const initials = (name = '') =>
  name
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map(w => w[0])
    .join('')
    .toUpperCase() || '·';

export const greeting = () => {
  const h = new Date().getHours();
  return h < 5 ? tr('Good night') : h < 12 ? tr('Good morning') : h < 18 ? tr('Good afternoon') : tr('Good evening');
};
