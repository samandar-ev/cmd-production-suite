const INLINE = /(\*\*[^*]+\*\*|~~[^~]+~~|\*[^*\s][^*]*\*|`[^`]+`|\[[^\]]+\]\([^)\s]+\))/g;

function inline(text, key = 'i') {
  return text
    .split(INLINE)
    .filter(Boolean)
    .map((part, i) => {
      const k = `${key}${i}`;
      if (part.startsWith('**') && part.endsWith('**')) return <strong key={k}>{inline(part.slice(2, -2), k)}</strong>;
      if (part.startsWith('~~') && part.endsWith('~~')) return <s key={k}>{part.slice(2, -2)}</s>;
      if (part.startsWith('`') && part.endsWith('`'))
        return (
          <code key={k} className="px-1.5 py-0.5 rounded-[5px] bg-haze text-[0.92em]">
            {part.slice(1, -1)}
          </code>
        );
      if (part.startsWith('*') && part.endsWith('*') && part.length > 2) return <em key={k}>{part.slice(1, -1)}</em>;
      const link = part.match(/^\[([^\]]+)\]\(([^)\s]+)\)$/);
      if (link) {
        const safe = /^(https?:|mailto:|\/)/i.test(link[2]) ? link[2] : '#';
        return (
          <a
            key={k}
            href={safe}
            target={safe.startsWith('/') ? undefined : '_blank'}
            rel="noreferrer"
            className="underline underline-offset-2 decoration-mist hover:decoration-ink"
          >
            {link[1]}
          </a>
        );
      }
      return part;
    });
}

const EMOJI_START = /^(\p{Extended_Pictographic})\s*/u;

export default function Markdown({ text, onToggle }) {
  const lines = (text || '').split('\n');
  const out = [];
  let i = 0;
  const listOf = (re, ordered) => {
    const items = [];
    while (i < lines.length && re.test(lines[i])) {
      items.push({ n: i, text: lines[i].replace(re, '') });
      i += 1;
    }
    const Tag = ordered ? 'ol' : 'ul';
    out.push(
      <Tag
        key={`l${items[0].n}`}
        className={`${ordered ? 'list-decimal' : 'list-disc'} pl-6 my-2 space-y-1 marker:text-mist`}
      >
        {items.map(it => (
          <li key={it.n}>{inline(it.text, `l${it.n}`)}</li>
        ))}
      </Tag>,
    );
  };
  while (i < lines.length) {
    const line = lines[i];
    if (line.startsWith('```')) {
      const start = i;
      const code = [];
      i += 1;
      while (i < lines.length && !lines[i].startsWith('```')) {
        code.push(lines[i]);
        i += 1;
      }
      i += 1;
      out.push(
        <pre key={`c${start}`} className="my-3 p-4 rounded-[10px] bg-haze text-[13px] overflow-x-auto">
          <code>{code.join('\n')}</code>
        </pre>,
      );
      continue;
    }
    const h = line.match(/^(#{1,3})\s+(.*)/);
    if (h) {
      const size = [
        'text-[25px] display font-semibold mt-6 mb-2',
        'text-[20px] font-semibold mt-6 mb-1.5',
        'text-[17px] font-semibold mt-4 mb-1',
      ][h[1].length - 1];
      const Tag = `h${h[1].length + 1}`;
      out.push(
        <Tag key={`h${i}`} className={size}>
          {inline(h[2], `h${i}`)}
        </Tag>,
      );
      i += 1;
      continue;
    }
    const todo = line.match(/^\s*[-*] \[( |x|X)\]\s?(.*)/);
    if (todo) {
      const n = i;
      const done = todo[1] !== ' ';
      out.push(
        <label key={`t${n}`} className="flex items-start gap-2.5 my-1 cursor-pointer">
          <input
            type="checkbox"
            checked={done}
            onChange={() => onToggle?.(n)}
            disabled={!onToggle}
            className="mt-1 w-4 h-4 accent-ink shrink-0"
          />
          <span className={done ? 'line-through text-mist' : ''}>{inline(todo[2], `t${n}`)}</span>
        </label>,
      );
      i += 1;
      continue;
    }
    if (/^\s*[-*]\s+/.test(line)) {
      listOf(/^\s*[-*]\s+(?!\[[ xX]\])/, false);
      continue;
    }
    if (/^\s*\d+[.)]\s+/.test(line)) {
      listOf(/^\s*\d+[.)]\s+/, true);
      continue;
    }
    if (/^>\s?/.test(line)) {
      const start = i;
      const body = [];
      while (i < lines.length && /^>\s?/.test(lines[i])) {
        body.push(lines[i].replace(/^>\s?/, ''));
        i += 1;
      }
      const emoji = body[0]?.match(EMOJI_START);
      out.push(
        emoji ? (
          <div key={`q${start}`} className="my-3 flex gap-3 rounded-[10px] bg-haze px-4 py-3">
            <span aria-hidden>{emoji[1]}</span>
            <div>
              {body.map((b, k) => (
                <p key={k}>{inline(k ? b : b.replace(EMOJI_START, ''), `q${start}${k}`)}</p>
              ))}
            </div>
          </div>
        ) : (
          <blockquote key={`q${start}`} className="my-3 border-l-[3px] border-ink pl-4 text-graphite">
            {body.map((b, k) => (
              <p key={k}>{inline(b, `q${start}${k}`)}</p>
            ))}
          </blockquote>
        ),
      );
      continue;
    }
    if (/^(-{3,}|\*{3,})\s*$/.test(line)) {
      out.push(<hr key={`d${i}`} className="my-5 border-hairline" />);
      i += 1;
      continue;
    }
    if (!line.trim()) {
      out.push(<div key={`s${i}`} className="h-2" />);
      i += 1;
      continue;
    }
    out.push(
      <p key={`p${i}`} className="my-1 leading-relaxed">
        {inline(line, `p${i}`)}
      </p>,
    );
    i += 1;
  }
  return <div className="text-[15px] break-words">{out}</div>;
}
