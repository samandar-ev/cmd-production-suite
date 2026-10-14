import axios from 'axios';
import { tr } from './i18n';

const api = axios.create({ baseURL: '/api/v1/', headers: { 'Content-Type': 'application/json' } });

api.interceptors.request.use(config => {
  const token = localStorage.getItem('access_token');
  if (token) config.headers.Authorization = `Bearer ${token}`;
  config.headers['Accept-Language'] = localStorage.getItem('lang') || 'en';
  return config;
});

let refreshing = null;
const refresh = () => {
  refreshing ??= axios
    .post('/api/v1/auth/refresh/', { refresh: localStorage.getItem('refresh_token') })
    .then(({ data }) => {
      localStorage.setItem('access_token', data.access);
      if (data.refresh) localStorage.setItem('refresh_token', data.refresh);
      return data.access;
    })
    .finally(() => {
      refreshing = null;
    });
  return refreshing;
};

api.interceptors.response.use(
  r => r,
  async error => {
    const req = error.config;
    if (error.response?.status === 401 && !req._retry && !req.url.includes('auth/')) {
      req._retry = true;
      const token = localStorage.getItem('refresh_token') && (await refresh().catch(() => null));
      if (token) {
        req.headers.Authorization = `Bearer ${token}`;
        return api(req);
      }
      localStorage.removeItem('access_token');
      localStorage.removeItem('refresh_token');
      if (!location.pathname.startsWith('/sign-in')) location.assign('/sign-in');
    }
    return Promise.reject(error);
  },
);

export const list = res => (Array.isArray(res.data) ? res.data : res.data?.results || []);

export const errorText = (err, fallback = tr('Something went wrong. Try again.')) => {
  const d = err?.response?.data;
  if (!d) return err?.message === 'Network Error' ? tr('Can’t reach the server. Check your connection.') : fallback;
  if (typeof d === 'string') return fallback;
  if (d.error || d.detail) return d.error || d.detail;
  return Object.values(d).flat().map(String).join(' ');
};

export default api;
