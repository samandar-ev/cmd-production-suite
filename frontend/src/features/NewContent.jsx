import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import api, { errorText } from '../lib/api';
import { Dialog } from '../ui';
import { useToast } from '../lib/hooks';
import { tr } from '../lib/i18n';

const PLATFORMS = ['Instagram', 'TikTok', 'YouTube', 'Telegram', 'Facebook', 'Website'];
const TYPES = ['Reel', 'Video', 'Story', 'Carousel', 'Photo', 'Film'];

export default function NewContent({ projects, preset, onClose }) {
  const navigate = useNavigate();
  const toast = useToast();
  const active = projects.filter(p => p.status !== 'archived');
  const [form, setForm] = useState({
    title: '',
    project: preset || active[0]?.id || '',
    platform: 'Instagram',
    content_type: 'Reel',
    target_publish_date: '',
    script_scenario: '',
  });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const set = k => e => setForm(f => ({ ...f, [k]: e.target.value }));
  const save = async e => {
    e.preventDefault();
    setBusy(true);
    setError('');
    try {
      const { data } = await api.post('content-items/', {
        ...form,
        target_publish_date: form.target_publish_date ? new Date(form.target_publish_date).toISOString() : null,
      });
      toast(tr('Content added — plan who shoots and edits it'));
      navigate(`/content/${data.id}?plan=1`);
    } catch (err) {
      setError(errorText(err));
      setBusy(false);
    }
  };
  return (
    <Dialog
      title={tr('New content')}
      sub={tr('Add the idea now; you’ll pick the crew and deadlines next.')}
      onClose={onClose}
      footer={
        <>
          <button onClick={onClose} className="btn btn-ghost">
            {tr('Cancel')}
          </button>
          <button form="nc" disabled={busy || !form.title.trim() || !form.project} className="btn btn-primary">
            {busy ? tr('Adding…') : tr('Add content')}
          </button>
        </>
      }
    >
      <form id="nc" onSubmit={save} className="space-y-4">
        {error && (
          <p role="alert" className="text-tally">
            {error}
          </p>
        )}
        <div>
          <label className="label" htmlFor="nc-t">
            {tr('What is it?')}
          </label>
          <input
            id="nc-t"
            className="field"
            value={form.title}
            onChange={set('title')}
            placeholder={tr('e.g. Pumpkin latte reel')}
            required
          />
        </div>
        <div>
          <label className="label" htmlFor="nc-p">
            {tr('Project')}
          </label>
          <select id="nc-p" className="field" value={form.project} onChange={set('project')}>
            {active.map(p => (
              <option key={p.id} value={p.id}>
                {p.name}
              </option>
            ))}
          </select>
        </div>
        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="label" htmlFor="nc-pl">
              {tr('Platform')}
            </label>
            <select id="nc-pl" className="field" value={form.platform} onChange={set('platform')}>
              {PLATFORMS.map(p => (
                <option key={p}>{p}</option>
              ))}
            </select>
          </div>
          <div>
            <label className="label" htmlFor="nc-ty">
              {tr('Format')}
            </label>
            <select id="nc-ty" className="field" value={form.content_type} onChange={set('content_type')}>
              {TYPES.map(p => (
                <option key={p} value={p}>
                  {tr(p)}
                </option>
              ))}
            </select>
          </div>
        </div>
        <div>
          <label className="label" htmlFor="nc-d">
            {tr('Publish on')} <span className="font-normal text-mist">{tr('(optional)')}</span>
          </label>
          <input
            id="nc-d"
            type="datetime-local"
            className="field"
            value={form.target_publish_date}
            onChange={set('target_publish_date')}
          />
        </div>
        <div>
          <label className="label" htmlFor="nc-s">
            {tr('Idea or script')} <span className="font-normal text-mist">{tr('(optional)')}</span>
          </label>
          <textarea
            id="nc-s"
            rows={3}
            className="field"
            value={form.script_scenario}
            onChange={set('script_scenario')}
            placeholder={tr('What happens on screen, the message, the call to action')}
          />
        </div>
      </form>
    </Dialog>
  );
}
