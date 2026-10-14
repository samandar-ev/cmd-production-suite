import RU from '../locales/ru';

export const lang = localStorage.getItem('lang') === 'ru' ? 'ru' : 'en';
export const locale = () => (lang === 'ru' ? 'ru-RU' : 'en-GB');
const fill = (text, params) => (params ? text.replace(/\{(\w+)\}/g, (m, k) => params[k] ?? m) : text);

export const tr = (key, params) => {
  const hit = lang === 'ru' ? RU[key] : null;
  return fill(typeof hit === 'string' ? hit : key.replace(/^[a-z]+\|/, ''), params);
};

const rules = new Intl.PluralRules(lang === 'ru' ? 'ru' : 'en');
export const trn = (n, one, many, params = {}) => {
  const p = { n, ...params };
  if (lang === 'ru' && Array.isArray(RU[one])) {
    const form = { one: 0, few: 1, many: 2, other: 2 }[rules.select(n)];
    return fill(RU[one][form], p);
  }
  return fill(n === 1 ? one : many, p);
};

export const setLanguage = code => {
  if (code === lang) return;
  localStorage.setItem('lang', code);
  location.reload();
};
