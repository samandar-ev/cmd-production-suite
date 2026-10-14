import { createContext, useCallback, useContext, useEffect, useRef, useState } from 'react';
import { isManager } from './auth';

const IDLE_MS = 10 * 60 * 1000;
let lastActive = Date.now();
const wake = new Set();
const touch = () => {
  const was = Date.now() - lastActive > IDLE_MS;
  lastActive = Date.now();
  if (was) wake.forEach(f => f());
};
['pointerdown', 'keydown', 'wheel', 'touchstart', 'mousemove'].forEach(e =>
  addEventListener(e, touch, { passive: true }),
);
const awake = () => document.visibilityState === 'visible' && Date.now() - lastActive < IDLE_MS;

export const usePulse = (fn, ms) =>
  useEffect(() => {
    fn();
    const t = setInterval(() => awake() && fn(), ms);
    const onShow = () => awake() && fn();
    document.addEventListener('visibilitychange', onShow);
    wake.add(fn);
    return () => {
      clearInterval(t);
      document.removeEventListener('visibilitychange', onShow);
      wake.delete(fn);
    };
  }, [fn, ms]);

export const useLoad = (fn, deps = []) => {
  const [state, setState] = useState({ data: null, error: null });
  const latest = useRef(fn);
  useEffect(() => {
    latest.current = fn;
  });
  const reload = useCallback(
    () =>
      latest.current().then(
        data => setState({ data, error: null }),
        error => setState(s => ({ ...s, error })),
      ),
    [],
  );
  const key = JSON.stringify(deps);
  useEffect(() => {
    reload();
  }, [reload, key]);
  return { ...state, reload };
};

export const ToastCtx = createContext(() => {});
export const ConfirmCtx = createContext(async () => false);
export const useConfirm = () => useContext(ConfirmCtx);
export const useToast = () => useContext(ToastCtx);

export const pathFor = (type, id, user) => {
  if (!id && type !== 'AIApproval') return null;
  const m = isManager(user);
  return (
    {
      Task: `/orders/${id}`,
      VideoSubmission: `/review/${id}`,
      Project: `/projects/${id}`,
      ContentItem: m ? `/content/${id}` : '/',
      Todo: '/workspace',
      Event: '/calendar',
      AIApproval: '/approvals',
    }[type] || null
  );
};
