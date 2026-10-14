import { create } from 'zustand';
import api from './api';
import { lang, setLanguage, tr } from './i18n';

export const MANAGER = ['OWNER', 'PROJECT_MANAGER'];
export const ROLE_TEXT = {
  OWNER: tr('Owner'),
  PROJECT_MANAGER: tr('Project manager'),
  VIDEOGRAPHER: tr('Videographer'),
  EDITOR: tr('Editor'),
};

export const useAuth = create((set, get) => ({
  user: null,
  ready: false,

  async load() {
    if (!localStorage.getItem('access_token')) return set({ user: null, ready: true });
    try {
      const { data } = await api.get('users/me/');
      if ((data.language || 'en') !== lang) return setLanguage(data.language || 'en');
      set({ user: data, ready: true });
    } catch {
      set({ user: null, ready: true });
    }
  },

  async signIn(username, password, code) {
    const { data } = await api.post('auth/login/', { username, password, ...(code ? { code } : {}) });
    if (data.code_required) return { codeRequired: true };
    localStorage.setItem('access_token', data.access);
    localStorage.setItem('refresh_token', data.refresh);
    await get().load();
    return { user: get().user };
  },

  signOut() {
    const refresh = localStorage.getItem('refresh_token');
    if (refresh) api.post('auth/logout/', { refresh }).catch(() => {});
    localStorage.removeItem('access_token');
    localStorage.removeItem('refresh_token');
    set({ user: null });
  },

  setUser: user => set({ user }),
}));

export const isManager = u => MANAGER.includes(u?.role);
export const nameOf = u => u?.full_name || [u?.first_name, u?.last_name].filter(Boolean).join(' ') || u?.username || '';
