import React from 'react';

function renderInline(text, sources, keyPrefix) {
  const parts = text.split(/(\*\*[^*]+\*\*|`[^`]+`|\[S\d+\])/g).filter(Boolean);
  return parts.map((part, index) => {
    const key = `${keyPrefix}-${index}`;
    if (part.startsWith('**') && part.endsWith('**')) return <strong key={key} className="font-semibold text-inherit">{part.slice(2, -2)}</strong>;
    if (part.startsWith('`') && part.endsWith('`')) return <code key={key} className="answer-code rounded-md border border-violet-200 bg-violet-50 px-1 py-0.5 font-mono text-[0.92em] text-violet-800">{part.slice(1, -1)}</code>;
    const citation = part.match(/^\[S(\d+)\]$/);
    if (citation) {
      const source = sources?.find((item) => item.citation_id === `S${citation[1]}`);
      if (source?.url) return <a key={key} href={source.url} target="_blank" rel="noreferrer" className="answer-citation mx-0.5 inline-flex items-center rounded-md border border-violet-200 bg-violet-50 px-1.5 py-0.5 align-baseline text-[0.78em] font-semibold text-violet-700 hover:bg-violet-100">{part}</a>;
    }
    return <React.Fragment key={key}>{part}</React.Fragment>;
  });
}

export default function AnswerMarkdown({ content, sources = [] }) {
  const lines = (content || '').split(/\r?\n/);
  const blocks = [];
  let paragraph = [];
  let list = [];
  let listType = '';
  const flushParagraph = () => {
    if (paragraph.length) blocks.push({ type: 'paragraph', lines: paragraph });
    paragraph = [];
  };
  const flushList = () => {
    if (list.length) blocks.push({ type: listType, lines: list });
    list = [];
    listType = '';
  };

  lines.forEach((line) => {
    const trimmed = line.trim();
    const heading = trimmed.match(/^(#{1,3})\s+(.+)$/);
    const numbered = trimmed.match(/^\d+[.)]\s+(.+)$/);
    const bullet = trimmed.match(/^[-*+]\s+(.+)$/);
    if (!trimmed) { flushParagraph(); flushList(); return; }
    if (heading) { flushParagraph(); flushList(); blocks.push({ type: `h${heading[1].length}`, text: heading[2] }); return; }
    if (numbered || bullet) {
      flushParagraph();
      const nextType = numbered ? 'ol' : 'ul';
      if (list.length && listType !== nextType) flushList();
      listType = nextType;
      list.push(numbered?.[1] || bullet?.[1]);
      return;
    }
    flushList();
    paragraph.push(trimmed);
  });
  flushParagraph();
  flushList();

  return <div className="answer-markdown space-y-3 text-sm leading-7 text-slate-700 dark:text-slate-200">
    {blocks.map((block, index) => {
      if (block.type === 'h1' || block.type === 'h2' || block.type === 'h3') {
        const Tag = block.type;
        return <Tag key={index} className="pt-1 text-base font-bold tracking-tight text-slate-900 dark:text-white">{renderInline(block.text, sources, `h${index}`)}</Tag>;
      }
      if (block.type === 'ul' || block.type === 'ol') {
        const Tag = block.type;
        return <Tag key={index} className={`${Tag === 'ul' ? 'list-disc' : 'list-decimal'} space-y-1 pl-6 marker:text-violet-500`}>
          {block.lines.map((line, lineIndex) => <li key={lineIndex} className="pl-1">{renderInline(line, sources, `l${index}-${lineIndex}`)}</li>)}
        </Tag>;
      }
      return <p key={index}>{block.lines.map((line, lineIndex) => <React.Fragment key={lineIndex}>{lineIndex > 0 && <br />}{renderInline(line, sources, `p${index}-${lineIndex}`)}</React.Fragment>)}</p>;
    })}
  </div>;
}
