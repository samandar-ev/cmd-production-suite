import { useEffect, useMemo, useRef, useState } from 'react';
import {
  Heading1,
  Heading2,
  List,
  ListOrdered,
  ListChecks,
  Quote,
  Minus,
  Code,
  Lightbulb,
  Bold,
  Italic,
  Eye,
  PencilLine,
  Heading3,
} from 'lucide-react';
import { tr } from '../lib/i18n';
import Markdown from './Markdown';

const BLOCKS = [
  { key: 'h1', label: tr('Heading 1'), hint: tr('Big section title'), icon: Heading1, prefix: '# ' },
  { key: 'h2', label: tr('Heading 2'), hint: tr('Medium title'), icon: Heading2, prefix: '## ' },
  { key: 'h3', label: tr('Heading 3'), hint: tr('Small title'), icon: Heading3, prefix: '### ' },
  { key: 'todo', label: tr('To-do list'), hint: tr('Track tasks with checkboxes'), icon: ListChecks, prefix: '- [ ] ' },
  { key: 'bullet', label: tr('Bulleted list'), hint: tr('A simple list'), icon: List, prefix: '- ' },
  { key: 'number', label: tr('Numbered list'), hint: tr('A list with numbers'), icon: ListOrdered, prefix: '1. ' },
  { key: 'quote', label: tr('Quote'), hint: tr('Capture a quote'), icon: Quote, prefix: '> ' },
  { key: 'callout', label: tr('Callout'), hint: tr('Make something stand out'), icon: Lightbulb, prefix: '> 💡 ' },
  { key: 'code', label: tr('Code'), hint: tr('A code block'), icon: Code, prefix: '```\n', suffix: '\n```' },
  { key: 'divider', label: tr('Divider'), hint: tr('Separate sections'), icon: Minus, prefix: '---\n' },
];

const lineBounds = (text, pos) => {
  const start = text.lastIndexOf('\n', pos - 1) + 1;
  const end = text.indexOf('\n', pos);
  return [start, end === -1 ? text.length : end];
};

export default function NoteEditor({ value, onChange }) {
  const [mode, setMode] = useState(() => (value?.trim() ? 'read' : 'write'));
  const [menu, setMenu] = useState(null);
  const area = useRef(null);
  const items = useMemo(
    () =>
      menu
        ? BLOCKS.filter(
            b =>
              tr(b.label).toLowerCase().includes(menu.query.toLowerCase()) ||
              b.label.toLowerCase().includes(menu.query.toLowerCase()),
          )
        : [],
    [menu],
  );

  useEffect(() => {
    if (mode === 'write') area.current?.focus();
  }, [mode]);

  const replace = (from, to, insert, caret) => {
    const next = value.slice(0, from) + insert + value.slice(to);
    onChange(next);
    requestAnimationFrame(() => {
      const el = area.current;
      if (el) {
        el.focus();
        el.selectionStart = el.selectionEnd = caret ?? from + insert.length;
      }
    });
  };

  const applyBlock = b => {
    const el = area.current;
    const at = menu ? menu.at : el.selectionStart;
    const [start] = lineBounds(value, at);
    const cut = menu ? at + 1 + menu.query.length : at;
    const before = value.slice(start, menu ? at : start);
    replace(start, cut, before + b.prefix + (b.suffix || ''), start + before.length + b.prefix.length);
    setMenu(null);
  };

  const wrap = mark => {
    const el = area.current;
    const { selectionStart: s, selectionEnd: e } = el;
    const sel = value.slice(s, e) || tr('text');
    replace(s, e, `${mark}${sel}${mark}`, s + mark.length + sel.length + mark.length);
  };

  const caretTop = el => {
    const linesAbove = value.slice(0, el.selectionStart).split('\n').length;
    return Math.min(el.clientHeight - 40, linesAbove * 26 - el.scrollTop + 8);
  };

  const onKeyDown = e => {
    const el = e.currentTarget;
    if ((e.metaKey || e.ctrlKey) && (e.key === 'b' || e.key === 'i')) {
      e.preventDefault();
      wrap(e.key === 'b' ? '**' : '*');
      return;
    }
    if (menu) {
      if (e.key === 'ArrowDown') {
        e.preventDefault();
        setMenu(m => ({ ...m, active: Math.min(m.active + 1, items.length - 1) }));
        return;
      }
      if (e.key === 'ArrowUp') {
        e.preventDefault();
        setMenu(m => ({ ...m, active: Math.max(m.active - 1, 0) }));
        return;
      }
      if (e.key === 'Enter' && items[menu.active]) {
        e.preventDefault();
        applyBlock(items[menu.active]);
        return;
      }
      if (e.key === 'Escape') {
        setMenu(null);
        return;
      }
    }
    if (e.key === 'Enter' && !e.shiftKey) {
      const [start, end] = lineBounds(value, el.selectionStart);
      const line = value.slice(start, end);
      const m = line.match(/^(\s*)([-*] \[[ xX]\] |[-*] |(\d+)[.)] |> (?:💡 )?)/);
      if (m && el.selectionStart === end) {
        e.preventDefault();
        if (line.trim() === m[0].trim()) {
          replace(start, end, '', start);
          return;
        }
        const next = m[3]
          ? `${m[1]}${Number(m[3]) + 1}. `
          : m[2].includes('[')
            ? `${m[1]}- [ ] `
            : m[1] + m[2].replace('💡 ', '');
        replace(el.selectionStart, el.selectionStart, `\n${next}`);
      }
    }
  };

  const onInput = e => {
    const el = e.target;
    const v = el.value;
    const pos = el.selectionStart;
    onChange(v);
    const [start] = lineBounds(v, pos);
    const lineToCaret = v.slice(start, pos);
    const slash = lineToCaret.match(/(^|\s)\/([\p{L}\d ]{0,20})$/u);
    if (slash)
      setMenu(m => ({
        at: pos - slash[2].length - 1,
        query: slash[2],
        top: caretTop(el),
        active: m?.query === slash[2] ? m.active : 0,
      }));
    else setMenu(null);
  };

  const toggleTodo = n => {
    const lines = value.split('\n');
    lines[n] = lines[n].replace(/\[( |x|X)\]/, (_, c) => (c === ' ' ? '[x]' : '[ ]'));
    onChange(lines.join('\n'));
  };

  return (
    <div>
      <div className="flex flex-wrap items-center gap-1 mb-4 sticky top-14 lg:top-0 bg-paper z-10 py-1">
        <div className="seg" role="group" aria-label={tr('View')}>
          <button aria-pressed={mode === 'read'} onClick={() => setMode('read')}>
            <Eye size={14} className="inline -mt-0.5 mr-1" />
            {tr('Read')}
          </button>
          <button aria-pressed={mode === 'write'} onClick={() => setMode('write')}>
            <PencilLine size={14} className="inline -mt-0.5 mr-1" />
            {tr('Write')}
          </button>
        </div>
        {mode === 'write' && (
          <>
            <span className="w-px h-6 bg-hairline mx-1" />
            {[
              ['h2', Heading2],
              ['todo', ListChecks],
              ['bullet', List],
              ['callout', Lightbulb],
            ].map(([k, Icon]) => {
              const b = BLOCKS.find(x => x.key === k);
              return (
                <button
                  key={k}
                  onMouseDown={e => e.preventDefault()}
                  onClick={() => applyBlock(b)}
                  className="btn-icon w-9 h-9"
                  title={tr(b.label)}
                  aria-label={tr(b.label)}
                >
                  <Icon size={17} />
                </button>
              );
            })}
            <button
              onMouseDown={e => e.preventDefault()}
              onClick={() => wrap('**')}
              className="btn-icon w-9 h-9"
              title={`${tr('Bold')} (⌘B)`}
              aria-label={tr('Bold')}
            >
              <Bold size={17} />
            </button>
            <button
              onMouseDown={e => e.preventDefault()}
              onClick={() => wrap('*')}
              className="btn-icon w-9 h-9"
              title={`${tr('Italic')} (⌘I)`}
              aria-label={tr('Italic')}
            >
              <Italic size={17} />
            </button>
            <span className="text-[12px] text-mist ml-2 hidden sm:inline">{tr('Type / for blocks')}</span>
          </>
        )}
      </div>

      {mode === 'read' ? (
        <div onDoubleClick={() => setMode('write')} className="min-h-[50vh]">
          {value?.trim() ? (
            <Markdown text={value} onToggle={toggleTodo} />
          ) : (
            <p className="text-mist">
              {tr('Empty note.')}{' '}
              <button onClick={() => setMode('write')} className="underline underline-offset-2">
                {tr('Start writing')}
              </button>
            </p>
          )}
        </div>
      ) : (
        <div className="relative">
          <textarea
            ref={area}
            value={value}
            onChange={onInput}
            onKeyDown={onKeyDown}
            onBlur={() => setTimeout(() => setMenu(null), 150)}
            placeholder={tr('Write, or type / for headings, to-dos, callouts…')}
            aria-label={tr('Note')}
            className="w-full min-h-[55vh] bg-transparent outline-none resize-none leading-[26px] text-[15px] font-[450]"
            spellCheck
          />
          {menu && items.length > 0 && (
            <ul
              role="listbox"
              className="absolute left-0 z-20 w-72 max-h-80 overflow-y-auto bg-paper rounded-[12px] border border-hairline shadow-[0_18px_40px_-18px_rgba(26,31,43,.45)] p-1.5 sheet-in"
              style={{ top: menu.top + 24 }}
            >
              {items.map((b, k) => (
                <li key={b.key} role="option" aria-selected={k === menu.active}>
                  <button
                    onMouseDown={e => e.preventDefault()}
                    onClick={() => applyBlock(b)}
                    onMouseEnter={() => setMenu(m => ({ ...m, active: k }))}
                    className={`w-full flex items-center gap-3 px-2.5 py-2 rounded-[8px] text-left ${k === menu.active ? 'bg-haze' : ''}`}
                  >
                    <span className="w-8 h-8 rounded-[7px] border border-hairline flex items-center justify-center shrink-0">
                      <b.icon size={16} />
                    </span>
                    <span>
                      <span className="block text-[14px] font-medium">{tr(b.label)}</span>
                      <span className="block text-[12px] text-graphite">{tr(b.hint)}</span>
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  );
}
